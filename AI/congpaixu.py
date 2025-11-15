import sys
import os
import re
import json
import asyncio
import aiohttp
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any
from datetime import datetime

from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                            QWidget, QPushButton, QLabel, QLineEdit, QTextEdit, 
                            QFileDialog, QSpinBox, QProgressBar, QGroupBox, 
                            QGridLayout, QScrollArea, QComboBox, QMessageBox,
                            QSplitter, QFrame, QCheckBox)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QPalette, QColor


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file="config.json"):
        self.config_file = Path(config_file)
        self.default_config = {
            "input_folder": "",
            "output_folder": "",
            "api_url": "https://kilocode-miler.deno.dev/v1/chat/completions",
            "api_key": "",
            "model": "claude-3-7-sonnet-20250219",
            "fixed_words": "",
            "system_prompt": """你是一个强大的Stable Diffusion绘画提示词构造大师，十分擅长各种Stable Diffusion提示词构造，并且能够准确的将用户的提示词严格按照用户需求进行重排序,并且直接提取()包裹里的内容，然后移除提示词的()等包裹符合，然后使用<sdtext></sdtext>包裹排序后的提示词发送回去，仅可发送提示词，其余多余的不进行发送，排序规则严格为：[固定角色名字][人物数量词][人物数量词修饰][发型发色][眼睛颜色][头部发饰][身体服装][腿部服装][服装饰品装饰][表情][服装状态][身体部位][身体部位状态][角色动作][背景]""",
            "max_concurrent": 20,
            "skip_existing": True
        }
    
    def load_config(self) -> Dict[str, Any]:
        """加载配置"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # 合并默认配置，确保所有键都存在
                merged_config = self.default_config.copy()
                merged_config.update(config)
                return merged_config
            else:
                return self.default_config.copy()
        except Exception as e:
            print(f"加载配置失败: {e}")
            return self.default_config.copy()
    
    def save_config(self, config: Dict[str, Any]):
        """保存配置"""
        try:
            # 创建备份
            if self.config_file.exists():
                backup_file = self.config_file.with_suffix('.json.bak')
                self.config_file.rename(backup_file)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            # 删除备份文件
            backup_file = self.config_file.with_suffix('.json.bak')
            if backup_file.exists():
                backup_file.unlink()
                
        except Exception as e:
            print(f"保存配置失败: {e}")
            # 如果保存失败，尝试恢复备份
            backup_file = self.config_file.with_suffix('.json.bak')
            if backup_file.exists():
                backup_file.rename(self.config_file)


class APIWorker(QThread):
    progress_updated = pyqtSignal(int, int)  # current, total
    file_processed = pyqtSignal(str, bool, str)  # filename, success, message
    file_skipped = pyqtSignal(str, str)  # filename, reason
    finished = pyqtSignal()
    
    def __init__(self, input_folder, output_folder, api_url, api_key, model, 
                 system_prompt, fixed_words, max_concurrent, skip_existing=True):
        super().__init__()
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.system_prompt = system_prompt
        self.fixed_words = fixed_words
        self.max_concurrent = max_concurrent
        self.skip_existing = skip_existing
        self.is_running = True
        
    def run(self):
        asyncio.run(self.process_files())
        
    def stop(self):
        self.is_running = False
        
    async def process_files(self):
        txt_files = list(Path(self.input_folder).glob("*.txt"))
        total_files = len(txt_files)
        
        if total_files == 0:
            self.file_processed.emit("", False, "未找到txt文件")
            self.finished.emit()
            return
        
        # 过滤需要处理的文件
        files_to_process = []
        skipped_count = 0
        
        for txt_file in txt_files:
            output_file = Path(self.output_folder) / txt_file.name
            
            if self.skip_existing and output_file.exists():
                self.file_skipped.emit(txt_file.name, "输出文件已存在，跳过处理")
                skipped_count += 1
            else:
                files_to_process.append(txt_file)
        
        if not files_to_process:
            self.file_processed.emit("", False, f"所有文件都已存在，共跳过 {skipped_count} 个文件")
            self.finished.emit()
            return
        
        # 更新总数为实际需要处理的文件数
        actual_total = len(files_to_process)
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            for i, txt_file in enumerate(files_to_process):
                if not self.is_running:
                    break
                task = self.process_single_file(session, semaphore, txt_file, i + 1, actual_total)
                tasks.append(task)
            
            await asyncio.gather(*tasks, return_exceptions=True)
        
        self.finished.emit()
    
    async def process_single_file(self, session, semaphore, txt_file, current, total):
        async with semaphore:
            if not self.is_running:
                return
                
            try:
                # 读取文件内容
                with open(txt_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                
                if not content:
                    self.file_processed.emit(txt_file.name, False, "文件内容为空")
                    self.progress_updated.emit(current, total)
                    return
                
                # 构建请求
                user_message = f"固定词为[{self.fixed_words}]，请你排序这个提示词：[{content}]"
                
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    "temperature": 0.1
                }
                
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                # 发送请求
                async with session.post(self.api_url, json=payload, headers=headers, timeout=60) as response:
                    if response.status == 200:
                        result = await response.json()
                        response_content = result['choices'][0]['message']['content']
                        
                        # 提取重排序后的提示词
                        match = re.search(r'<sdtext>(.*?)</sdtext>', response_content, re.DOTALL)
                        if match:
                            sorted_prompt = match.group(1).strip()
                            
                            # 保存到输出文件夹
                            output_file = Path(self.output_folder) / txt_file.name
                            with open(output_file, 'w', encoding='utf-8') as f:
                                f.write(sorted_prompt)
                            
                            self.file_processed.emit(txt_file.name, True, "处理成功")
                        else:
                            self.file_processed.emit(txt_file.name, False, "未找到<sdtext>标签")
                    else:
                        error_text = await response.text()
                        self.file_processed.emit(txt_file.name, False, f"API错误: {response.status} - {error_text}")
                        
            except Exception as e:
                self.file_processed.emit(txt_file.name, False, f"处理错误: {str(e)}")
            
            self.progress_updated.emit(current, total)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.config_manager = ConfigManager()
        self.init_ui()
        self.setup_styles()
        self.load_config()
        
    def init_ui(self):
        self.setWindowTitle("SD绘画提示词批量重排序工具 v2.0")
        self.setGeometry(100, 100, 1000, 800)
        
        # 创建中央部件和主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(splitter)
        
        # 配置区域
        config_widget = QWidget()
        config_layout = QVBoxLayout(config_widget)
        config_layout.setSpacing(15)
        
        # 文件路径配置
        path_group = QGroupBox("文件路径配置")
        path_layout = QGridLayout(path_group)
        path_layout.setSpacing(10)
        
        # 输入文件夹
        path_layout.addWidget(QLabel("输入文件夹:"), 0, 0)
        self.input_folder_edit = QLineEdit()
        self.input_folder_edit.setPlaceholderText("选择包含txt文件的文件夹")
        path_layout.addWidget(self.input_folder_edit, 0, 1)
        
        input_browse_btn = QPushButton("浏览")
        input_browse_btn.clicked.connect(self.browse_input_folder)
        path_layout.addWidget(input_browse_btn, 0, 2)
        
        # 输出文件夹
        path_layout.addWidget(QLabel("输出文件夹:"), 1, 0)
        self.output_folder_edit = QLineEdit()
        self.output_folder_edit.setPlaceholderText("选择输出重排序文件的文件夹")
        path_layout.addWidget(self.output_folder_edit, 1, 1)
        
        output_browse_btn = QPushButton("浏览")
        output_browse_btn.clicked.connect(self.browse_output_folder)
        path_layout.addWidget(output_browse_btn, 1, 2)
        
        config_layout.addWidget(path_group)
        
        # API配置
        api_group = QGroupBox("API配置")
        api_layout = QGridLayout(api_group)
        api_layout.setSpacing(10)
        
        # API URL
        api_layout.addWidget(QLabel("API URL:"), 0, 0)
        self.api_url_edit = QLineEdit()
        self.api_url_edit.setPlaceholderText("输入API请求地址")
        api_layout.addWidget(self.api_url_edit, 0, 1, 1, 2)
        
        # API Key
        api_layout.addWidget(QLabel("API Key:"), 1, 0)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("输入API密钥")
        api_layout.addWidget(self.api_key_edit, 1, 1, 1, 2)
        
        # 模型选择
        api_layout.addWidget(QLabel("模型:"), 2, 0)
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItems([
            "claude-3-7-sonnet-20250219",
            "gpt-4",
            "gpt-4-turbo",
            "claude-3-sonnet",
            "claude-3-opus"
        ])
        api_layout.addWidget(self.model_combo, 2, 1)
        
        # 最大并发数
        api_layout.addWidget(QLabel("最大并发数:"), 2, 2)
        self.max_concurrent_spin = QSpinBox()
        self.max_concurrent_spin.setRange(1, 100)
        self.max_concurrent_spin.setValue(20)
        api_layout.addWidget(self.max_concurrent_spin, 2, 3)
        
        config_layout.addWidget(api_group)
        
        # 处理选项
        options_group = QGroupBox("处理选项")
        options_layout = QVBoxLayout(options_group)
        
        self.skip_existing_checkbox = QCheckBox("跳过已存在的输出文件")
        self.skip_existing_checkbox.setChecked(True)
        self.skip_existing_checkbox.setToolTip("如果输出文件夹中已存在同名文件，则跳过处理该文件")
        options_layout.addWidget(self.skip_existing_checkbox)
        
        config_layout.addWidget(options_group)
        
        # 提示词配置
        prompt_group = QGroupBox("提示词配置")
        prompt_layout = QVBoxLayout(prompt_group)
        prompt_layout.setSpacing(10)
        
        # 固定词
        fixed_words_layout = QHBoxLayout()
        fixed_words_layout.addWidget(QLabel("固定词:"))
        self.fixed_words_edit = QLineEdit()
        self.fixed_words_edit.setPlaceholderText("输入固定词，如角色名等")
        fixed_words_layout.addWidget(self.fixed_words_edit)
        prompt_layout.addLayout(fixed_words_layout)
        
        # 系统提示词
        prompt_layout.addWidget(QLabel("系统提示词:"))
        self.system_prompt_edit = QTextEdit()
        self.system_prompt_edit.setMaximumHeight(120)
        prompt_layout.addWidget(self.system_prompt_edit)
        
        config_layout.addWidget(prompt_group)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # 保存配置按钮
        save_config_btn = QPushButton("保存配置")
        save_config_btn.clicked.connect(self.save_config)
        save_config_btn.setMinimumHeight(40)
        button_layout.addWidget(save_config_btn)
        
        # 加载配置按钮
        load_config_btn = QPushButton("重新加载配置")
        load_config_btn.clicked.connect(self.load_config)
        load_config_btn.setMinimumHeight(40)
        button_layout.addWidget(load_config_btn)
        
        button_layout.addStretch()
        
        self.start_btn = QPushButton("开始处理")
        self.start_btn.clicked.connect(self.start_processing)
        self.start_btn.setMinimumHeight(40)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("停止处理")
        self.stop_btn.clicked.connect(self.stop_processing)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setMinimumHeight(40)
        button_layout.addWidget(self.stop_btn)
        
        button_layout.addStretch()
        config_layout.addLayout(button_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        config_layout.addWidget(self.progress_bar)
        
        splitter.addWidget(config_widget)
        
        # 日志区域
        log_group = QGroupBox("处理日志")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        log_layout.addWidget(self.log_text)
        
        # 清空日志按钮
        clear_log_btn = QPushButton("清空日志")
        clear_log_btn.clicked.connect(self.clear_log)
        log_layout.addWidget(clear_log_btn)
        
        splitter.addWidget(log_group)
        
        # 设置分割器比例
        splitter.setSizes([600, 200])
        
    def setup_styles(self):
        """设置界面样式"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px 0 10px;
                color: #333333;
            }
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QLineEdit, QTextEdit, QComboBox {
                border: 2px solid #ddd;
                border-radius: 4px;
                padding: 5px;
                background-color: white;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                border-color: #4CAF50;
            }
            QSpinBox {
                border: 2px solid #ddd;
                border-radius: 4px;
                padding: 5px;
                background-color: white;
                min-width: 80px;
            }
            QProgressBar {
                border: 2px solid #ddd;
                border-radius: 4px;
                text-align: center;
                background-color: #f0f0f0;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 2px;
            }
            QCheckBox {
                spacing: 8px;
                color: #333333;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #ddd;
                border-radius: 3px;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border-color: #4CAF50;
            }
            QCheckBox::indicator:checked:hover {
                background-color: #45a049;
            }
        """)
    
    def browse_input_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择输入文件夹")
        if folder:
            self.input_folder_edit.setText(folder)
    
    def browse_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if folder:
            self.output_folder_edit.setText(folder)
    
    def clear_log(self):
        self.log_text.clear()
    
    def log_message(self, message, color="black"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.setTextColor(QColor(color))
        self.log_text.append(f"[{timestamp}] {message}")
        self.log_text.setTextColor(QColor("black"))
        # 自动滚动到底部
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
    
    def get_current_config(self) -> Dict[str, Any]:
        """获取当前界面配置"""
        return {
            "input_folder": self.input_folder_edit.text(),
            "output_folder": self.output_folder_edit.text(),
            "api_url": self.api_url_edit.text(),
            "api_key": self.api_key_edit.text(),
            "model": self.model_combo.currentText(),
            "fixed_words": self.fixed_words_edit.text(),
            "system_prompt": self.system_prompt_edit.toPlainText(),
            "max_concurrent": self.max_concurrent_spin.value(),
            "skip_existing": self.skip_existing_checkbox.isChecked()
        }
    
    def set_config_to_ui(self, config: Dict[str, Any]):
        """将配置设置到界面"""
        self.input_folder_edit.setText(config.get("input_folder", ""))
        self.output_folder_edit.setText(config.get("output_folder", ""))
        self.api_url_edit.setText(config.get("api_url", ""))
        self.api_key_edit.setText(config.get("api_key", ""))
        
        model = config.get("model", "")
        if model:
            index = self.model_combo.findText(model)
            if index >= 0:
                self.model_combo.setCurrentIndex(index)
            else:
                self.model_combo.setCurrentText(model)
        
        self.fixed_words_edit.setText(config.get("fixed_words", ""))
        self.system_prompt_edit.setPlainText(config.get("system_prompt", ""))
        self.max_concurrent_spin.setValue(config.get("max_concurrent", 20))
        self.skip_existing_checkbox.setChecked(config.get("skip_existing", True))
    
    def load_config(self):
        """加载配置"""
        try:
            config = self.config_manager.load_config()
            self.set_config_to_ui(config)
            self.log_message("配置加载成功", "blue")
        except Exception as e:
            self.log_message(f"配置加载失败: {e}", "red")
    
    def save_config(self):
        """保存配置"""
        try:
            config = self.get_current_config()
            self.config_manager.save_config(config)
            self.log_message("配置保存成功", "blue")
            QMessageBox.information(self, "成功", "配置已保存到 config.json")
        except Exception as e:
            self.log_message(f"配置保存失败: {e}", "red")
            QMessageBox.warning(self, "错误", f"配置保存失败: {e}")
    
    def closeEvent(self, event):
        """程序关闭时自动保存配置"""
        try:
            config = self.get_current_config()
            self.config_manager.save_config(config)
        except Exception as e:
            print(f"自动保存配置失败: {e}")
        
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "确认退出", 
                "正在处理文件，确定要退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.worker.stop()
                self.worker.quit()
                self.worker.wait(3000)  # 等待最多3秒
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
    
    def start_processing(self):
        # 验证输入
        if not self.input_folder_edit.text():
            QMessageBox.warning(self, "警告", "请选择输入文件夹")
            return
        
        if not self.output_folder_edit.text():
            QMessageBox.warning(self, "警告", "请选择输出文件夹")
            return
        
        if not self.api_url_edit.text():
            QMessageBox.warning(self, "警告", "请输入API URL")
            return
        
        if not self.api_key_edit.text():
            QMessageBox.warning(self, "警告", "请输入API Key")
            return
        
        if not self.model_combo.currentText():
            QMessageBox.warning(self, "警告", "请选择或输入模型名称")
            return
        
        # 检查输入文件夹是否存在
        if not Path(self.input_folder_edit.text()).exists():
            QMessageBox.warning(self, "警告", "输入文件夹不存在")
            return
        
        # 创建输出文件夹
        try:
            os.makedirs(self.output_folder_edit.text(), exist_ok=True)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法创建输出文件夹: {e}")
            return
        
        # 统计文件信息
        txt_files = list(Path(self.input_folder_edit.text()).glob("*.txt"))
        if not txt_files:
            QMessageBox.information(self, "提示", "输入文件夹中没有找到txt文件")
            return
        
        # 统计需要处理和跳过的文件
        existing_files = 0
        if self.skip_existing_checkbox.isChecked():
            for txt_file in txt_files:
                output_file = Path(self.output_folder_edit.text()) / txt_file.name
                if output_file.exists():
                    existing_files += 1
        
        total_files = len(txt_files)
        files_to_process = total_files - existing_files
        
        self.log_message(f"发现 {total_files} 个txt文件", "blue")
        if existing_files > 0:
            self.log_message(f"跳过 {existing_files} 个已存在的文件", "orange")
        self.log_message(f"将处理 {files_to_process} 个文件", "blue")
        
        if files_to_process == 0:
            QMessageBox.information(self, "提示", "所有文件都已存在，无需处理")
            return
        
        # 启动工作线程
        self.worker = APIWorker(
            self.input_folder_edit.text(),
            self.output_folder_edit.text(),
            self.api_url_edit.text(),
            self.api_key_edit.text(),
            self.model_combo.currentText(),
            self.system_prompt_edit.toPlainText(),
            self.fixed_words_edit.text(),
            self.max_concurrent_spin.value(),
            self.skip_existing_checkbox.isChecked()
        )
        
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.file_processed.connect(self.on_file_processed)
        self.worker.file_skipped.connect(self.on_file_skipped)
        self.worker.finished.connect(self.on_processing_finished)
        
        self.worker.start()
        
        # 更新UI状态
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.log_message("开始处理文件...", "blue")
    
    def stop_processing(self):
        if self.worker:
            self.worker.stop()
            self.log_message("正在停止处理...", "orange")
    
    def update_progress(self, current, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
    
    def on_file_processed(self, filename, success, message):
        if success:
            self.log_message(f"✓ {filename}: {message}", "green")
        else:
            self.log_message(f"✗ {filename}: {message}", "red")
    
    def on_file_skipped(self, filename, reason):
        self.log_message(f"⏭ {filename}: {reason}", "orange")
    
    def on_processing_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.log_message("处理完成！", "blue")
        
        if self.worker:
            self.worker.quit()
            self.worker.wait()
            self.worker = None


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 使用Fusion样式获得更好的外观
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
