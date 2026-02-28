# widgets.py
# 包含自定义的 PyQt6 控件

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QFormLayout, QFileDialog,
                             QTextEdit, QDialogButtonBox, QLabel, QPushButton, QMessageBox, QSpinBox, 
                             QWidget, QCheckBox, QComboBox, QInputDialog, QTabWidget)
from PyQt6.QtCore import pyqtSignal, QThread

try: import openai
except ImportError: openai = None

from utils import format_time, parse_time

LANGUAGES = { "auto": "自动检测", "en": "英语", "zh": "中文", "de": "德语", "es": "西班牙语", "ru": "俄语", "ko": "韩语", "fr": "法语", "ja": "日语", "pt": "葡萄牙语", "tr": "土耳其语", "pl": "波兰语", "ca": "加泰罗尼亚语", "nl": "荷兰语", "ar": "阿拉伯语", "sv": "瑞典语", "it": "意大利语", "id": "印度尼西亚语", "hi": "印地语", "fi": "芬兰语", "vi": "越南语", "he": "希伯来语", "uk": "乌克兰语", "el": "希腊语", "ms": "马来语", "cs": "捷克语", "ro": "罗马尼亚语", "da": "丹麦语", "hu": "匈牙利语", "ta": "泰米尔语", "no": "挪威语", "th": "泰语", "ur": "乌尔都语", "hr": "克罗地亚语", "bg": "保加利亚语", "lt": "立陶宛语", "la": "拉丁语", "mi": "毛利语", "ml": "马拉雅拉姆语", "cy": "威尔士语", "sk": "斯洛伐克语", "te": "泰卢固语", "pa": "旁遮普语", "lv": "拉脱维亚语", "as": "阿萨姆语", "sr": "塞尔维亚语", "az": "阿塞拜疆语", "gl": "加利西亚语", "sl": "斯洛文尼亚语", "kn": "卡纳达语", "et": "爱沙尼亚语", "mk": "马其顿语", "br": "布列塔尼语", "eu": "巴斯克语", "is": "冰岛语", "hy": "亚美尼亚语", "ne": "尼泊尔语", "mn": "蒙古语", "bs": "波斯尼亚语", "kk": "哈萨克语", "sq": "阿尔巴尼亚语", "sw": "斯瓦希里语", "gu": "古吉拉特语", "mr": "马拉地语", "ka": "格鲁吉亚语", "be": "白俄罗斯语", "tg": "塔吉克语", "si": "僧伽罗语", "km": "高棉语", "sn": "绍纳语", "yo": "约鲁巴语", "so": "索马里语", "af": "南非语", "oc": "奥克语", "sd": "信德语", "am": "阿姆哈拉语", "yi": "意第绪语", "lo": "老挝语", "uz": "乌兹别克语", "fo": "法罗语", "ht": "海地克里奥尔语", "ps": "普什图语", "tk": "土库曼语", "nn": "新挪威语", "mt": "马耳他语", "sa": "梵语", "lb": "卢森堡语", "my": "缅甸语", "bo": "藏语", "tl": "他加禄语", "mg": "马尔加什语", "bn": "孟加拉语", "jw": "爪哇语", "su": "巽他语"}

class ModelListWorker(QThread):
    finished = pyqtSignal(list); error = pyqtSignal(str)
    def __init__(self, api_base, api_key):
        super().__init__(); self.api_base = api_base; self.api_key = api_key if api_key else "no-key-required"
    def run(self):
        if not openai: self.error.emit("OpenAI 库未安装 (pip install openai)"); return
        try:
            client = openai.OpenAI(api_key=self.api_key, base_url=self.api_base); models = client.models.list()
            model_ids = sorted([model.id for model in models.data]); self.finished.emit(model_ids)
        except Exception as e: self.error.emit(f"获取模型列表失败: {e}")

