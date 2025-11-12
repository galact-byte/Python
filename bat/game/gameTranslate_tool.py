import sys
import os
import re
import json
import threading
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QGridLayout, QPushButton, QTextEdit, 
                             QProgressBar, QLabel, QFileDialog, QMessageBox,
                             QTabWidget, QListWidget, QSplitter, QGroupBox,
                             QFrame, QScrollArea)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon

class ExtractWorker(QThread):
    """提取文本的工作线程"""
    progress_updated = pyqtSignal(int)
    log_updated = pyqtSignal(str)
    finished = pyqtSignal(dict)
    
    def __init__(self, folder_path):
        super().__init__()
        self.folder_path = folder_path
    
    def run(self):
        try:
            self.log_updated.emit("开始提取日语文本...")
            
            input_dir = Path(self.folder_path)
            output_dir = input_dir / "output"
            output_dir.mkdir(exist_ok=True)
            
            # 获取所有txt文件
            txt_files = list(input_dir.glob("*.txt"))
            total_files = len(txt_files)
            
            if total_files == 0:
                self.log_updated.emit("❌ 在选择的文件夹中没有找到任何txt文件")
                self.finished.emit({})
                return
            
            all_texts = {}
            processed_files = 0
            
            for file_path in txt_files:
                self.log_updated.emit(f"正在处理: {file_path.name}")
                
                extracted_texts = self.process_script_file(file_path)
                
                if extracted_texts:
                    for text in extracted_texts:
                        json_key = self.normalize_text_for_json(text)
                        all_texts[json_key] = ""
                    
                    self.log_updated.emit(f"✅ {file_path.name} - 提取了 {len(extracted_texts)} 条文本")
                else:
                    self.log_updated.emit(f"⚠️  {file_path.name} - 没有找到日语文本")
                
                processed_files += 1
                progress = int((processed_files / total_files) * 100)
                self.progress_updated.emit(progress)
            
            # 保存JSON文件
            if all_texts:
                output_file = output_dir / "extracted_japanese_texts.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(all_texts, f, ensure_ascii=False, indent=2)
                
                self.log_updated.emit(f"\n🎉 提取完成！")
                self.log_updated.emit(f"📊 总共处理了 {total_files} 个文件")
                self.log_updated.emit(f"📝 提取了 {len(all_texts)} 条唯一的日语文本")
                self.log_updated.emit(f"💾 已保存到: {output_file}")
                self.log_updated.emit(f"\n📌 请翻译 extracted_japanese_texts.json 文件")
                self.log_updated.emit(f"📌 然后重命名为 completed.json")
            
            self.finished.emit(all_texts)
            
        except Exception as e:
            self.log_updated.emit(f"❌ 提取过程中出错: {str(e)}")
            self.finished.emit({})
    
    def process_script_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return self.extract_japanese_text(content)
        except Exception as e:
            self.log_updated.emit(f"❌ 处理文件 {file_path} 时出错: {e}")
            return []
    
    def extract_japanese_text(self, content):
        blocks_with_pos = []
        for match in re.finditer(r'@.*?;', content, re.DOTALL):
            block = match.group(0)
            block_content = block[1:-1].strip()
            lines = block_content.split('\n')
            
            japanese_lines = []
            for line in lines:
                line = line.strip()
                if line and self.contains_japanese(line):
                    japanese_lines.append(line)
            
            if japanese_lines:
                combined_text = '\n'.join(japanese_lines)
                blocks_with_pos.append(combined_text)
        
        return blocks_with_pos
    
    def contains_japanese(self, text):
        japanese_pattern = r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF\u3400-\u4DBF\uFF01-\uFF5E\u3000-\u303F【】]'
        return bool(re.search(japanese_pattern, text))
    
    def normalize_text_for_json(self, text):
        return text.replace('\n', '\\r\\n')

