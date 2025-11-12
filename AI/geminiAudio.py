import sys
import os
import json
import time
import traceback
import base64
import requests
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import re

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog,
    QTabWidget, QTableWidget, QTableWidgetItem, QSpinBox,
    QComboBox, QMessageBox, QProgressBar, QGroupBox,
    QSplitter, QHeaderView, QMenu, QMenuBar, QStatusBar,
    QListWidget, QListWidgetItem, QCheckBox, QTextBrowser
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot, QTimer
from PyQt6.QtGui import QAction, QFont, QColor

@dataclass
class ProjectConfig:
    """项目配置数据类"""
    api_keys: List[str]
    input_folder: str
    output_folder: str
    selected_model: str
    thread_count: int
    system_prompt: str
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        return cls(**data)

class APIKeyManager:
    """API密钥管理器"""
    def __init__(self, keys: List[str]):
        self.keys = keys if keys else []
        self.current_index = 0
        self.lock = Lock()
    
    def get_next_key(self) -> Optional[str]:
        """获取下一个可用的API密钥"""
        with self.lock:
            if not self.keys:
                return None
            key = self.keys[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.keys)
            return key
    
    def update_keys(self, keys: List[str]):
        """更新API密钥列表"""
        with self.lock:
            self.keys = keys
            self.current_index = 0

class GeminiAPIClient:
    """Gemini API 客户端"""
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    
    @staticmethod
    def list_models(api_key: str) -> List[str]:
        """获取可用模型列表"""
        try:
            url = f"{GeminiAPIClient.BASE_URL}/models?key={api_key}"
            response = requests.get(url)
            response.raise_for_status()
            
            models = []
            data = response.json()
            
            for model in data.get('models', []):
                model_name = model.get('name', '').replace('models/', '')
                # 检查是否支持音频
                if 'generateContent' in model.get('supportedGenerationMethods', []):
                    models.append(model_name)
            
            return models
        except Exception as e:
            raise Exception(f"获取模型列表失败: {str(e)}")
    
    @staticmethod
    def generate_content(api_key: str, model: str, system_prompt: str, 
                        user_message: str, audio_data: bytes, 
                        mime_type: str) -> str:
        """发送生成内容请求"""
        try:
            # 构建URL
            url = f"{GeminiAPIClient.BASE_URL}/models/{model}:generateContent?key={api_key}"
            
            # 将音频数据转换为base64
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            # 构建请求体
            request_body = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": f"{system_prompt}\n\n{user_message}"
                            },
                            {
                                "inlineData": {
                                    "mimeType": mime_type,
                                    "data": audio_base64
                                }
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "topP": 0.95,
                    "topK": 40,
                    "maxOutputTokens": 8192,
                }
            }
            
            # 发送请求
            headers = {
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=request_body, headers=headers, timeout=120)
            response.raise_for_status()
            
            # 解析响应
            data = response.json()
            
            # 提取生成的文本
            if 'candidates' in data and len(data['candidates']) > 0:
                candidate = data['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content']:
                    parts = candidate['content']['parts']
                    if len(parts) > 0 and 'text' in parts[0]:
                        return parts[0]['text']
            
            return ""
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"API请求失败: {str(e)}")
        except Exception as e:
            raise Exception(f"处理失败: {str(e)}")