class SettingsDialog(QDialog):
    def __init__(self, current_settings, parent=None):
        super().__init__(parent); self.setWindowTitle("设置"); self.setMinimumWidth(600); self.settings = current_settings.copy(); self.layout = QVBoxLayout(self); form_layout = QFormLayout()
        form_layout.addRow(QLabel("<b>--- 路径设置 ---</b>"))
        self.vlc_path_edit = QLineEdit(self.settings.get("vlc_path", "")); self.ffmpeg_path_edit = QLineEdit(self.settings.get("ffmpeg_path", "")); self.models_dir_edit = QLineEdit(self.settings.get("models_dir", ""))
        form_layout.addRow("VLC 路径:", self.create_path_widget(self.vlc_path_edit, is_dir=True)); form_layout.addRow("FFmpeg 路径:", self.create_path_widget(self.ffmpeg_path_edit, is_file=True)); form_layout.addRow("模型目录:", self.create_path_widget(self.models_dir_edit, is_dir=True))
        form_layout.addRow(QLabel("<b>--- Whisper 转写参数 ---</b>"))
        self.language_combo = QComboBox(); self.language_combo.setToolTip("选择音频的语言。'自动检测'能识别语言，但指定语言可以提高准确性。")
        for code, name in LANGUAGES.items(): self.language_combo.addItem(f"{name} ({code})", code)
        current_lang = self.settings.get("language", "auto");
        if (lang_index := self.language_combo.findData(current_lang)) != -1: self.language_combo.setCurrentIndex(lang_index)
        form_layout.addRow("识别语言:", self.language_combo)
        self.initial_prompt_edit = QLineEdit(self.settings.get("initial_prompt", "")); self.initial_prompt_edit.setToolTip("可选的初始提示，可以引导模型纠正特定单词或风格。\n例如：'字幕应使用简体中文。Zoe, Kärcher, octorara'"); form_layout.addRow("初始提示(Prompt):", self.initial_prompt_edit)
        self.beam_size_spin = QSpinBox(); self.beam_size_spin.setRange(1, 20); self.beam_size_spin.setValue(self.settings.get("beam_size", 5)); self.beam_size_spin.setToolTip("用于解码的束搜索大小。更高的值可能更准确但更慢。"); form_layout.addRow("Beam Size:", self.beam_size_spin)
        self.vad_min_silence_spin = QSpinBox(); self.vad_min_silence_spin.setRange(100, 2000); self.vad_min_silence_spin.setSingleStep(50); self.vad_min_silence_spin.setValue(self.settings.get("vad_min_silence_ms", 500)); self.vad_min_silence_spin.setToolTip("语音活动检测(VAD)的最小静音持续时间（毫秒）。\n用于在长段静音处断句。"); form_layout.addRow("VAD 最小静音(ms):", self.vad_min_silence_spin)
        self.word_ts_check = QCheckBox(); self.word_ts_check.setChecked(self.settings.get("word_timestamps", False)); self.word_ts_check.setToolTip("生成单词级别的时间戳。这会显著增加处理时间。"); form_layout.addRow("启用单词级时间戳:", self.word_ts_check)
        
        form_layout.addRow(QLabel("<b>--- 翻译设置 (OpenAI API) ---</b>"))
        self.api_base_edit = QLineEdit(self.settings.get("openai_api_base", "")); self.api_base_edit.setToolTip("您的API地址，例如 https://api.openai.com/v1 或本地模型的 http://localhost:1234/v1"); form_layout.addRow("API Base URL:", self.api_base_edit)
        self.api_key_edit = QLineEdit(self.settings.get("openai_api_key", "")); self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password); self.api_key_edit.setToolTip("您的API密钥 (本地模型可留空)"); form_layout.addRow("API Key:", self.api_key_edit)
        model_layout = QHBoxLayout(); self.model_combo = QComboBox(); self.model_combo.setToolTip("选择用于翻译的AI模型"); self.model_combo.addItem(self.settings.get("openai_model", "")); self.refresh_models_btn = QPushButton("刷新"); self.refresh_models_btn.clicked.connect(self.refresh_models); model_layout.addWidget(self.model_combo, 1); model_layout.addWidget(self.refresh_models_btn); form_layout.addRow("模型:", model_layout)
        # <<< 新增：上下文行数设置 >>>
        self.context_lines_spin = QSpinBox(); self.context_lines_spin.setRange(0, 10); self.context_lines_spin.setValue(self.settings.get("translation_context_lines", 3)); self.context_lines_spin.setToolTip("进行上下文翻译时，向前参考的字幕行数。"); form_layout.addRow("上下文参考行数:", self.context_lines_spin)

        self.layout.addLayout(form_layout)
        # <<< 新增：使用 QTabWidget 管理提示词 >>>
        self.tabs = QTabWidget(); self.layout.addWidget(self.tabs)
        self.standard_prompt_tab = self.create_prompt_tab("standard")
        self.context_prompt_tab = self.create_prompt_tab("contextual")
        self.tabs.addTab(self.standard_prompt_tab, "标准翻译提示词")
        self.tabs.addTab(self.context_prompt_tab, "上下文翻译提示词")
        self.populate_prompts()
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel); button_box.accepted.connect(self.accept); button_box.rejected.connect(self.reject); self.layout.addWidget(button_box)

    def create_prompt_tab(self, prompt_type):
        widget = QWidget(); layout = QVBoxLayout(widget); form_layout = QFormLayout()
        prompt_layout = QHBoxLayout()
        combo = QComboBox(); combo.currentIndexChanged.connect(lambda: self.on_prompt_selected(prompt_type))
        save_btn = QPushButton("保存"); save_btn.clicked.connect(lambda: self.save_prompt(prompt_type))
        delete_btn = QPushButton("删除"); delete_btn.clicked.connect(lambda: self.delete_prompt(prompt_type))
        prompt_layout.addWidget(combo, 1); prompt_layout.addWidget(save_btn); prompt_layout.addWidget(delete_btn)
        form_layout.addRow("预设:", prompt_layout)
        text_edit = QTextEdit(); text_edit.setMinimumHeight(120)
        form_layout.addRow(text_edit)
        layout.addLayout(form_layout)
        # 存储控件引用
        setattr(self, f"{prompt_type}_prompt_combo", combo)
        setattr(self, f"{prompt_type}_prompt_edit", text_edit)
        return widget

    def populate_prompts(self):
        self.populate_single_prompt_type("standard")
        self.populate_single_prompt_type("contextual")
    def populate_single_prompt_type(self, p_type):
        combo = getattr(self, f"{p_type}_prompt_combo")
        text_edit = getattr(self, f"{p_type}_prompt_edit")
        combo.clear(); prompts = self.settings.get("translation_prompts", {}).get(p_type, {})
        if prompts: combo.addItems(prompts.keys())
        active_prompt = self.settings.get(f"active_{p_type}_prompt_name")
        if active_prompt in prompts: combo.setCurrentText(active_prompt); text_edit.setText(prompts[active_prompt])
        else: text_edit.clear()

    def on_prompt_selected(self, p_type):
        combo = getattr(self, f"{p_type}_prompt_combo"); text_edit = getattr(self, f"{p_type}_prompt_edit")
        prompt_name = combo.currentText(); prompts = self.settings.get("translation_prompts", {}).get(p_type, {})
        if prompt_name in prompts: text_edit.setText(prompts[prompt_name])
    
    def save_prompt(self, p_type):
        combo = getattr(self, f"{p_type}_prompt_combo"); text_edit = getattr(self, f"{p_type}_prompt_edit")
        prompt_name, ok = QInputDialog.getText(self, "保存提示词", "输入预设名称:")
        if ok and prompt_name:
            prompts = self.settings.get("translation_prompts", {}).get(p_type, {})
            prompts[prompt_name] = text_edit.toPlainText(); self.settings["translation_prompts"][p_type] = prompts
            self.settings[f"active_{p_type}_prompt_name"] = prompt_name; self.populate_single_prompt_type(p_type)

    def delete_prompt(self, p_type):
        combo = getattr(self, f"{p_type}_prompt_combo")
        prompt_name = combo.currentText();
        if not prompt_name: return
        prompts = self.settings.get("translation_prompts", {}).get(p_type, {})
        if len(prompts) <= 1: QMessageBox.warning(self, "操作失败", "不能删除最后一个提示词预设。"); return
        reply = QMessageBox.question(self, "确认删除", f"确定要删除预设 '{prompt_name}' 吗？")
        if reply == QMessageBox.StandardButton.Yes:
            del prompts[prompt_name]; self.settings["translation_prompts"][p_type] = prompts
            self.settings[f"active_{p_type}_prompt_name"] = list(prompts.keys())[0]; self.populate_single_prompt_type(p_type)

    def get_settings(self):
        self.settings.update({
            "vlc_path": self.vlc_path_edit.text(), "ffmpeg_path": self.ffmpeg_path_edit.text(), "models_dir": self.models_dir_edit.text(),
            "beam_size": self.beam_size_spin.value(), "vad_min_silence_ms": self.vad_min_silence_spin.value(), "language": self.language_combo.currentData(),
            "word_timestamps": self.word_ts_check.isChecked(), "initial_prompt": self.initial_prompt_edit.text(),
            "openai_api_base": self.api_base_edit.text(), "openai_api_key": self.api_key_edit.text(), "openai_model": self.model_combo.currentText(),
            "translation_context_lines": self.context_lines_spin.value(),
            "active_standard_prompt_name": self.standard_prompt_combo.currentText(),
            "active_contextual_prompt_name": self.contextual_prompt_combo.currentText()
        })
        return self.settings

    # --- 其他辅助函数保持不变 ---
    def refresh_models(self):
        api_base = self.api_base_edit.text()
        if not api_base: QMessageBox.warning(self, "信息不完整", "请输入API Base URL。"); return
        api_key = self.api_key_edit.text(); self.refresh_models_btn.setText("刷新中..."); self.refresh_models_btn.setEnabled(False)
        self.model_worker = ModelListWorker(api_base, api_key); self.model_worker.finished.connect(self.on_models_refreshed); self.model_worker.error.connect(self.on_models_error); self.model_worker.start()
    def on_models_refreshed(self, model_ids):
        self.refresh_models_btn.setText("刷新"); self.refresh_models_btn.setEnabled(True); current_model = self.model_combo.currentText(); self.model_combo.clear(); self.model_combo.addItems(model_ids)
        if current_model in model_ids: self.model_combo.setCurrentText(current_model)
        QMessageBox.information(self, "成功", f"成功获取 {len(model_ids)} 个模型。")
    def on_models_error(self, error_msg):
        self.refresh_models_btn.setText("刷新"); self.refresh_models_btn.setEnabled(True); QMessageBox.critical(self, "错误", error_msg)
    def create_path_widget(self, line_edit, is_dir=False, is_file=False):
        widget = QWidget(); layout = QHBoxLayout(widget); layout.setContentsMargins(0, 0, 0, 0); layout.addWidget(line_edit); browse_btn = QPushButton("浏览..."); layout.addWidget(browse_btn)
        if is_dir: browse_btn.clicked.connect(lambda: self.get_directory(line_edit))
        elif is_file: browse_btn.clicked.connect(lambda: self.get_file(line_edit))
        return widget
    def get_directory(self, line_edit):
        path = QFileDialog.getExistingDirectory(self, "选择目录", line_edit.text());
        if path: line_edit.setText(path)
    def get_file(self, line_edit):
        path, _ = QFileDialog.getOpenFileName(self, "选择文件", line_edit.text());
        if path: line_edit.setText(path)