class TranslateWorker(QThread):
    """翻译应用的工作线程"""
    progress_updated = pyqtSignal(int)
    log_updated = pyqtSignal(str)
    finished = pyqtSignal(bool, dict)
    
    def __init__(self, folder_path):
        super().__init__()
        self.folder_path = folder_path
    
    def run(self):
        try:
            self.log_updated.emit("开始应用翻译...")
            
            input_dir = Path(self.folder_path)
            output_dir = input_dir / "output"
            completed_dir = input_dir / "completed"
            completed_dir.mkdir(exist_ok=True)
            
            # 读取翻译字典
            translation_file = output_dir / "completed.json"
            if not translation_file.exists():
                self.log_updated.emit("❌ 找不到翻译文件 completed.json")
                self.log_updated.emit("📌 请确保已经翻译了extracted_japanese_texts.json并重命名为completed.json")
                self.finished.emit(False, {})
                return
            
            with open(translation_file, 'r', encoding='utf-8') as f:
                translation_dict = json.load(f)
            
            # 统计应该翻译的文本数量
            translated_texts = {k: v for k, v in translation_dict.items() if v.strip()}
            empty_texts = {k: v for k, v in translation_dict.items() if not v.strip()}
            
            self.log_updated.emit(f"📖 加载翻译字典: {len(translation_dict)} 条总计")
            self.log_updated.emit(f"✅ 已翻译: {len(translated_texts)} 条")
            self.log_updated.emit(f"⚠️  未翻译: {len(empty_texts)} 条")
            
            if empty_texts:
                self.log_updated.emit("\n⚠️  警告：以下文本尚未翻译：")
                for i, key in enumerate(list(empty_texts.keys())[:5]):  # 只显示前5个
                    display_text = key.replace('\\r\\n', ' ').strip()
                    if len(display_text) > 50:
                        display_text = display_text[:50] + "..."
                    self.log_updated.emit(f"   {i+1}. {display_text}")
                if len(empty_texts) > 5:
                    self.log_updated.emit(f"   ... 还有 {len(empty_texts)-5} 条未翻译")
            
            # 获取所有txt文件
            txt_files = list(input_dir.glob("*.txt"))
            total_files = len(txt_files)
            
            if total_files == 0:
                self.log_updated.emit("❌ 没有找到要翻译的txt文件")
                self.finished.emit(False, {})
                return
            
            processed_files = 0
            total_replacements = 0
            translation_stats = {}
            
            for file_path in txt_files:
                self.log_updated.emit(f"\n📝 正在翻译: {file_path.name}")
                
                replacement_count = self.translate_script_file(file_path, translation_dict, completed_dir)
                if replacement_count >= 0:
                    total_replacements += replacement_count
                    translation_stats[file_path.name] = replacement_count
                    self.log_updated.emit(f"✅ {file_path.name} - 完成 {replacement_count} 处替换")
                else:
                    self.log_updated.emit(f"❌ {file_path.name} - 翻译失败")
                
                processed_files += 1
                progress = int((processed_files / total_files) * 100)
                self.progress_updated.emit(progress)
            
            # 验证替换完整性
            self.log_updated.emit(f"\n📊 翻译统计：")
            self.log_updated.emit(f"总替换次数: {total_replacements}")
            self.log_updated.emit(f"已翻译文本数: {len(translated_texts)}")
            
            if total_replacements == len(translated_texts):
                self.log_updated.emit("✅ 替换完整性验证通过！")
            elif total_replacements < len(translated_texts):
                missed = len(translated_texts) - total_replacements
                self.log_updated.emit(f"⚠️  可能有 {missed} 条翻译未被应用")
            else:
                extra = total_replacements - len(translated_texts)
                self.log_updated.emit(f"ℹ️  替换次数超出预期 {extra} 次（可能有重复文本）")
            
            self.log_updated.emit(f"\n🎉 翻译完成！文件保存在 completed 目录")
            self.finished.emit(True, translation_stats)
            
        except Exception as e:
            self.log_updated.emit(f"❌ 翻译过程中出错: {str(e)}")
            self.finished.emit(False, {})
    
    def translate_script_file(self, file_path, translation_dict, output_dir):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            replacement_count = 0
            
            def replace_block(match):
                nonlocal replacement_count
                original_block = match.group(0)
                new_block = self.replace_japanese_text_in_block(original_block, translation_dict)
                if new_block != original_block:
                    replacement_count += 1
                return new_block
            
            translated_content = re.sub(r'@.*?;', replace_block, content, flags=re.DOTALL)
            
            output_file = output_dir / file_path.name
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(translated_content)
            
            return replacement_count
        except Exception as e:
            self.log_updated.emit(f"❌ 翻译文件 {file_path} 时出错: {e}")
            return -1
    
    def replace_japanese_text_in_block(self, block, translation_dict):
        block_content = block[1:-1]
        lines = block_content.split('\n')
        
        japanese_lines = []
        for line in lines:
            line_stripped = line.strip()
            if line_stripped and self.contains_japanese(line_stripped):
                japanese_lines.append(line_stripped)
        
        if japanese_lines:
            combined_japanese = '\n'.join(japanese_lines)
            json_key = self.normalize_text_for_json(combined_japanese)
            
            if json_key in translation_dict and translation_dict[json_key]:
                translated_text = self.denormalize_text_from_json(translation_dict[json_key])
                translated_lines = translated_text.split('\n')
                
                new_lines = []
                translated_line_index = 0
                
                for line in lines:
                    line_stripped = line.strip()
                    if line_stripped and self.contains_japanese(line_stripped):
                        if translated_line_index < len(translated_lines):
                            indent = len(line) - len(line.lstrip())
                            new_lines.append(' ' * indent + translated_lines[translated_line_index])
                            translated_line_index += 1
                        else:
                            new_lines.append(line)
                    else:
                        new_lines.append(line)
                
                new_block_content = '\n'.join(new_lines)
                return '@' + new_block_content + ';'
        
        return block
    
    def contains_japanese(self, text):
        japanese_pattern = r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF\u3400-\u4DBF\uFF01-\uFF5E\u3000-\u303F【】]'
        return bool(re.search(japanese_pattern, text))
    
    def normalize_text_for_json(self, text):
        return text.replace('\n', '\\r\\n')
    
    def denormalize_text_from_json(self, text):
        return text.replace('\\r\\n', '\n')

class GameLocalizationGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.folder_path = ""
        self.translation_stats = {}
        self.init_ui()
        self.apply_styles()
    
    def init_ui(self):
        self.setWindowTitle("游戏脚本汉化工具 v2.0")
        self.setGeometry(100, 100, 1200, 800)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 创建选项卡
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # 主要功能选项卡
        self.create_main_tab()
        
        # 文件对比选项卡
        self.create_compare_tab()
    
    def create_main_tab(self):
        """创建主要功能选项卡"""
        main_tab = QWidget()
        self.tab_widget.addTab(main_tab, "主要功能")
        
        layout = QVBoxLayout(main_tab)
        
        # 文件夹选择区域
        folder_group = QGroupBox("文件夹选择")
        folder_layout = QHBoxLayout(folder_group)
        
        self.folder_label = QLabel("请选择包含游戏脚本的文件夹")
        self.folder_label.setStyleSheet("color: #666; font-style: italic;")
        
        self.select_folder_btn = QPushButton("📁 选择文件夹")
        self.select_folder_btn.clicked.connect(self.select_folder)
        
        folder_layout.addWidget(self.folder_label, 1)
        folder_layout.addWidget(self.select_folder_btn)
        layout.addWidget(folder_group)
        
        # 操作按钮区域
        button_group = QGroupBox("操作")
        button_layout = QHBoxLayout(button_group)
        
        self.extract_btn = QPushButton("🔍 提取日语文本")
        self.extract_btn.setEnabled(False)
        self.extract_btn.clicked.connect(self.extract_texts)
        
        self.translate_btn = QPushButton("🌍 应用翻译")
        self.translate_btn.setEnabled(False)
        self.translate_btn.clicked.connect(self.apply_translation)
        
        button_layout.addWidget(self.extract_btn)
        button_layout.addWidget(self.translate_btn)
        layout.addWidget(button_group)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 日志区域
        log_group = QGroupBox("操作日志")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(300)
        log_layout.addWidget(self.log_text)
        
        # 日志控制按钮
        log_button_layout = QHBoxLayout()
        
        self.clear_log_btn = QPushButton("🗑️ 清空日志")
        self.clear_log_btn.clicked.connect(self.clear_log)
        
        self.save_log_btn = QPushButton("💾 保存日志")
        self.save_log_btn.clicked.connect(self.save_log)
        
        log_button_layout.addWidget(self.clear_log_btn)
        log_button_layout.addWidget(self.save_log_btn)
        log_button_layout.addStretch()
        
        log_layout.addLayout(log_button_layout)
        layout.addWidget(log_group)
    
    def create_compare_tab(self):
        """创建文件对比选项卡"""
        compare_tab = QWidget()
        self.tab_widget.addTab(compare_tab, "文件对比")
        
        layout = QVBoxLayout(compare_tab)
        
        # 刷新按钮
        refresh_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("🔄 刷新文件列表")
        self.refresh_btn.clicked.connect(self.refresh_file_lists)
        refresh_layout.addWidget(self.refresh_btn)
        refresh_layout.addStretch()
        layout.addLayout(refresh_layout)
        
        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        
        # 原始文件列表
        original_group = QGroupBox("原始文件")
        original_layout = QVBoxLayout(original_group)
        self.original_list = QListWidget()
        self.original_list.itemClicked.connect(self.on_original_file_selected)
        original_layout.addWidget(self.original_list)
        splitter.addWidget(original_group)
        
        # 翻译后文件列表
        translated_group = QGroupBox("翻译后文件")
        translated_layout = QVBoxLayout(translated_group)
        self.translated_list = QListWidget()
        self.translated_list.itemClicked.connect(self.on_translated_file_selected)
        translated_layout.addWidget(self.translated_list)
        splitter.addWidget(translated_group)
        
        layout.addWidget(splitter)
        
        # 文件内容预览
        preview_group = QGroupBox("文件预览")
        preview_layout = QHBoxLayout(preview_group)
        
        # 原始文件预览
        original_preview_layout = QVBoxLayout()
        original_title = QLabel("原始文件内容:")
        original_title.setFixedHeight(25)  # 固定标题高度
        original_preview_layout.addWidget(original_title)
        self.original_preview = QTextEdit()
        self.original_preview.setReadOnly(True)
        self.original_preview.setMinimumHeight(400)  # 增加预览框高度
        original_preview_layout.addWidget(self.original_preview)
        
        # 翻译后文件预览
        translated_preview_layout = QVBoxLayout()
        translated_title = QLabel("翻译后文件内容:")
        translated_title.setFixedHeight(25)  # 固定标题高度
        translated_preview_layout.addWidget(translated_title)
        self.translated_preview = QTextEdit()
        self.translated_preview.setReadOnly(True)
        self.translated_preview.setMinimumHeight(400)  # 增加预览框高度
        translated_preview_layout.addWidget(self.translated_preview)
        
        preview_layout.addLayout(original_preview_layout)
        preview_layout.addLayout(translated_preview_layout)
        layout.addWidget(preview_group)
    
    def apply_styles(self):
        """应用样式"""
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
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 10px 20px;
                text-align: center;
                font-size: 14px;
                border-radius: 6px;
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
            
            QProgressBar {
                border: 2px solid #cccccc;
                border-radius: 5px;
                text-align: center;
                font-weight: bold;
            }
            
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
            
            QTextEdit {
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 5px;
                font-family: 'Consolas', 'Monaco', monospace;
            }
            
            QListWidget {
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 5px;
            }
            
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #eeeeee;
            }
            
            QListWidget::item:selected {
                background-color: #4CAF50;
                color: white;
            }
            
            QTabWidget::pane {
                border: 1px solid #cccccc;
                border-radius: 4px;
            }
            
            QTabBar::tab {
                background-color: #eeeeee;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 2px solid #4CAF50;
            }
        """)
        
        # 设置字体
        font = QFont("Microsoft YaHei", 10)
        self.setFont(font)
    
    def select_folder(self):
        """选择文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择包含游戏脚本的文件夹")
        if folder:
            self.folder_path = folder
            self.folder_label.setText(f"已选择: {folder}")
            self.folder_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.extract_btn.setEnabled(True)
            self.translate_btn.setEnabled(True)  # 移除条件限制，始终启用
            
            self.log(f"📁 已选择文件夹: {folder}")
            self.refresh_file_lists()
    
    def extract_texts(self):
        """提取文本"""
        if not self.folder_path:
            self.log("❌ 请先选择文件夹！")
            return
        
        self.extract_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.extract_worker = ExtractWorker(self.folder_path)
        self.extract_worker.progress_updated.connect(self.progress_bar.setValue)
        self.extract_worker.log_updated.connect(self.log)
        self.extract_worker.finished.connect(self.on_extract_finished)
        self.extract_worker.start()
    
    def apply_translation(self):
        """应用翻译"""
        if not self.folder_path:
            self.log("❌ 请先选择文件夹！")
            return
        
        # 不再锁住按钮，让工作线程处理错误检查
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.translate_worker = TranslateWorker(self.folder_path)
        self.translate_worker.progress_updated.connect(self.progress_bar.setValue)
        self.translate_worker.log_updated.connect(self.log)
        self.translate_worker.finished.connect(self.on_translate_finished)
        self.translate_worker.start()
    
    def on_extract_finished(self, texts):
        """提取完成的回调"""
        self.extract_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.refresh_file_lists()
    
    def on_translate_finished(self, success, stats):
        """翻译完成的回调"""
        self.progress_bar.setVisible(False)
        self.translation_stats = stats
        
        if success:
            self.refresh_file_lists()
            # 自动切换到对比选项卡
            self.tab_widget.setCurrentIndex(1)
    
    def refresh_file_lists(self):
        """刷新文件列表"""
        if not self.folder_path:
            return
        
        self.original_list.clear()
        self.translated_list.clear()
        
        # 加载原始文件
        input_dir = Path(self.folder_path)
        for txt_file in input_dir.glob("*.txt"):
            item_text = txt_file.name
            if txt_file.name in self.translation_stats:
                count = self.translation_stats[txt_file.name]
                item_text += f" ({count} 处替换)"
            self.original_list.addItem(item_text)
        
        # 加载翻译后文件
        completed_dir = input_dir / "completed"
        if completed_dir.exists():
            for txt_file in completed_dir.glob("*.txt"):
                self.translated_list.addItem(txt_file.name)
    
    def on_original_file_selected(self, item):
        """原始文件被选中"""
        if not self.folder_path:
            return
        
        filename = item.text().split(" (")[0]  # 移除统计信息
        file_path = Path(self.folder_path) / filename
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 限制显示长度
            if len(content) > 3000:
                content = content[:3000] + "\n\n... (文件内容过长，仅显示前3000个字符)"
            
            self.original_preview.setText(content)
        except Exception as e:
            self.original_preview.setText(f"无法读取文件: {str(e)}")
    
    def on_translated_file_selected(self, item):
        """翻译后文件被选中"""
        if not self.folder_path:
            return
        
        filename = item.text()
        file_path = Path(self.folder_path) / "completed" / filename
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 限制显示长度
            if len(content) > 5000:
                content = content[:5000] + "\n\n... (文件内容过长，仅显示前5000个字符)"
            
            self.translated_preview.setText(content)
        except Exception as e:
            self.translated_preview.setText(f"无法读取文件: {str(e)}")
    
    def log(self, message):
        """添加日志"""
        self.log_text.append(f"[{self.get_current_time()}] {message}")
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
    
    def clear_log(self):
        """清空日志"""
        self.log_text.clear()
    
    def save_log(self):
        """保存日志"""
        if not self.folder_path:
            self.log("❌ 请先选择工作文件夹！")
            return
        
        log_content = self.log_text.toPlainText()
        if not log_content.strip():
            self.log("ℹ️  日志为空，无需保存。")
            return
        
        try:
            log_file = Path(self.folder_path) / f"localization_log_{self.get_current_time().replace(':', '-')}.txt"
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(log_content)
            
            self.log(f"💾 日志已保存到: {log_file}")
        except Exception as e:
            self.log(f"❌ 保存日志失败: {str(e)}")
    
    def get_current_time(self):
        """获取当前时间字符串"""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")
    
    def closeEvent(self, event):
        """关闭事件"""
        reply = QMessageBox.question(self, "确认退出", 
                                   "确定要退出汉化工具吗？",
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("游戏脚本汉化工具")
    app.setApplicationVersion("2.0")
    
    # 设置应用图标（如果有的话）
    # app.setWindowIcon(QIcon("icon.png"))
    
    window = GameLocalizationGUI()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()