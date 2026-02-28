# workers.py
# 后台工作线程，处理耗时任务

import os, tempfile
from pathlib import Path
import re
try: import torch
except ImportError: torch = None
import numpy as np
from faster_whisper import WhisperModel
from PyQt6.QtCore import QThread, pyqtSignal
import ffmpeg, openai

from utils import format_time

class AudioWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    def __init__(self, media_path, parent=None):
        super().__init__(parent); self.media_path = str(media_path)
    def run(self):
        try:
            out, _ = (ffmpeg.input(self.media_path).output('-', format='f32le', acodec='pcm_f32le', ac=1, ar=16000).run(cmd='ffmpeg', capture_stdout=True, capture_stderr=True))
            probe = ffmpeg.probe(self.media_path)
            duration = float(probe['format']['duration'])
            
            waveform = np.frombuffer(out, dtype=np.float32)
            chunk_size = 1024
            num_chunks = len(waveform) // chunk_size
            
            if num_chunks > 0:
                waveform = waveform[:num_chunks * chunk_size]
                waveform = waveform.reshape((num_chunks, chunk_size))
                time_axis = np.arange(num_chunks) * (chunk_size / 16000.0)
                min_vals = waveform.min(axis=1)
                max_vals = waveform.max(axis=1)
                rms_vals = np.sqrt(np.mean(waveform**2, axis=1))
                processed_data = (time_axis, min_vals, max_vals, rms_vals)
                self.finished.emit((duration, processed_data))
            else:
                empty_data = (np.array([]), np.array([]), np.array([]), np.array([]))
                self.finished.emit((duration, empty_data))
        except Exception as e: self.error.emit(f"FFmpeg处理音频失败: {e}")

class TranscriptionWorker(QThread):
    segment_ready = pyqtSignal(dict)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    def __init__(self, media_path, model_path, device, whisper_params, parent=None):
        super().__init__(parent)
        self.media_path = media_path; self.model_path = model_path; self.device = device; self.whisper_params = whisper_params; self._is_running = True
    def run(self):
        model = None
        try:
            compute_type = "float16" if self.device == "cuda" else "int8"
            model = WhisperModel(self.model_path, device=self.device, compute_type=compute_type)
            segments, info = model.transcribe(str(self.media_path), **self.whisper_params)
            
            srt_content = ""
            for i, segment in enumerate(segments):
                if not self._is_running: break
                start_time_str = format_time(segment.start)
                end_time_str = format_time(segment.end)
                text = segment.text.strip()
                self.segment_ready.emit({'index': i + 1, 'start_time': start_time_str, 'end_time': end_time_str, 'text': text, 'start_sec': segment.start, 'end_sec': segment.end})
                srt_content += f"{i + 1}\n{start_time_str} --> {end_time_str}\n{text}\n\n"
            
            if self._is_running:
                cache_dir = Path.home() / ".whisper_gui_tool" / "cache"
                cache_dir.mkdir(parents=True, exist_ok=True)
                srt_path = cache_dir / (self.media_path.stem + ".srt")
                with open(srt_path, "w", encoding="utf-8") as f: f.write(srt_content)
                self.finished.emit(str(srt_path))
        except Exception as e:
            self.error.emit(f"转写失败: {e}")
        finally:
            if model:
                del model
                if torch and torch.cuda.is_available():
                    torch.cuda.empty_cache()
    def stop(self): self._is_running = False

class RetranscribeWorker(QThread):
    finished = pyqtSignal(str, int)
    error = pyqtSignal(str)
    def __init__(self, media_path, model, start_sec, end_sec, row_index, whisper_params, parent=None):
        super().__init__(parent)
        self.media_path = str(media_path); self.model = model; self.start_sec = start_sec; self.end_sec = end_sec; self.row_index = row_index; self.whisper_params = whisper_params
    def run(self):
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpfile:
                tmp_path = tmpfile.name
            try:
                (ffmpeg.input(self.media_path, ss=self.start_sec, to=self.end_sec)
                 .output(tmp_path, acodec='pcm_s16le', ac=1, ar=16000)
                 .run(cmd='ffmpeg', capture_stdout=True, capture_stderr=True, overwrite_output=True))
                
                segments, _ = self.model.transcribe(tmp_path, **self.whisper_params)
                new_text = " ".join(seg.text.strip() for seg in segments)
                self.finished.emit(new_text or "[无语音]", self.row_index)
            finally:
                if os.path.exists(tmp_path): os.remove(tmp_path)
        except Exception as e:
            self.error.emit(f"重新转写失败: {e}")
        finally:
            del self.model
            self.model = None

class TranslationWorker(QThread):
    segment_translated = pyqtSignal(int, str)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    def __init__(self, subtitles, indices_to_process, api_config, parent=None):
        super().__init__(parent)
        self.subtitles = subtitles; self.indices_to_process = indices_to_process; self.api_config = api_config; self._is_running = True
        self.remove_re = re.compile(r"[\"\'“”（）《》【】「」]")
        self.space_re = re.compile(r"[\s.,!?;:、。，；：？！]+")

    def run(self):
        try:
            client = openai.OpenAI(api_key=self.api_config['key'], base_url=self.api_config['base'])
            
            for i in self.indices_to_process:
                if not self._is_running: break
                
                current_text_to_translate = self.subtitles[i]['text']

                if self.api_config['use_context']:
                    full_text_list = [sub['text'] for sub in self.subtitles]
                    context_start = max(0, i - self.api_config['context_lines'])
                    context_end = min(len(full_text_list), i + self.api_config['context_lines'] + 1)
                    context_slices = full_text_list[context_start:context_end]
                    
                    context_str = "\n".join(
                        f"{'' if (idx + context_start) != i else '>> '}{line}" 
                        for idx, line in enumerate(context_slices)
                    )
                    
                    # <<< 核心修复：将 'target_line' 改回 'text'，与标准模式保持一致 >>>
                    prompt = self.api_config['prompt'].format(context=context_str, text=current_text_to_translate)
                else:
                    prompt = self.api_config['prompt'].format(text=current_text_to_translate)

                response = client.chat.completions.create(model=self.api_config['model'], messages=[{"role": "user", "content": prompt}], temperature=0)
                raw_translation = response.choices[0].message.content.strip().strip('"')
                no_quotes_text = self.remove_re.sub('', raw_translation)
                cleaned_translation = self.space_re.sub(' ', no_quotes_text).strip()
                
                self.segment_translated.emit(i, cleaned_translation)

            if self._is_running: self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))
        
    def stop(self): self._is_running = False