# --- AudioVisualizer 和 EditDialog 保持原样 ---
class AudioVisualizer(pg.PlotWidget):
    region_updated = pyqtSignal(int, float, float)
    def __init__(self, parent=None):
        super().__init__(parent); self.setBackground('k'); self.regions = []; self.slider_value = 50; opts = {'autoDownsample': True, 'clipToView': True, 'downsampleMethod': 'peak'}; self.min_curve = pg.PlotCurveItem(pen=pg.mkPen(color=(76, 175, 80, 100)), **opts); self.max_curve = pg.PlotCurveItem(pen=pg.mkPen(color=(76, 175, 80, 100)), **opts); self.rms_curve = pg.PlotCurveItem(pen=pg.mkPen(color=(165, 214, 167, 200), width=2), **opts); self.fill_item = pg.FillBetweenItem(self.min_curve, self.max_curve, brush=pg.mkBrush(76, 175, 80, 50)); self.addItem(self.fill_item); self.addItem(self.min_curve); self.addItem(self.max_curve); self.addItem(self.rms_curve); self.playhead = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('cyan', width=2)); self.playhead.setVisible(False); self.addItem(self.playhead); self.getViewBox().setMouseEnabled(y=False); self.getAxis('left').setLabel('Amplitude')
    def plot_data(self, duration, waveform_data):
        time_axis, min_vals, max_vals, rms_vals = waveform_data; self.min_curve.setData(time_axis, min_vals); self.max_curve.setData(time_axis, max_vals); self.rms_curve.setData(time_axis, rms_vals); self.setLimits(xMin=0, xMax=duration); self.playhead.setPos(0); self.playhead.setVisible(True); self._update_y_axis_zoom()
    def set_height_multiplier(self, value):
        self.slider_value = value; self._update_y_axis_zoom()
    def _update_y_axis_zoom(self):
        y_limit = 10 ** ((50 - self.slider_value) / 50.0); self.setYRange(-y_limit, y_limit, padding=0.05)
    def update_all_regions(self, subtitles):
        for region in self.regions: self.removeItem(region)
        self.regions.clear()
        for i, sub in enumerate(subtitles):
            region = pg.LinearRegionItem(values=[sub['start_sec'], sub['end_sec']], orientation='vertical', brush=(255, 255, 255, 50), movable=True); region.row_index = i; region.sigRegionChangeFinished.connect(self.on_region_changed); self.addItem(region); self.regions.append(region)
    def on_region_changed(self, region):
        start_sec, end_sec = region.getRegion(); self.region_updated.emit(region.row_index, start_sec, end_sec)
    def focus_on_region(self, row_index):
        if 0 <= row_index < len(self.regions):
            region = self.regions[row_index]; start_sec, end_sec = region.getRegion(); duration = end_sec - start_sec; padding = max(duration * 1.5, 2.0); self.getViewBox().setXRange(max(0, start_sec - padding), end_sec + padding, padding=0.05)
    def update_playhead_position(self, seconds):
        if self.playhead.isVisible(): self.playhead.setPos(seconds)
