# main.py
# 主应用程序窗口和入口点

import sys, os, re, time, contextlib
import gc
from pathlib import Path
try: import torch
except ImportError: torch = None
import pyqtgraph as pg, vlc
from faster_whisper import WhisperModel
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QProgressDialog, QMessageBox, QLabel, QStyle, QComboBox, QStatusBar, QToolButton, QSlider, QMenu, QInputDialog)
from PyQt6.QtCore import Qt, QTimer, QPoint
import config
from utils import format_time, parse_time
from workers import AudioWorker, TranscriptionWorker, RetranscribeWorker, TranslationWorker
from widgets import AudioVisualizer, EditDialog, SettingsDialog

pg.setConfigOptions(useOpenGL=True, antialias=True)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("Whisper GUI 工具"); self.setGeometry(100, 100, 1400, 800); self.model = None; self.media_path = None; self.srt_path = None; self.subtitles = []; self.progress_dialog = None; self.active_dialog = None; self.media_duration_ms = 0; self.preview_end_time = None; self.animation_timer = QTimer(self); self.last_known_vlc_time_ms = 0; self.last_update_monotonic_time = 0
        # <<< 关键修复 3：规范化worker属性的初始化 >>>
        self.audio_worker = None; self.transcription_worker = None; self.retranscribe_worker = None; self.translation_worker = None
        vlc_args = ['--quiet', '--avcodec-hw=none', '--vout=windib', '--no-one-instance', '--ignore-config', '--no-video-title-show']
        with open(os.devnull, 'w') as devnull:
            with contextlib.redirect_stderr(devnull): self.vlc_instance = vlc.Instance(vlc_args)
        self.player = self.vlc_instance.media_player_new(); self.init_ui(); self.set_icons(); self.populate_model_combo()
    
    def init_ui(self):
        central_widget = QWidget(); self.setCentralWidget(central_widget); main_layout = QHBoxLayout(central_widget); left_layout = QVBoxLayout(); self.video_frame = QWidget(); self.video_frame.setStyleSheet("background-color: black;"); left_layout.addWidget(self.video_frame, 3); audio_layout = QHBoxLayout(); self.audio_canvas = AudioVisualizer(self); self.audio_canvas.region_updated.connect(self.on_spectrogram_region_updated); audio_layout.addWidget(self.audio_canvas, 1); self.height_slider = QSlider(Qt.Orientation.Vertical); self.height_slider.setRange(0, 100); self.height_slider.setValue(50); self.height_slider.setFixedWidth(20); self.height_slider.valueChanged.connect(self.audio_canvas.set_height_multiplier); audio_layout.addWidget(self.height_slider); left_layout.addLayout(audio_layout, 1); self.progress_slider = QSlider(Qt.Orientation.Horizontal); self.progress_slider.setFixedHeight(15); self.progress_slider.sliderMoved.connect(self.seek_video); self.progress_slider.valueChanged.connect(self.update_playhead_from_slider); left_layout.addWidget(self.progress_slider); control_layout = QHBoxLayout(); self.play_pause_btn = QPushButton("播放/暂停"); self.play_pause_btn.clicked.connect(self.toggle_play_pause); self.stop_btn = QPushButton("停止"); self.stop_btn.clicked.connect(self.stop_video); control_layout.addWidget(self.play_pause_btn); control_layout.addWidget(self.stop_btn); left_layout.addLayout(control_layout)
        right_layout = QVBoxLayout(); file_ops_layout = QHBoxLayout(); self.open_btn = QPushButton("打开媒体"); self.open_btn.clicked.connect(self.open_file); self.import_btn = QPushButton("导入SRT"); self.import_btn.clicked.connect(self.import_srt_file); self.transcribe_btn = QPushButton("开始转写"); self.transcribe_btn.clicked.connect(self.start_transcription); file_ops_layout.addWidget(self.open_btn); file_ops_layout.addWidget(self.import_btn); file_ops_layout.addWidget(self.transcribe_btn); right_layout.addLayout(file_ops_layout)
        translation_layout = QHBoxLayout()
        self.translate_all_btn = QPushButton("翻译全部...")
        translate_all_menu = QMenu(self)
        standard_action = translate_all_menu.addAction("标准翻译")
        context_action = translate_all_menu.addAction("带上下文翻译")
        self.translate_all_btn.setMenu(translate_all_menu)
        standard_action.triggered.connect(lambda: self.handle_full_translation(use_context=False))
        context_action.triggered.connect(lambda: self.handle_full_translation(use_context=True))
        translation_layout.addWidget(self.translate_all_btn); right_layout.addLayout(translation_layout)
        config_layout = QHBoxLayout(); config_layout.addWidget(QLabel("模型:")); self.model_combo = QComboBox(); config_layout.addWidget(self.model_combo, 1); self.refresh_models_btn = QToolButton(); self.refresh_models_btn.clicked.connect(self.populate_model_combo); config_layout.addWidget(self.refresh_models_btn); self.settings_btn = QPushButton("设置"); self.settings_btn.clicked.connect(self.open_settings_dialog); config_layout.addWidget(self.settings_btn); config_layout.addWidget(QLabel("设备:")); self.device_combo = QComboBox(); self.device_combo.addItems(["cuda", "cpu"]); config_layout.addWidget(self.device_combo); right_layout.addLayout(config_layout)
        model_mgmt_layout = QHBoxLayout(); self.load_model_btn = QPushButton("加载模型"); self.load_model_btn.clicked.connect(self.load_whisper_model); self.unload_model_btn = QPushButton("卸载模型"); self.unload_model_btn.clicked.connect(self.unload_whisper_model); self.unload_model_btn.setEnabled(False); model_mgmt_layout.addWidget(self.load_model_btn); model_mgmt_layout.addWidget(self.unload_model_btn); right_layout.addLayout(model_mgmt_layout)
        self.subtitle_table = QTableWidget(); self.subtitle_table.setColumnCount(5); self.subtitle_table.setHorizontalHeaderLabels(["序号", "开始", "结束", "原文", "译文"]); self.subtitle_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.subtitle_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.subtitle_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection); header = self.subtitle_table.horizontalHeader(); header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents); header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents); header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents); header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch); header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch); self.subtitle_table.cellClicked.connect(self.jump_to_timestamp); self.subtitle_table.cellDoubleClicked.connect(self.edit_subtitle); self.subtitle_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.subtitle_table.customContextMenuRequested.connect(self.show_context_menu); right_layout.addWidget(self.subtitle_table)
        save_layout = QHBoxLayout(); self.update_cache_btn = QPushButton("更新缓存"); self.update_cache_btn.clicked.connect(self.update_srt_cache); self.save_btn = QPushButton("保存SRT文件"); self.save_btn.clicked.connect(self.save_srt); save_layout.addWidget(self.update_cache_btn); save_layout.addWidget(self.save_btn); right_layout.addLayout(save_layout)
        main_layout.addLayout(left_layout, 2); main_layout.addLayout(right_layout, 1); self.status_bar = QStatusBar(); self.setStatusBar(self.status_bar); self.player.set_hwnd(int(self.video_frame.winId()))

    # --- 翻译相关函数 ---
    def check_api_settings(self):
        if not config.SETTINGS.get("openai_api_base"): QMessageBox.warning(self, "API未配置", "请先在'设置'中配置您的API地址 (API Base URL)。"); return False
        return True
    def handle_full_translation(self, use_context):
        if not self.check_api_settings() or not self.subtitles: return
        mode_text = "带上下文翻译" if use_context else "标准翻译"
        reply = QMessageBox.question(self, "确认翻译", f"将使用 '{mode_text}' 模式和模型 '{config.SETTINGS.get('openai_model')}' 翻译全部 {len(self.subtitles)} 条字幕。是否继续？")
        if reply == QMessageBox.StandardButton.No: return
        self.progress_dialog = QProgressDialog("正在翻译字幕...", "取消", 0, len(self.subtitles), self); self.progress_dialog.setWindowTitle("翻译中"); self.progress_dialog.canceled.connect(self.cancel_translation); self.progress_dialog.show()
        self.start_translation(self.subtitles, use_context=use_context)
    def translate_single_segment(self, row, use_context):
        if not self.check_api_settings(): return
        self.start_translation([self.subtitles[row]], use_context=use_context)
    def start_translation(self, subs_to_translate, use_context):
        base_config = { 'base': config.SETTINGS.get("openai_api_base"), 'key': config.SETTINGS.get("openai_api_key"), 'model': config.SETTINGS.get("openai_model") }
        if use_context:
            prompt_name = config.SETTINGS.get("active_contextual_prompt_name")
            prompt_template = config.SETTINGS.get("translation_prompts", {}).get("contextual", {}).get(prompt_name)
            if not prompt_template: self.show_critical_error("未找到有效的上下文提示词，请在设置中检查。"); return
            api_config = { **base_config, 'use_context': True, 'prompt': prompt_template, 'context_lines': config.SETTINGS.get("translation_context_lines") }
        else:
            prompt_name = config.SETTINGS.get("active_standard_prompt_name")
            prompt_template = config.SETTINGS.get("translation_prompts", {}).get("standard", {}).get(prompt_name)
            if not prompt_template: self.show_critical_error("未找到有效的标准提示词，请在设置中检查。"); return
            api_config = { **base_config, 'use_context': False, 'prompt': prompt_template }
        indices_to_process = [self.subtitles.index(sub) for sub in subs_to_translate]
        self.translation_worker = TranslationWorker(self.subtitles, indices_to_process, api_config, self); self.translation_worker.segment_translated.connect(self.on_segment_translated); self.translation_worker.finished.connect(self.on_translation_finished); self.translation_worker.error.connect(self.on_translation_error); self.translation_worker.start()
    def on_segment_translated(self, row_index, translated_text):
        self.subtitles[row_index]['translation'] = translated_text; self.subtitle_table.setItem(row_index, 4, QTableWidgetItem(translated_text)); self.subtitle_table.selectRow(row_index)
        if self.progress_dialog: self.progress_dialog.setValue(self.progress_dialog.value() + 1)
    def on_translation_finished(self):
        self.status_bar.showMessage("翻译完成！", 5000)
        if self.progress_dialog: self.progress_dialog.close(); self.progress_dialog = None
        self.translation_worker = None
    def on_translation_error(self, error_msg):
        self.show_critical_error(f"翻译失败: {error_msg}")
        if self.progress_dialog: self.progress_dialog.close(); self.progress_dialog = None
        self.translation_worker = None
    def cancel_translation(self):
        if self.translation_worker: self.translation_worker.stop(); self.status_bar.showMessage("翻译已取消", 5000)

    # --- 右键菜单和表格操作 ---
    def show_context_menu(self, position: QPoint):
        selected_rows = sorted(list(set(item.row() for item in self.subtitle_table.selectedItems())));
        if not selected_rows: return
        menu = QMenu()
        if len(selected_rows) == 1:
            row = selected_rows[0]; 
            menu.addAction("重新转写原文").triggered.connect(lambda: self.retranscribe_segment(row))
            menu.addSeparator()
            menu.addAction("标准翻译此句").triggered.connect(lambda: self.translate_single_segment(row, use_context=False))
            menu.addAction("带上下文翻译此句").triggered.connect(lambda: self.translate_single_segment(row, use_context=True))
            menu.addSeparator()
            menu.addAction("编辑").triggered.connect(lambda: self.edit_subtitle(row, 0))
            menu.addAction("从中间拆分").triggered.connect(lambda: self.handle_split_row(row))
            menu.addAction("删除").triggered.connect(lambda: self.handle_delete_row(row))
            menu.addSeparator()
            menu.addAction("复制起始时间").triggered.connect(lambda: self.handle_copy_time(row, 'start'))
            menu.addAction("复制结束时间").triggered.connect(lambda: self.handle_copy_time(row, 'end'))
        else: 
            menu.addAction("合并选中行").triggered.connect(lambda: self.handle_merge_rows(selected_rows))
        menu.exec(self.subtitle_table.viewport().mapToGlobal(position))
    def add_subtitle_segment(self, segment_data):
        segment_data['translation'] = ''; self.subtitles.append(segment_data); row_count = self.subtitle_table.rowCount(); self.subtitle_table.insertRow(row_count); self.subtitle_table.setItem(row_count, 0, QTableWidgetItem(str(segment_data['index']))); self.subtitle_table.setItem(row_count, 1, QTableWidgetItem(segment_data['start_time'])); self.subtitle_table.setItem(row_count, 2, QTableWidgetItem(segment_data['end_time'])); self.subtitle_table.setItem(row_count, 3, QTableWidgetItem(segment_data['text'])); self.subtitle_table.setItem(row_count, 4, QTableWidgetItem('')); self.subtitle_table.scrollToBottom()
    def populate_table(self):
        self.subtitle_table.setRowCount(0)
        for sub in self.subtitles:
            row_count = self.subtitle_table.rowCount(); self.subtitle_table.insertRow(row_count); self.subtitle_table.setItem(row_count, 0, QTableWidgetItem(str(sub['index']))); self.subtitle_table.setItem(row_count, 1, QTableWidgetItem(sub['start_time'])); self.subtitle_table.setItem(row_count, 2, QTableWidgetItem(sub['end_time'])); self.subtitle_table.setItem(row_count, 3, QTableWidgetItem(sub['text'])); self.subtitle_table.setItem(row_count, 4, QTableWidgetItem(sub.get('translation', '')))
    def edit_subtitle(self, row, column):
        if row < len(self.subtitles):
            self.active_dialog = EditDialog(self.subtitles[row], row, self)
            if self.active_dialog.exec(): updated_data = self.active_dialog.get_data(); self.subtitles[row].update({**updated_data, 'start_time': format_time(updated_data['start_sec']), 'end_time': format_time(updated_data['end_sec'])}); self.populate_table(); self.subtitle_table.selectRow(row); self.audio_canvas.update_all_regions(self.subtitles)
            self.active_dialog = None
    def handle_merge_rows(self, rows):
        if len(rows) < 2: return
        for i in range(1, len(rows)):
            if rows[i] != rows[i-1] + 1: QMessageBox.warning(self, "操作失败", "只能合并连续的字幕行。"); return
        first_row, last_row = rows[0], rows[-1]; first_sub, last_sub = self.subtitles[first_row], self.subtitles[last_row]; merged_text = " ".join(self.subtitles[r]['text'] for r in rows); merged_translation = " ".join(self.subtitles[r].get('translation', '') for r in rows).strip(); first_sub.update({ 'end_sec': last_sub['end_sec'], 'end_time': last_sub['end_time'], 'text': merged_text, 'translation': merged_translation });
        for r in reversed(rows[1:]): self.subtitles.pop(r)
        self.reindex_subtitles(); self.populate_table(); self.audio_canvas.update_all_regions(self.subtitles); self.subtitle_table.selectRow(first_row)
    def reindex_subtitles(self):
        for i, sub in enumerate(self.subtitles): sub['index'] = i + 1
    def handle_split_row(self, row):
        if not (0 <= row < len(self.subtitles)): return
        sub = self.subtitles[row]; duration = sub['end_sec'] - sub['start_sec']
        if duration < 0.1: QMessageBox.warning(self, "操作失败", "该行字幕太短，无法拆分。"); return
        mid_sec = sub['start_sec'] + duration / 2; text = sub['text']; mid_text_idx = len(text) // 2; trans = sub.get('translation', ''); mid_trans_idx = len(trans) // 2; new_sub = {'index': 0, 'start_sec': mid_sec, 'end_sec': sub['end_sec'], 'text': text[mid_text_idx:].lstrip(), 'translation': trans[mid_trans_idx:].lstrip(), 'start_time': format_time(mid_sec), 'end_time': sub['end_time']}; sub.update({ 'end_sec': mid_sec, 'end_time': format_time(mid_sec), 'text': text[:mid_text_idx].rstrip(), 'translation': trans[:mid_trans_idx].rstrip() }); self.subtitles.insert(row + 1, new_sub); self.reindex_subtitles(); self.populate_table(); self.audio_canvas.update_all_regions(self.subtitles); self.subtitle_table.selectRow(row + 1)
    def handle_delete_row(self, row):
        if 0 <= row < len(self.subtitles):
            reply = QMessageBox.question(self, '确认删除', f"确定要删除第 {self.subtitles[row]['index']} 行字幕吗？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes: self.subtitles.pop(row); self.reindex_subtitles(); self.populate_table(); self.audio_canvas.update_all_regions(self.subtitles)
    def handle_copy_time(self, row, time_type):
        if 0 <= row < len(self.subtitles): time_key = 'start_time' if time_type == 'start' else 'end_time'; time_str = self.subtitles[row][time_key]; QApplication.clipboard().setText(time_str); self.status_bar.showMessage(f"已复制: {time_str}", 3000)

    # --- 文件、设置和媒体播放 ---
    def open_settings_dialog(self):
        dialog = SettingsDialog(config.SETTINGS, self)
        if dialog.exec():
            new_settings = dialog.get_settings()
            config.save_settings(new_settings)
            config.SETTINGS.update(new_settings)
            QMessageBox.information(self, "设置已保存", "所有设置已立即生效。")
            self.populate_model_combo()
    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "打开媒体文件");
        if not file_path: return
        self.progress_dialog = QProgressDialog("正在处理/读取音频...", "取消", 0, 0, self); self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal); self.progress_dialog.setWindowTitle("请稍候"); self.progress_dialog.show(); self.media_path = Path(file_path); self.subtitles.clear(); self.subtitle_table.setRowCount(0); self.setWindowTitle(f"Whisper GUI 工具 - {self.media_path.name}"); self.audio_worker = AudioWorker(self.media_path, self); self.audio_worker.finished.connect(self.on_audio_loaded); self.audio_worker.error.connect(self.show_critical_error); self.audio_worker.start(); cached_srt_path = config.CACHE_DIR / (self.media_path.stem + ".srt");
        if cached_srt_path.exists(): self.load_srt(srt_path=str(cached_srt_path))
        self.load_media()
    def load_srt(self, srt_path=None):
        path_to_load = srt_path if srt_path else self.srt_path;
        if not path_to_load: return
        self.subtitles.clear()
        try:
            with open(path_to_load, 'r', encoding='utf-8') as f: content = f.read()
            pattern = re.compile(r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)\n\n', re.DOTALL)
            for match in pattern.finditer(content):
                text_block = match.group(4).strip().split('\n'); original_text = ''; translation = ''
                if len(text_block) > 1 and text_block[0] and text_block[1]: translation = text_block[0]; original_text = '\n'.join(text_block[1:])
                else: original_text = '\n'.join(text_block)
                self.subtitles.append({'index': int(match.group(1)), 'start_time': match.group(2), 'end_time': match.group(3), 'start_sec': parse_time(match.group(2)), 'end_sec': parse_time(match.group(3)), 'text': original_text, 'translation': translation})
            self.populate_table(); self.srt_path = path_to_load; self.status_bar.showMessage(f"已加载字幕: {Path(path_to_load).name}", 5000); self.audio_canvas.update_all_regions(self.subtitles)
        except Exception as e: QMessageBox.critical(self, "错误", f"加载SRT失败: {e}")
    def import_srt_file(self):
        srt_path, _ = QFileDialog.getOpenFileName(self, "导入SRT", "", "SRT Files (*.srt)")
        if srt_path:
            self.load_srt(srt_path=srt_path)
    def save_srt(self):
        if not self.subtitles: QMessageBox.warning(self, "警告", "无可保存字幕"); return
        items = ["仅原文", "仅译文", "双语 (译文在上)"]; item, ok = QInputDialog.getItem(self, "选择保存模式", "请选择要导出的字幕内容:", items, 0, False)
        if not ok or not item: return
        default_name = self.media_path.stem + ".srt" if self.media_path else "subtitles.srt"; save_path, _ = QFileDialog.getSaveFileName(self, "保存SRT文件", default_name, "SRT (*.srt)")
        if not save_path: return
        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                for sub in self.subtitles:
                    text_to_write = ""
                    if item == "仅原文": text_to_write = sub['text']
                    elif item == "仅译文": text_to_write = sub.get('translation', '') or sub['text']
                    elif item == "双语 (译文在上)": trans = sub.get('translation', ''); orig = sub['text']; text_to_write = f"{trans}\n{orig}" if trans else orig
                    f.write(f"{sub['index']}\n{sub['start_time']} --> {sub['end_time']}\n{text_to_write.strip()}\n\n")
            self.status_bar.showMessage(f"已保存到: {save_path}")
        except Exception as e: QMessageBox.critical(self, "错误", f"保存失败: {e}")
    def update_srt_cache(self):
        if not self.media_path or not self.subtitles: QMessageBox.warning(self, "警告", "没有可更新的媒体或字幕。"); return
        cache_path = config.CACHE_DIR / (self.media_path.stem + ".srt")
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                for sub in self.subtitles:
                    trans = sub.get('translation', ''); orig = sub['text']; text_to_write = f"{trans}\n{orig}" if trans and orig else orig
                    f.write(f"{sub['index']}\n{sub['start_time']} --> {sub['end_time']}\n{text_to_write.strip()}\n\n")
            self.status_bar.showMessage(f"字幕缓存已更新: {cache_path.name}", 5000)
        except Exception as e: QMessageBox.critical(self, "错误", f"更新缓存失败: {e}")
    def on_audio_loaded(self, result):
        if self.progress_dialog: self.progress_dialog.close(); self.progress_dialog = None
        if result: duration, waveform_data = result; self.media_duration_ms = int(duration * 1000); self.progress_slider.setMaximum(self.media_duration_ms); self.animation_timer.setInterval(16); self.animation_timer.timeout.connect(self.animate_playhead); event_manager = self.player.event_manager(); event_manager.event_attach(vlc.EventType.MediaPlayerPositionChanged, self.handle_vlc_position_change); self.audio_canvas.plot_data(duration, waveform_data); self.status_bar.showMessage("音频加载完成", 5000); self.audio_canvas.update_all_regions(self.subtitles)
        else: self.status_bar.showMessage("音频处理失败！", 5000)
    def handle_vlc_position_change(self, event):
        if self.media_duration_ms > 0:
            position_ms = int(event.u.new_position * self.media_duration_ms); self.last_known_vlc_time_ms = position_ms; self.last_update_monotonic_time = time.monotonic();
            if self.progress_slider.value() != position_ms: self.progress_slider.blockSignals(True); self.progress_slider.setValue(position_ms); self.progress_slider.blockSignals(False)
    def animate_playhead(self):
        if self.media_duration_ms == 0: return
        if self.preview_end_time is not None and self.player.is_playing():
            current_time_ms = self.player.get_time()
            if current_time_ms / 1000.0 >= self.preview_end_time: self.pause_after_preview(self.preview_end_time); return 
        if not self.player.is_playing(): return
        elapsed_since_last_sync = time.monotonic() - self.last_update_monotonic_time; estimated_time_ms = self.last_known_vlc_time_ms + (elapsed_since_last_sync * 1000); estimated_time_ms = min(estimated_time_ms, self.media_duration_ms); self.audio_canvas.update_playhead_position(estimated_time_ms / 1000.0)
    def _force_update_position(self, time_ms):
        self.last_known_vlc_time_ms = time_ms; self.last_update_monotonic_time = time.monotonic(); seconds = time_ms / 1000.0; self.audio_canvas.update_playhead_position(seconds); self.progress_slider.blockSignals(True); self.progress_slider.setValue(int(time_ms)); self.progress_slider.blockSignals(False)
    def seek_video(self, value_ms):
        if self.media_duration_ms > 0: self.player.set_position(value_ms / self.media_duration_ms); self._force_update_position(value_ms)
    def update_playhead_from_slider(self, value_ms): self.audio_canvas.update_playhead_position(value_ms / 1000.0)
    def jump_to_timestamp(self, row, column):
        if 0 <= row < len(self.subtitles): sub = self.subtitles[row]; self.audio_canvas.focus_on_region(row); start_ms = int(sub['start_sec'] * 1000); self.preview_end_time = sub['end_sec']; self.player.play(); self.player.set_time(start_ms); self._force_update_position(start_ms); self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause)); self.animation_timer.start()
    def pause_after_preview(self, final_pos_sec):
        if self.player.is_playing(): self.player.pause(); self.animation_timer.stop(); self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self._force_update_position(final_pos_sec * 1000); self.preview_end_time = None
    def toggle_play_pause(self):
        self.preview_end_time = None
        if self.player.is_playing(): self.player.pause(); self.animation_timer.stop(); self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)); self._force_update_position(self.player.get_time())
        else: self.player.play(); self.animation_timer.start(); self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
    def stop_video(self): self.preview_end_time = None; self.player.stop(); self.animation_timer.stop(); self._force_update_position(0); self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
    def load_media(self):
        if self.media_path: media = self.vlc_instance.media_new(str(self.media_path)); self.player.set_media(media)
    def closeEvent(self, event):
        self.setWindowTitle("正在关闭，请稍候...")
        QApplication.processEvents()
        self.animation_timer.stop()
        workers_to_stop = [self.audio_worker, self.transcription_worker, self.retranscribe_worker, self.translation_worker]
        for worker in workers_to_stop:
            if worker and worker.isRunning():
                worker.stop()
                worker.wait(2000)
        if self.player and self.player.is_playing(): self.player.stop()
        self.unload_whisper_model(); QApplication.processEvents()
        if self.player:
            try:
                event_manager = self.player.event_manager()
                if event_manager: event_manager.event_detach(vlc.EventType.MediaPlayerPositionChanged)
            except Exception as e: print(f"分离VLC事件时出错 (可忽略): {e}")
            self.player.release(); self.player = None
        if self.vlc_instance: self.vlc_instance.release(); self.vlc_instance = None
        gc.collect(); event.accept()

    # --- Whisper 模型和转写 ---
    def start_transcription(self):
        if not self.media_path: QMessageBox.warning(self, "警告", "请先打开文件！"); return
        if not self.model_combo.currentText() or "目录为空" in self.model_combo.currentText(): QMessageBox.warning(self, "警告", "请选择模型！"); return
        self.subtitles.clear(); self.subtitle_table.setRowCount(0); self.transcribe_btn.setEnabled(False); self.open_btn.setEnabled(False); self.status_bar.showMessage("转写中..."); model_path = str(config.MODELS_DIR / self.model_combo.currentText()); device = self.device_combo.currentText(); whisper_params = {k: v for k, v in config.SETTINGS.items() if k in ["beam_size", "vad_min_silence_ms", "language", "word_timestamps", "initial_prompt"]}; self.transcription_worker = TranscriptionWorker(self.media_path, model_path, device, whisper_params, self); self.transcription_worker.segment_ready.connect(self.add_subtitle_segment); self.transcription_worker.finished.connect(self.on_transcription_finished); self.transcription_worker.error.connect(self.show_critical_error); self.transcription_worker.start()
    
    def on_transcription_finished(self, srt_path): 
        self.srt_path = srt_path; self.transcribe_btn.setEnabled(True); self.open_btn.setEnabled(True); self.status_bar.showMessage(f"转写完成！", 10000); QMessageBox.information(self, "成功", f"转写完成！\n字幕已存至: {srt_path}"); self.audio_canvas.update_all_regions(self.subtitles)
        self.transcription_worker = None # 任务完成后，释放对worker的引用

    def on_retranscription_finished(self, new_text, row_index):
        if 0 <= row_index < len(self.subtitles): self.subtitles[row_index]['text'] = new_text; self.populate_table(); self.subtitle_table.selectRow(row_index); self.status_bar.showMessage(f"第 {self.subtitles[row_index]['index']} 行更新完毕。", 5000)
        if self.active_dialog and self.active_dialog.row_index == row_index: self.active_dialog.on_retranscribe_finished(new_text)
        self.retranscribe_worker = None # 任务完成后，释放对worker的引用

    def on_spectrogram_region_updated(self, row_index, start_sec, end_sec):
        if row_index < len(self.subtitles): self.subtitles[row_index].update({'start_sec': start_sec, 'end_sec': end_sec, 'start_time': format_time(start_sec), 'end_time': format_time(end_sec)}); self.subtitle_table.item(row_index, 1).setText(format_time(start_sec)); self.subtitle_table.item(row_index, 2).setText(format_time(end_sec))
    def show_critical_error(self, message): QMessageBox.critical(self, "后台进程错误", message); self.transcribe_btn.setEnabled(True); self.open_btn.setEnabled(True); self.status_bar.clearMessage()
    def populate_model_combo(self):
        self.model_combo.clear()
        try:
            model_folders = [d.name for d in config.MODELS_DIR.iterdir() if d.is_dir()]
            if model_folders: self.model_combo.addItems(sorted(model_folders))
            else: self.model_combo.addItem("模型目录为空")
        except Exception as e: QMessageBox.critical(self, "错误", f"读取模型文件夹失败: {e}")
    def load_whisper_model(self):
        if self.model: QMessageBox.information(self, "提示", "模型已加载。"); return
        model_folder_name = self.model_combo.currentText()
        if not model_folder_name or "目录为空" in model_folder_name: QMessageBox.warning(self, "警告", "请选择有效的模型！"); return
        self.load_model_btn.setEnabled(False); self.unload_model_btn.setEnabled(False)
        self.status_bar.showMessage("正在加载模型..."); QApplication.processEvents()
        model_path = str(config.MODELS_DIR / model_folder_name); device = self.device_combo.currentText(); compute_type = "float16" if device == "cuda" else "int8"
        try: 
            self.model = WhisperModel(model_path, device=device, compute_type=compute_type)
            self.status_bar.showMessage("模型加载成功！", 5000)
            self.unload_model_btn.setEnabled(True)
        except Exception as e: 
            QMessageBox.critical(self, "错误", f"加载模型失败: {e}"); self.model = None
            self.load_model_btn.setEnabled(True)
    def unload_whisper_model(self):
        if self.model:
            self.load_model_btn.setEnabled(False); self.unload_model_btn.setEnabled(False)
            self.status_bar.showMessage("正在卸载模型..."); QApplication.processEvents()
            del self.model; self.model = None
            gc.collect()
            if torch and torch.cuda.is_available(): torch.cuda.empty_cache()
            self.status_bar.showMessage("模型已卸载。", 5000)
            self.load_model_btn.setEnabled(True)
    def retranscribe_segment(self, row_index, start_sec=None, end_sec=None):
        if self.retranscribe_worker and self.retranscribe_worker.isRunning():
            QMessageBox.warning(self, "请稍候", "另一次重新转写任务正在进行中。")
            return
        if not self.model: QMessageBox.warning(self, "警告", "请先加载模型。"); return
        if not (0 <= row_index < len(self.subtitles)): return
        sub = self.subtitles[row_index]; start = start_sec if start_sec is not None else sub['start_sec']; end = end_sec if end_sec is not None else sub['end_sec']; self.status_bar.showMessage(f"正在重新识别第 {sub['index']} 行...")
        whisper_params = {k: v for k, v in config.SETTINGS.items() if k in ["beam_size", "initial_prompt"]}; self.retranscribe_worker = RetranscribeWorker(self.media_path, self.model, start, end, row_index, whisper_params, self); self.retranscribe_worker.finished.connect(self.on_retranscription_finished); self.retranscribe_worker.error.connect(self.show_critical_error); self.retranscribe_worker.start()
    def set_icons(self):
        style = self.style(); self.open_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)); self.import_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileLinkIcon)); self.play_pause_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay)); self.stop_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaStop)); self.save_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)); self.transcribe_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)); self.refresh_models_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload)); self.load_model_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)); self.unload_model_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton)); self.settings_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)); self.update_cache_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon)); self.translate_all_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_CommandLink))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    config.setup_environment()
    if not Path(config.FFMPEG_PATH).is_file(): QMessageBox.critical(None, "依赖缺失", f"错误：找不到 ffmpeg.exe！\n请在'设置'中配置正确路径: {config.FFMPEG_PATH}")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())