class AudioProcessWorker(QThread):
    """音频处理工作线程"""
    progress = pyqtSignal(str)  # 进度信息
    finished = pyqtSignal(dict)  # 完成信号
    error = pyqtSignal(str)  # 错误信号
    file_processed = pyqtSignal(str, bool, str)  # 文件处理完成信号(文件名, 成功, 消息)
    
    def __init__(self, config: ProjectConfig, api_manager: APIKeyManager):
        super().__init__()
        self.config = config
        self.api_manager = api_manager
        self.is_running = True
        self.processed_count = 0
        self.total_count = 0
        self.success_count = 0
        
    def run(self):
        """运行音频处理任务"""
        try:
            # 获取所有音频文件
            audio_files = self.get_audio_files()
            self.total_count = len(audio_files)
            
            if not audio_files:
                self.progress.emit("没有找到需要处理的音频文件")
                return
            
            self.progress.emit(f"找到 {len(audio_files)} 个音频文件需要处理")
            
            # 使用线程池处理文件
            with ThreadPoolExecutor(max_workers=self.config.thread_count) as executor:
                futures = {
                    executor.submit(self.process_single_file, file_path): file_path
                    for file_path in audio_files
                }
                
                for future in as_completed(futures):
                    if not self.is_running:
                        executor.shutdown(wait=False)
                        break
                    
                    file_path = futures[future]
                    try:
                        success, message = future.result()
                        self.processed_count += 1
                        if success:
                            self.success_count += 1
                        self.file_processed.emit(file_path.name, success, message)
                        self.progress.emit(
                            f"进度: {self.processed_count}/{self.total_count} - "
                            f"{'成功' if success else '失败'}: {file_path.name}"
                        )
                    except Exception as e:
                        self.processed_count += 1
                        error_msg = f"处理文件出错 {file_path.name}: {str(e)}"
                        self.error.emit(error_msg)
                        self.file_processed.emit(file_path.name, False, str(e))
            
            self.finished.emit({
                'total': self.total_count,
                'processed': self.processed_count,
                'success': self.success_count
            })
            
        except Exception as e:
            self.error.emit(f"处理过程出错: {str(e)}\n{traceback.format_exc()}")
    
    def get_audio_files(self) -> List[Path]:
        """获取需要处理的音频文件"""
        input_path = Path(self.config.input_folder)
        output_path = Path(self.config.output_folder)
        
        if not input_path.exists():
            return []
        
        # 支持的音频格式
        audio_extensions = {'.mp3', '.wav', '.m4a', '.flac', '.aac', '.ogg', '.opus', '.webm'}
        audio_files = []
        
        for file_path in input_path.iterdir():
            if file_path.suffix.lower() in audio_extensions:
                # 检查是否已经处理过
                base_name = file_path.stem
                zh_file = output_path / f"{base_name}_zh.txt"
                jp_file = output_path / f"{base_name}_jp.txt"
                
                # 如果两个文件都不存在，则需要处理
                if not (zh_file.exists() and jp_file.exists()):
                    audio_files.append(file_path)
        
        return audio_files
    
    def get_mime_type(self, file_path: Path) -> str:
        """获取文件的MIME类型"""
        extension_map = {
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.m4a': 'audio/mp4',
            '.flac': 'audio/flac',
            '.aac': 'audio/aac',
            '.ogg': 'audio/ogg',
            '.opus': 'audio/opus',
            '.webm': 'audio/webm'
        }
        return extension_map.get(file_path.suffix.lower(), 'audio/mpeg')
    
    def process_single_file(self, file_path: Path) -> Tuple[bool, str]:
        """处理单个音频文件"""
        try:
            # 获取API密钥
            api_key = self.api_manager.get_next_key()
            if not api_key:
                return False, "没有可用的API密钥"
            
            # 读取音频文件
            with open(file_path, 'rb') as f:
                audio_data = f.read()
            
            # 获取MIME类型
            mime_type = self.get_mime_type(file_path)
            
            # 构建系统提示词和用户消息
            system_prompt = self.config.system_prompt
            user_message = "请你开始解析这个音频"
            
            # 发送API请求
            response_text = GeminiAPIClient.generate_content(
                api_key=api_key,
                model=self.config.selected_model,
                system_prompt=system_prompt,
                user_message=user_message,
                audio_data=audio_data,
                mime_type=mime_type
            )
            
            # 解析响应
            jp_text, cn_text = self.parse_response(response_text)
            
            if not jp_text and not cn_text:
                return False, "未能从响应中提取有效文本"
            
            # 保存结果
            output_path = Path(self.config.output_folder)
            output_path.mkdir(parents=True, exist_ok=True)
            
            base_name = file_path.stem
            
            # 保存日文文本
            if jp_text:
                jp_file = output_path / f"{base_name}_jp.txt"
                with open(jp_file, 'w', encoding='utf-8') as f:
                    f.write(jp_text)
            
            # 保存中文文本
            if cn_text:
                zh_file = output_path / f"{base_name}_zh.txt"
                with open(zh_file, 'w', encoding='utf-8') as f:
                    f.write(cn_text)
            
            return True, f"成功处理"
            
        except Exception as e:
            return False, f"处理失败: {str(e)}"
    
    def parse_response(self, text: str) -> Tuple[str, str]:
        """解析API响应，提取日文和中文文本"""
        if not text:
            return "", ""
        
        # 提取日文文本
        jp_pattern = r'<jpText>(.*?)</jpText>'
        jp_matches = re.findall(jp_pattern, text, re.DOTALL | re.IGNORECASE)
        jp_text = '\n'.join(jp_matches) if jp_matches else ""
        
        # 提取中文文本  
        cn_pattern = r'<cnText>(.*?)</cnText>'
        cn_matches = re.findall(cn_pattern, text, re.DOTALL | re.IGNORECASE)
        cn_text = '\n'.join(cn_matches) if cn_matches else ""
        
        # 如果没有找到标签格式，尝试其他解析方式
        if not jp_text and not cn_text:
            # 尝试查找日文和中文内容
            lines = text.split('\n')
            jp_lines = []
            cn_lines = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 简单判断是否包含日文字符
                if any('\u3040' <= char <= '\u309f' or '\u30a0' <= char <= '\u30ff' 
                       or '\u4e00' <= char <= '\u9fff' for char in line):
                    # 如果是纯中文（没有假名），归类为中文
                    if not any('\u3040' <= char <= '\u309f' or '\u30a0' <= char <= '\u30ff' 
                              for char in line):
                        cn_lines.append(line)
                    else:
                        jp_lines.append(line)
            
            jp_text = '\n'.join(jp_lines)
            cn_text = '\n'.join(cn_lines)
        
        return jp_text.strip(), cn_text.strip()
    
    def stop(self):
        """停止处理"""
        self.is_running = False