class EditDialog(QDialog):
    def __init__(self, subtitle_data, row_index, parent=None):
        super().__init__(parent); self.setWindowTitle("编辑字幕"); self.subtitle_data = subtitle_data; self.row_index = row_index; self.layout = QVBoxLayout(self)
        time_layout = QHBoxLayout(); self.start_time_edit = QLineEdit(format_time(self.subtitle_data['start_sec'])); self.end_time_edit = QLineEdit(format_time(self.subtitle_data['end_sec'])); time_layout.addWidget(QLabel("开始时间:")); time_layout.addWidget(self.start_time_edit); time_layout.addWidget(QLabel("-->")); time_layout.addWidget(QLabel("结束时间:")); time_layout.addWidget(self.end_time_edit); self.layout.addLayout(time_layout)
        text_form_layout = QFormLayout(); self.original_text_edit = QTextEdit(self.subtitle_data['text']); self.translated_text_edit = QTextEdit(self.subtitle_data.get('translation', '')); text_form_layout.addRow("原文:", self.original_text_edit); text_form_layout.addRow("译文:", self.translated_text_edit); self.layout.addLayout(text_form_layout)
        action_layout = QHBoxLayout(); self.play_segment_btn = QPushButton("预览片段"); self.play_segment_btn.clicked.connect(self.preview_segment); self.retranscribe_btn = QPushButton("重新识别原文"); self.retranscribe_btn.clicked.connect(self.retranscribe_segment); action_layout.addWidget(self.play_segment_btn); action_layout.addWidget(self.retranscribe_btn); self.layout.addLayout(action_layout)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel); button_box.accepted.connect(self.accept); button_box.rejected.connect(self.reject); self.layout.addWidget(button_box)
    def retranscribe_segment(self):
        start_sec = parse_time(self.start_time_edit.text()); end_sec = parse_time(self.end_time_edit.text())
        if end_sec <= start_sec: QMessageBox.warning(self, "错误", "结束时间必须大于开始时间。"); return
        self.retranscribe_btn.setText("识别中..."); self.retranscribe_btn.setEnabled(False); self.parent().retranscribe_segment(self.row_index, start_sec, end_sec)
    def on_retranscribe_finished(self, new_text):
        if new_text is not None: self.original_text_edit.setText(new_text)
        self.retranscribe_btn.setText("重新识别原文"); self.retranscribe_btn.setEnabled(True)
    def preview_segment(self):
        start_ms = int(parse_time(self.start_time_edit.text()) * 1000); self.parent().player.play(); self.parent().player.set_time(start_ms)
    def get_data(self):
        return {'index': self.subtitle_data['index'], 'start_sec': parse_time(self.start_time_edit.text()), 'end_sec': parse_time(self.end_time_edit.text()), 'text': self.original_text_edit.toPlainText().strip(), 'translation': self.translated_text_edit.toPlainText().strip()}