class ModelFetchWorker(QThread):
    """模型获取工作线程"""
    models_fetched = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key
    
    def run(self):
        """获取可用模型列表"""
        try:
            models = GeminiAPIClient.list_models(self.api_key)
            self.models_fetched.emit(models)
        except Exception as e:
            self.error.emit(str(e))

class AudioLabelingApp(QMainWindow):
    """音频打标主应用程序"""
    
    def __init__(self):
        super().__init__()
        self.current_project = None
        self.api_manager = APIKeyManager([])
        self.worker = None
        self.model_cache = []
        self.init_ui()
        
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("音频打标专业工具 v2.0")
        self.setGeometry(100, 100, 1400, 900)
        
        # 设置菜单栏
        self.setup_menu()
        
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 创建选项卡
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # 配置标签页
        self.setup_config_tab()
        
        # 预览标签页
        self.setup_preview_tab()
        
        # 日志标签页
        self.setup_log_tab()
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")
        
        # 进度栏
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
    
    def setup_menu(self):
        """设置菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        
        new_project_action = QAction("新建项目", self)
        new_project_action.setShortcut("Ctrl+N")
        new_project_action.triggered.connect(self.new_project)
        file_menu.addAction(new_project_action)
        
        open_project_action = QAction("打开项目", self)
        open_project_action.setShortcut("Ctrl+O")
        open_project_action.triggered.connect(self.open_project)
        file_menu.addAction(open_project_action)
        
        save_project_action = QAction("保存项目", self)
        save_project_action.setShortcut("Ctrl+S")
        save_project_action.triggered.connect(self.save_project)
        file_menu.addAction(save_project_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def setup_config_tab(self):
        """设置配置标签页"""
        config_widget = QWidget()
        self.tab_widget.addTab(config_widget, "配置")
        
        layout = QVBoxLayout(config_widget)
        
        # API配置组
        api_group = QGroupBox("API 配置")
        api_layout = QVBoxLayout()
        
        # API密钥输入
        api_key_label = QLabel("API 密钥 (每行一个，支持多个密钥轮询):")
        api_layout.addWidget(api_key_label)
        
        self.api_keys_text = QTextEdit()
        self.api_keys_text.setPlaceholderText("输入一个或多个API密钥，每行一个\n多个密钥将自动轮询使用")
        self.api_keys_text.setMaximumHeight(100)
        api_layout.addWidget(self.api_keys_text)
        
        # 模型选择
        model_layout = QHBoxLayout()
        model_label = QLabel("选择模型:")
        model_layout.addWidget(model_label)
        
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(300)
        self.model_combo.addItems([
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b", 
            "gemini-1.5-pro",
            "gemini-2.0-flash-exp"
        ])
        model_layout.addWidget(self.model_combo)
        
        self.refresh_models_btn = QPushButton("刷新模型列表")
        self.refresh_models_btn.clicked.connect(self.refresh_models)
        model_layout.addWidget(self.refresh_models_btn)
        
        model_layout.addStretch()
        api_layout.addLayout(model_layout)
        
        api_group.setLayout(api_layout)
        layout.addWidget(api_group)
        
        # 文件夹配置组
        folder_group = QGroupBox("文件夹配置")
        folder_layout = QVBoxLayout()
        
        # 输入文件夹
        input_layout = QHBoxLayout()
        input_label = QLabel("音频输入文件夹:")
        input_label.setMinimumWidth(100)
        input_layout.addWidget(input_label)
        
        self.input_folder_edit = QLineEdit()
        input_layout.addWidget(self.input_folder_edit)
        
        input_browse_btn = QPushButton("浏览...")
        input_browse_btn.clicked.connect(self.browse_input_folder)
        input_layout.addWidget(input_browse_btn)
        
        folder_layout.addLayout(input_layout)
        
        # 输出文件夹
        output_layout = QHBoxLayout()
        output_label = QLabel("文本输出文件夹:")
        output_label.setMinimumWidth(100)
        output_layout.addWidget(output_label)
        
        self.output_folder_edit = QLineEdit()
        output_layout.addWidget(self.output_folder_edit)
        
        output_browse_btn = QPushButton("浏览...")
        output_browse_btn.clicked.connect(self.browse_output_folder)
        output_layout.addWidget(output_browse_btn)
        
        folder_layout.addLayout(output_layout)
        
        folder_group.setLayout(folder_layout)
        layout.addWidget(folder_group)
        
        # 处理配置组
        process_group = QGroupBox("处理配置")
        process_layout = QVBoxLayout()
        
        # 线程数设置
        thread_layout = QHBoxLayout()
        thread_label = QLabel("并发线程数:")
        thread_layout.addWidget(thread_label)
        
        self.thread_spinbox = QSpinBox()
        self.thread_spinbox.setMinimum(1)
        self.thread_spinbox.setMaximum(100)
        self.thread_spinbox.setValue(20)
        self.thread_spinbox.setToolTip("设置同时处理的音频文件数量（1-100）")
        thread_layout.addWidget(self.thread_spinbox)
        
        thread_info = QLabel("(建议: 10-30，过高可能导致API限流)")
        thread_info.setStyleSheet("color: gray;")
        thread_layout.addWidget(thread_info)
        
        thread_layout.addStretch()
        process_layout.addLayout(thread_layout)
        
        # 系统提示词
        prompt_label = QLabel("系统提示词:")
        process_layout.addWidget(prompt_label)
        
        self.system_prompt_text = QTextEdit()
        self.system_prompt_text.setPlainText(
            "你是一个专业的同声传译专家，能够以专业的准确获取日语语言里的日语文本，"
            "同时准确的分析出里面的完整日语原文和对应的中文翻译。输出格式要求：\n"
            "1. 将日语原文放在<jpText></jpText>标签中\n"
            "2. 将翻译后的中文放在<cnText></cnText>标签中\n"
            "3. 请确保翻译准确、自然、符合中文表达习惯"
        )
        self.system_prompt_text.setMaximumHeight(120)
        process_layout.addWidget(self.system_prompt_text)
        
        process_group.setLayout(process_layout)
        layout.addWidget(process_group)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.start_btn = QPushButton("开始处理")
        self.start_btn.clicked.connect(self.start_processing)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("停止处理")
        self.stop_btn.clicked.connect(self.stop_processing)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        button_layout.addWidget(self.stop_btn)
        
        layout.addLayout(button_layout)
        layout.addStretch()
    
    def setup_preview_tab(self):
        """设置预览标签页"""
        preview_widget = QWidget()
        self.tab_widget.addTab(preview_widget, "预览与编辑")
        
        layout = QVBoxLayout(preview_widget)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self.refresh_preview)
        toolbar_layout.addWidget(refresh_btn)
        
        save_changes_btn = QPushButton("💾 保存修改")
        save_changes_btn.clicked.connect(self.save_preview_changes)
        toolbar_layout.addWidget(save_changes_btn)
        
        delete_btn = QPushButton("🗑️ 删除选中")
        delete_btn.clicked.connect(self.delete_selected)
        toolbar_layout.addWidget(delete_btn)
        
        toolbar_layout.addStretch()
        
        # 统计信息
        self.stats_label = QLabel("文件: 0 | 完成: 0 | 未完成: 0")
        toolbar_layout.addWidget(self.stats_label)
        
        layout.addLayout(toolbar_layout)
        
        # 表格
        self.preview_table = QTableWidget()
        self.preview_table.setColumnCount(4)
        self.preview_table.setHorizontalHeaderLabels(["文件名", "日文原文", "中文翻译", "状态"])
        
        # 设置列宽
        header = self.preview_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        # 启用选择
        self.preview_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        layout.addWidget(self.preview_table)
    
    def setup_log_tab(self):
        """设置日志标签页"""
        log_widget = QWidget()
        self.tab_widget.addTab(log_widget, "处理日志")
        
        layout = QVBoxLayout(log_widget)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        
        clear_log_btn = QPushButton("清空日志")
        clear_log_btn.clicked.connect(self.clear_log)
        toolbar_layout.addWidget(clear_log_btn)
        
        export_log_btn = QPushButton("导出日志")
        export_log_btn.clicked.connect(self.export_log)
        toolbar_layout.addWidget(export_log_btn)
        
        # 自动滚动选项
        self.auto_scroll_check = QCheckBox("自动滚动")
        self.auto_scroll_check.setChecked(True)
        toolbar_layout.addWidget(self.auto_scroll_check)
        
        toolbar_layout.addStretch()
        layout.addLayout(toolbar_layout)
        
        # 日志显示
        self.log_browser = QTextBrowser()
        self.log_browser.setFont(QFont("Consolas", 9))
        layout.addWidget(self.log_browser)
    
    def new_project(self):
        """创建新项目"""
        reply = QMessageBox.question(
            self, "新建项目", 
            "创建新项目将清空当前配置，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.current_project = None
            self.api_keys_text.clear()
            self.input_folder_edit.clear()
            self.output_folder_edit.clear()
            self.thread_spinbox.setValue(20)
            self.log_browser.clear()
            self.preview_table.setRowCount(0)
            self.add_log("创建新项目")
    
    def open_project(self):
        """打开项目"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开项目", "", "项目文件 (*.json)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                config = ProjectConfig.from_dict(data)
                
                # 恢复配置
                self.api_keys_text.setPlainText('\n'.join(config.api_keys))
                self.input_folder_edit.setText(config.input_folder)
                self.output_folder_edit.setText(config.output_folder)
                self.thread_spinbox.setValue(config.thread_count)
                self.system_prompt_text.setPlainText(config.system_prompt)
                
                # 设置模型
                index = self.model_combo.findText(config.selected_model)
                if index >= 0:
                    self.model_combo.setCurrentIndex(index)
                else:
                    self.model_combo.addItem(config.selected_model)
                    self.model_combo.setCurrentText(config.selected_model)
                
                self.current_project = file_path
                self.add_log(f"打开项目: {file_path}")
                
                # 刷新预览
                self.refresh_preview()
                
                QMessageBox.information(self, "成功", "项目加载成功")
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"打开项目失败: {str(e)}")
    
    def save_project(self):
        """保存项目"""
        if not self.current_project:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存项目", "audio_project.json", "项目文件 (*.json)"
            )
            if not file_path:
                return
            self.current_project = file_path
        
        try:
            config = ProjectConfig(
                api_keys=[key.strip() for key in self.api_keys_text.toPlainText().strip().split('\n') if key.strip()],
                input_folder=self.input_folder_edit.text(),
                output_folder=self.output_folder_edit.text(),
                selected_model=self.model_combo.currentText(),
                thread_count=self.thread_spinbox.value(),
                system_prompt=self.system_prompt_text.toPlainText()
            )
            
            with open(self.current_project, 'w', encoding='utf-8') as f:
                json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)
            
            self.add_log(f"项目已保存: {self.current_project}")
            QMessageBox.information(self, "成功", "项目保存成功")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存项目失败: {str(e)}")
    
    def browse_input_folder(self):
        """浏览输入文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择音频输入文件夹")
        if folder:
            self.input_folder_edit.setText(folder)
            self.add_log(f"设置输入文件夹: {folder}")
    
    def browse_output_folder(self):
        """浏览输出文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择文本输出文件夹")
        if folder:
            self.output_folder_edit.setText(folder)
            self.add_log(f"设置输出文件夹: {folder}")
    
    def refresh_models(self):
        """刷新模型列表"""
        api_keys = [key.strip() for key in self.api_keys_text.toPlainText().strip().split('\n') if key.strip()]
        
        if not api_keys:
            QMessageBox.warning(self, "警告", "请先输入API密钥")
            return
        
        self.refresh_models_btn.setEnabled(False)
        self.add_log("正在获取模型列表...")
        
        # 创建并启动模型获取线程
        self.model_worker = ModelFetchWorker(api_keys[0])
        self.model_worker.models_fetched.connect(self.on_models_fetched)
        self.model_worker.error.connect(self.on_model_fetch_error)
        self.model_worker.start()
    
    @pyqtSlot(list)
    def on_models_fetched(self, models):
        """模型获取完成"""
        self.model_cache = models
        current_model = self.model_combo.currentText()
        
        self.model_combo.clear()
        self.model_combo.addItems(models)
        
        # 尝试恢复之前的选择
        if current_model in models:
            self.model_combo.setCurrentText(current_model)
        else:
            # 优先选择flash模型
            for i, model in enumerate(models):
                if 'flash' in model.lower():
                    self.model_combo.setCurrentIndex(i)
                    break
        
        self.refresh_models_btn.setEnabled(True)
        self.add_log(f"成功获取 {len(models)} 个模型")
    
    @pyqtSlot(str)
    def on_model_fetch_error(self, error):
        """模型获取错误"""
        self.refresh_models_btn.setEnabled(True)
        self.add_log(f"获取模型失败: {error}")
        QMessageBox.critical(self, "错误", f"获取模型列表失败:\n{error}")
    
    def start_processing(self):
        """开始处理音频"""
        # 验证配置
        api_keys = [key.strip() for key in self.api_keys_text.toPlainText().strip().split('\n') if key.strip()]
        
        if not api_keys:
            QMessageBox.warning(self, "警告", "请输入至少一个API密钥")
            return
        
        if not self.input_folder_edit.text():
            QMessageBox.warning(self, "警告", "请选择音频输入文件夹")
            return
        
        if not self.output_folder_edit.text():
            QMessageBox.warning(self, "警告", "请选择文本输出文件夹")
            return
        
        if not self.model_combo.currentText():
            QMessageBox.warning(self, "警告", "请选择模型")
            return
        
        # 更新API管理器
        self.api_manager.update_keys(api_keys)
        
        # 创建配置
        config = ProjectConfig(
            api_keys=api_keys,
            input_folder=self.input_folder_edit.text(),
            output_folder=self.output_folder_edit.text(),
            selected_model=self.model_combo.currentText(),
            thread_count=self.thread_spinbox.value(),
            system_prompt=self.system_prompt_text.toPlainText()
        )
        
        # 创建并启动工作线程
        self.worker = AudioProcessWorker(config, self.api_manager)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_processing_finished)
        self.worker.error.connect(self.on_processing_error)
        self.worker.file_processed.connect(self.on_file_processed)
        
        # 更新UI
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        
        self.add_log("="*50)
        self.add_log(f"开始处理音频文件...")
        self.add_log(f"模型: {config.selected_model}")
        self.add_log(f"线程数: {config.thread_count}")
        self.add_log(f"API密钥数: {len(api_keys)}")
        self.add_log("="*50)
        
        self.worker.start()
    
    def stop_processing(self):
        """停止处理"""
        if self.worker:
            reply = QMessageBox.question(
                self, "确认停止",
                "确定要停止当前处理吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.worker.stop()
                self.add_log("正在停止处理...")
                self.stop_btn.setEnabled(False)
    
    @pyqtSlot(str)
    def on_progress(self, message):
        """处理进度更新"""
        self.add_log(message)
        self.status_bar.showMessage(message)
    
    @pyqtSlot(dict)
    def on_processing_finished(self, result):
        """处理完成"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        
        self.add_log("="*50)
        self.add_log(f"处理完成!")
        self.add_log(f"总计: {result['total']} 个文件")
        self.add_log(f"处理: {result['processed']} 个文件")
        self.add_log(f"成功: {result['success']} 个文件")
        self.add_log(f"失败: {result['processed'] - result['success']} 个文件")
        self.add_log("="*50)
        
        self.status_bar.showMessage("处理完成")
        
        # 刷新预览
        self.refresh_preview()
        
        # 显示完成对话框
        QMessageBox.information(
            self, "处理完成", 
            f"音频处理完成!\n\n"
            f"总计: {result['total']} 个文件\n"
            f"成功: {result['success']} 个文件\n"
            f"失败: {result['processed'] - result['success']} 个文件"
        )
    
    @pyqtSlot(str)
    def on_processing_error(self, error):
        """处理错误"""
        self.add_log(f'<span style="color: red;">错误: {error}</span>')
    
    @pyqtSlot(str, bool, str)
    def on_file_processed(self, filename, success, message):
        """文件处理完成"""
        if success:
            self.add_log(f'<span style="color: green;">✓ {filename}: {message}</span>')
        else:
            self.add_log(f'<span style="color: red;">✗ {filename}: {message}</span>')
    
    def refresh_preview(self):
        """刷新预览表格"""
        output_folder = self.output_folder_edit.text()
        if not output_folder:
            return
        
        output_path = Path(output_folder)
        if not output_path.exists():
            return
        
        self.preview_table.setRowCount(0)
        
        # 获取所有处理过的文件
        processed_files = {}
        
        for file_path in output_path.iterdir():
            if file_path.suffix == '.txt':
                if file_path.name.endswith('_jp.txt'):
                    base_name = file_path.name[:-7]
                    if base_name not in processed_files:
                        processed_files[base_name] = {}
                    processed_files[base_name]['jp'] = file_path
                elif file_path.name.endswith('_zh.txt'):
                    base_name = file_path.name[:-7]
                    if base_name not in processed_files:
                        processed_files[base_name] = {}
                    processed_files[base_name]['zh'] = file_path
        
        # 统计信息
        total_files = len(processed_files)
        complete_files = sum(1 for f in processed_files.values() if 'jp' in f and 'zh' in f)
        incomplete_files = total_files - complete_files
        
        self.stats_label.setText(f"文件: {total_files} | 完成: {complete_files} | 未完成: {incomplete_files}")
        
        # 添加到表格
        for base_name, files in sorted(processed_files.items()):
            row = self.preview_table.rowCount()
            self.preview_table.insertRow(row)
            
            # 文件名
            self.preview_table.setItem(row, 0, QTableWidgetItem(base_name))
            
            # 日文内容
            jp_text = ""
            if 'jp' in files:
                try:
                    with open(files['jp'], 'r', encoding='utf-8') as f:
                        jp_text = f.read()
                except:
                    jp_text = "[读取失败]"
            
            jp_item = QTableWidgetItem(jp_text)
            jp_item.setToolTip(jp_text[:500] + "..." if len(jp_text) > 500 else jp_text)
            self.preview_table.setItem(row, 1, jp_item)
            
            # 中文内容
            zh_text = ""
            if 'zh' in files:
                try:
                    with open(files['zh'], 'r', encoding='utf-8') as f:
                        zh_text = f.read()
                except:
                    zh_text = "[读取失败]"
            
            zh_item = QTableWidgetItem(zh_text)
            zh_item.setToolTip(zh_text[:500] + "..." if len(zh_text) > 500 else zh_text)
            self.preview_table.setItem(row, 2, zh_item)
            
            # 状态
            if 'jp' in files and 'zh' in files:
                status_item = QTableWidgetItem("✓ 完成")
                status_item.setForeground(QColor(0, 128, 0))
            else:
                status_item = QTableWidgetItem("⚠ 不完整")
                status_item.setForeground(QColor(255, 140, 0))
            
            self.preview_table.setItem(row, 3, status_item)
        
        self.add_log(f"预览已刷新: {total_files} 个文件")
    
    def save_preview_changes(self):
        """保存预览表格的修改"""
        output_folder = self.output_folder_edit.text()
        if not output_folder:
            QMessageBox.warning(self, "警告", "请先设置输出文件夹")
            return
        
        output_path = Path(output_folder)
        output_path.mkdir(parents=True, exist_ok=True)
        
        saved_count = 0
        error_count = 0
        
        for row in range(self.preview_table.rowCount()):
            try:
                base_name = self.preview_table.item(row, 0).text()
                jp_text = self.preview_table.item(row, 1).text() if self.preview_table.item(row, 1) else ""
                zh_text = self.preview_table.item(row, 2).text() if self.preview_table.item(row, 2) else ""
                
                # 保存日文
                if jp_text and jp_text != "[读取失败]":
                    jp_file = output_path / f"{base_name}_jp.txt"
                    with open(jp_file, 'w', encoding='utf-8') as f:
                        f.write(jp_text)
                
                # 保存中文
                if zh_text and zh_text != "[读取失败]":
                    zh_file = output_path / f"{base_name}_zh.txt"
                    with open(zh_file, 'w', encoding='utf-8') as f:
                        f.write(zh_text)
                
                saved_count += 1
                
            except Exception as e:
                error_count += 1
                self.add_log(f"保存失败 {base_name}: {str(e)}")
        
        self.add_log(f"保存完成: 成功 {saved_count} 个，失败 {error_count} 个")
        
        if error_count == 0:
            QMessageBox.information(self, "成功", f"已保存 {saved_count} 个文件的修改")
        else:
            QMessageBox.warning(self, "部分成功", 
                               f"保存完成\n成功: {saved_count} 个\n失败: {error_count} 个\n\n请查看日志获取详细信息")
    
    def delete_selected(self):
        """删除选中的文件"""
        selected_rows = set()
        for item in self.preview_table.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            QMessageBox.information(self, "提示", "请先选择要删除的文件")
            return
        
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除选中的 {len(selected_rows)} 个文件吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            output_path = Path(self.output_folder_edit.text())
            deleted_count = 0
            
            for row in selected_rows:
                base_name = self.preview_table.item(row, 0).text()
                
                # 删除对应的文件
                jp_file = output_path / f"{base_name}_jp.txt"
                zh_file = output_path / f"{base_name}_zh.txt"
                
                try:
                    if jp_file.exists():
                        jp_file.unlink()
                    if zh_file.exists():
                        zh_file.unlink()
                    deleted_count += 1
                except Exception as e:
                    self.add_log(f"删除失败 {base_name}: {str(e)}")
            
            self.add_log(f"删除了 {deleted_count} 个文件")
            self.refresh_preview()
    
    def add_log(self, message):
        """添加日志消息"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 检测是否包含HTML标签
        if '<span' in message:
            formatted_message = f"[{timestamp}] {message}"
        else:
            formatted_message = f"[{timestamp}] {message}"
        
        self.log_browser.append(formatted_message)
        
        # 自动滚动到底部
        if self.auto_scroll_check.isChecked():
            scrollbar = self.log_browser.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
    
    def clear_log(self):
        """清空日志"""
        reply = QMessageBox.question(
            self, "确认", "确定要清空所有日志吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.log_browser.clear()
            self.add_log("日志已清空")
    
    def export_log(self):
        """导出日志"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出日志", f"audio_log_{time.strftime('%Y%m%d_%H%M%S')}.txt", 
            "文本文件 (*.txt)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.log_browser.toPlainText())
                
                self.add_log(f"日志已导出到: {file_path}")
                QMessageBox.information(self, "成功", "日志导出成功")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出日志失败: {str(e)}")
    
    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self, "关于",
            "音频打标专业工具 v2.0\n\n"
            "使用 Google Gemini API 进行音频转写和翻译\n"
            "支持日语到中文的专业翻译\n\n"
            "特性:\n"
            "• 支持多种音频格式 (MP3, WAV, OGG, FLAC等)\n"
            "• 多线程并发处理\n"
            "• API密钥轮询机制\n"
            "• 项目管理功能\n"
            "• 实时预览和编辑\n\n"
            "基于 PyQt6 和 Google Generative AI API"
        )
    
    def closeEvent(self, event):
        """关闭事件处理"""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "确认退出",
                "处理任务正在进行中，确定要退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                if self.worker:
                    self.worker.stop()
                    self.worker.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyle('Fusion')
    
    # 设置应用程序图标和信息
    app.setApplicationName("音频打标专业工具")
    app.setOrganizationName("Audio Processing Tools")
    
    # 创建并显示主窗口
    window = AudioLabelingApp()
    window.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
