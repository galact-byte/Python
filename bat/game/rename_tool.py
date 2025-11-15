import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QWidget, QPushButton, QListWidget, QListWidgetItem,
                             QLineEdit, QLabel, QRadioButton, QButtonGroup, 
                             QSpinBox, QCheckBox, QGroupBox, QFileDialog,
                             QMessageBox, QProgressBar, QTextEdit)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon

class RenameWorker(QThread):
    """重命名工作线程"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(list)  # 传递成功和失败的文件列表
    error = pyqtSignal(str)

    def __init__(self, files, rename_type, prefix="", remove_prefix_count=0, 
                 remove_suffix_count=0, keep_extension=True, new_extension="", output_dir=""):
        super().__init__()
        self.files = files
        self.rename_type = rename_type
        self.prefix = prefix
        self.remove_prefix_count = remove_prefix_count
        self.remove_suffix_count = remove_suffix_count
        self.keep_extension = keep_extension
        self.new_extension = new_extension
        self.output_dir = output_dir

    def run(self):
        success_files = []
        failed_files = []
        total_files = len(self.files)

        for i, file_path in enumerate(self.files):
            try:
                original_path = Path(file_path)
                original_name = original_path.stem
                original_ext = original_path.suffix

                if self.rename_type == 1:  # 前缀+数字编号
                    new_name = f"{self.prefix}{i+1:03d}"
                elif self.rename_type == 2:  # 移除前几个字符
                    if len(original_name) > self.remove_prefix_count:
                        new_name = original_name[self.remove_prefix_count:]
                    else:
                        new_name = original_name
                elif self.rename_type == 3:  # 移除后几个字符
                    if len(original_name) > self.remove_suffix_count:
                        new_name = original_name[:-self.remove_suffix_count] if self.remove_suffix_count > 0 else original_name
                    else:
                        new_name = original_name
                else:
                    new_name = original_name

                # 处理空名称的情况
                if not new_name.strip():
                    new_name = f"renamed_{i+1}"

                # 处理扩展名
                if self.keep_extension:
                    final_extension = original_ext
                else:
                    final_extension = f".{self.new_extension}" if self.new_extension else ""

                # 确定输出路径
                if self.output_dir:
                    output_path = Path(self.output_dir) / f"{new_name}{final_extension}"
                else:
                    output_path = original_path.parent / f"{new_name}{final_extension}"

                # 避免文件名冲突
                counter = 1
                base_output_path = output_path
                while output_path.exists() and output_path != original_path:
                    name_with_counter = f"{new_name}_{counter}"
                    output_path = base_output_path.parent / f"{name_with_counter}{final_extension}"
                    counter += 1

                # 执行重命名
                if output_path != original_path:
                    if self.output_dir:  # 复制到新目录
                        import shutil
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(original_path, output_path)
                    else:  # 直接重命名
                        original_path.rename(output_path)

                success_files.append((str(original_path), str(output_path)))

            except Exception as e:
                failed_files.append((str(file_path), str(e)))

            # 更新进度
            progress_value = int((i + 1) / total_files * 100)
            self.progress.emit(progress_value)

        self.finished.emit([success_files, failed_files])

class FileRenamerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.files = []
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("批量文件重命名工具")
        self.setGeometry(100, 100, 850, 700)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 文件导入区域
        import_group = QGroupBox("文件导入")
        import_layout = QVBoxLayout(import_group)
        
        # 导入按钮
        import_buttons_layout = QHBoxLayout()
        self.import_folder_btn = QPushButton("导入文件夹")
        self.import_files_btn = QPushButton("导入文件")
        self.clear_files_btn = QPushButton("清空列表")
        
        import_buttons_layout.addWidget(self.import_folder_btn)
        import_buttons_layout.addWidget(self.import_files_btn)
        import_buttons_layout.addWidget(self.clear_files_btn)
        import_buttons_layout.addStretch()
        
        import_layout.addLayout(import_buttons_layout)
        
        # 文件列表
        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(150)
        import_layout.addWidget(self.file_list)
        
        main_layout.addWidget(import_group)
        
        # 重命名选项区域
        rename_group = QGroupBox("重命名选项")
        rename_layout = QVBoxLayout(rename_group)
        
        # 重命名类型选择
        self.rename_type_group = QButtonGroup()
        self.prefix_radio = QRadioButton("前缀+数字编号重命名")
        self.remove_prefix_radio = QRadioButton("移除文件前缀字符重命名")
        self.remove_suffix_radio = QRadioButton("移除文件后缀字符重命名")
        self.prefix_radio.setChecked(True)
        
        self.rename_type_group.addButton(self.prefix_radio, 1)
        self.rename_type_group.addButton(self.remove_prefix_radio, 2)
        self.rename_type_group.addButton(self.remove_suffix_radio, 3)
        
        rename_layout.addWidget(self.prefix_radio)
        rename_layout.addWidget(self.remove_prefix_radio)
        rename_layout.addWidget(self.remove_suffix_radio)
        
        # 前缀设置
        prefix_layout = QHBoxLayout()
        prefix_layout.addWidget(QLabel("前缀:"))
        self.prefix_edit = QLineEdit("file_")
        self.prefix_edit.setMaximumWidth(200)
        prefix_layout.addWidget(self.prefix_edit)
        prefix_layout.addStretch()
        rename_layout.addLayout(prefix_layout)
        
        # 移除前缀字符数设置
        remove_prefix_layout = QHBoxLayout()
        remove_prefix_layout.addWidget(QLabel("移除前缀字符数:"))
        self.remove_prefix_spinbox = QSpinBox()
        self.remove_prefix_spinbox.setMinimum(0)
        self.remove_prefix_spinbox.setMaximum(50)
        self.remove_prefix_spinbox.setValue(3)
        self.remove_prefix_spinbox.setMaximumWidth(100)
        remove_prefix_layout.addWidget(self.remove_prefix_spinbox)
        remove_prefix_layout.addStretch()
        rename_layout.addLayout(remove_prefix_layout)
        
        # 移除后缀字符数设置
        remove_suffix_layout = QHBoxLayout()
        remove_suffix_layout.addWidget(QLabel("移除后缀字符数:"))
        self.remove_suffix_spinbox = QSpinBox()
        self.remove_suffix_spinbox.setMinimum(0)
        self.remove_suffix_spinbox.setMaximum(50)
        self.remove_suffix_spinbox.setValue(3)
        self.remove_suffix_spinbox.setMaximumWidth(100)
        remove_suffix_layout.addWidget(self.remove_suffix_spinbox)
        remove_suffix_layout.addStretch()
        rename_layout.addLayout(remove_suffix_layout)
        
        # 示例说明
        example_label = QLabel("示例: 'document_2023.txt' → 移除前缀3字符 → 'ument_2023.txt' | 移除后缀4字符 → 'document_20.txt'")
        example_label.setStyleSheet("color: #666; font-size: 10px; font-style: italic;")
        example_label.setWordWrap(True)
        rename_layout.addWidget(example_label)
        
        main_layout.addWidget(rename_group)
        
        # 扩展名选项区域
        ext_group = QGroupBox("扩展名选项")
        ext_layout = QVBoxLayout(ext_group)
        
        self.keep_ext_checkbox = QCheckBox("保持原扩展名")
        self.keep_ext_checkbox.setChecked(True)
        ext_layout.addWidget(self.keep_ext_checkbox)
        
        new_ext_layout = QHBoxLayout()
        new_ext_layout.addWidget(QLabel("新扩展名:"))
        self.new_ext_edit = QLineEdit("txt")
        self.new_ext_edit.setEnabled(False)
        self.new_ext_edit.setMaximumWidth(200)
        new_ext_layout.addWidget(self.new_ext_edit)
        new_ext_layout.addStretch()
        ext_layout.addLayout(new_ext_layout)
        
        main_layout.addWidget(ext_group)
        
        # 输出选项区域
        output_group = QGroupBox("输出选项")
        output_layout = QVBoxLayout(output_group)
        
        self.same_dir_checkbox = QCheckBox("在原目录重命名（直接重命名原文件）")
        self.same_dir_checkbox.setChecked(True)
        output_layout.addWidget(self.same_dir_checkbox)
        
        output_dir_layout = QHBoxLayout()
        output_dir_layout.addWidget(QLabel("输出目录:"))
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setEnabled(False)
        self.browse_output_btn = QPushButton("浏览")
        self.browse_output_btn.setEnabled(False)
        self.browse_output_btn.setMaximumWidth(80)
        output_dir_layout.addWidget(self.output_dir_edit)
        output_dir_layout.addWidget(self.browse_output_btn)
        output_layout.addLayout(output_dir_layout)
        
        output_note = QLabel("注：不勾选时将复制文件到新目录并重命名，原文件保持不变")
        output_note.setStyleSheet("color: #666; font-size: 10px; font-style: italic;")
        output_layout.addWidget(output_note)
        
        main_layout.addWidget(output_group)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # 执行按钮
        button_layout = QHBoxLayout()
        self.preview_btn = QPushButton("预览重命名")
        self.execute_btn = QPushButton("执行重命名")
        self.preview_btn.setMinimumHeight(35)
        self.execute_btn.setMinimumHeight(35)
        
        button_layout.addStretch()
        button_layout.addWidget(self.preview_btn)
        button_layout.addWidget(self.execute_btn)
        
        main_layout.addLayout(button_layout)
        
        # 日志区域
        log_group = QGroupBox("操作日志")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        main_layout.addWidget(log_group)
        
        # 连接信号
        self.connect_signals()
        
        # 设置样式
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QRadioButton {
                spacing: 5px;
                margin: 5px;
            }
            QRadioButton:checked {
                color: #0078d4;
                font-weight: bold;
            }
        """)

    def connect_signals(self):
        # 导入文件相关
        self.import_folder_btn.clicked.connect(self.import_folder)
        self.import_files_btn.clicked.connect(self.import_files)
        self.clear_files_btn.clicked.connect(self.clear_files)
        
        # 选项变化
        self.keep_ext_checkbox.toggled.connect(self.toggle_extension_input)
        self.same_dir_checkbox.toggled.connect(self.toggle_output_dir)
        self.browse_output_btn.clicked.connect(self.browse_output_dir)
        
        # 重命名类型变化
        self.rename_type_group.buttonToggled.connect(self.on_rename_type_changed)
        
        # 执行按钮
        self.preview_btn.clicked.connect(self.preview_rename)
        self.execute_btn.clicked.connect(self.execute_rename)

    def on_rename_type_changed(self):
        """重命名类型改变时的处理"""
        rename_type = self.rename_type_group.checkedId()
        
        # 根据选择的类型启用/禁用相应的控件
        self.prefix_edit.setEnabled(rename_type == 1)
        self.remove_prefix_spinbox.setEnabled(rename_type == 2)
        self.remove_suffix_spinbox.setEnabled(rename_type == 3)

    def import_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            files = []
            for file_path in Path(folder).iterdir():
                if file_path.is_file():
                    files.append(str(file_path))
            self.add_files(files)

    def import_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择文件")
        if files:
            self.add_files(files)

    def add_files(self, files):
        added_count = 0
        for file_path in files:
            if file_path not in self.files:
                self.files.append(file_path)
                item = QListWidgetItem(Path(file_path).name)
                item.setToolTip(file_path)
                self.file_list.addItem(item)
                added_count += 1
        
        if added_count > 0:
            self.log_text.append(f"已添加 {added_count} 个新文件，当前总计 {len(self.files)} 个文件")
        else:
            self.log_text.append("没有添加新文件（可能已存在）")

    def clear_files(self):
        self.files.clear()
        self.file_list.clear()
        self.log_text.append("已清空文件列表")

    def toggle_extension_input(self, checked):
        self.new_ext_edit.setEnabled(not checked)

    def toggle_output_dir(self, checked):
        self.output_dir_edit.setEnabled(not checked)
        self.browse_output_btn.setEnabled(not checked)

    def browse_output_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if folder:
            self.output_dir_edit.setText(folder)

    def get_new_filename(self, file_path, index):
        """生成新文件名"""
        original_path = Path(file_path)
        original_name = original_path.stem
        original_ext = original_path.suffix

        # 根据重命名类型生成新名称
        rename_type = self.rename_type_group.checkedId()
        if rename_type == 1:  # 前缀+数字编号
            new_name = f"{self.prefix_edit.text()}{index+1:03d}"
        elif rename_type == 2:  # 移除前几个字符
            remove_count = self.remove_prefix_spinbox.value()
            if len(original_name) > remove_count:
                new_name = original_name[remove_count:]
            else:
                new_name = original_name
        elif rename_type == 3:  # 移除后几个字符
            remove_count = self.remove_suffix_spinbox.value()
            if len(original_name) > remove_count and remove_count > 0:
                new_name = original_name[:-remove_count]
            else:
                new_name = original_name
        else:
            new_name = original_name

        # 处理空名称的情况
        if not new_name.strip():
            new_name = f"renamed_{index+1}"

        # 处理扩展名
        if self.keep_ext_checkbox.isChecked():
            final_extension = original_ext
        else:
            ext_text = self.new_ext_edit.text().strip()
            final_extension = f".{ext_text}" if ext_text else ""

        return f"{new_name}{final_extension}"

    def preview_rename(self):
        if not self.files:
            QMessageBox.warning(self, "警告", "请先导入文件")
            return

        preview_text = "重命名预览:\n" + "="*60 + "\n"
        
        # 获取当前重命名类型
        rename_type = self.rename_type_group.checkedId()
        type_names = {1: "前缀+数字编号", 2: "移除前缀字符", 3: "移除后缀字符"}
        preview_text += f"重命名模式: {type_names.get(rename_type, '未知')}\n"
        
        if rename_type == 1:
            preview_text += f"前缀: '{self.prefix_edit.text()}'\n"
        elif rename_type == 2:
            preview_text += f"移除前缀字符数: {self.remove_prefix_spinbox.value()}\n"
        elif rename_type == 3:
            preview_text += f"移除后缀字符数: {self.remove_suffix_spinbox.value()}\n"
            
        preview_text += f"扩展名处理: {'保持原扩展名' if self.keep_ext_checkbox.isChecked() else f'改为 .{self.new_ext_edit.text()}'}\n"
        preview_text += "-"*60 + "\n"
        
        for i, file_path in enumerate(self.files):
            original_name = Path(file_path).name
            new_name = self.get_new_filename(file_path, i)
            preview_text += f"{i+1:3d}. {original_name} → {new_name}\n"
            
            # 限制预览数量
            if i >= 19:
                remaining = len(self.files) - 20
                if remaining > 0:
                    preview_text += f"... 还有 {remaining} 个文件\n"
                break

        # 显示预览对话框
        dialog = QMessageBox(self)
        dialog.setWindowTitle("重命名预览")
        dialog.setText(f"将要处理 {len(self.files)} 个文件:")
        dialog.setDetailedText(preview_text)
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.exec()

    def execute_rename(self):
        if not self.files:
            QMessageBox.warning(self, "警告", "请先导入文件")
            return

        # 确认对话框
        reply = QMessageBox.question(
            self, "确认操作", 
            f"确定要重命名 {len(self.files)} 个文件吗？\n\n"
            "注意：此操作不可撤销！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return

        # 获取参数
        rename_type = self.rename_type_group.checkedId()
        prefix = self.prefix_edit.text()
        remove_prefix_count = self.remove_prefix_spinbox.value()
        remove_suffix_count = self.remove_suffix_spinbox.value()
        keep_extension = self.keep_ext_checkbox.isChecked()
        new_extension = self.new_ext_edit.text().strip()
        
        output_dir = ""
        if not self.same_dir_checkbox.isChecked():
            output_dir = self.output_dir_edit.text().strip()
            if not output_dir:
                QMessageBox.warning(self, "警告", "请选择输出目录")
                return

        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 禁用执行按钮
        self.execute_btn.setEnabled(False)
        self.preview_btn.setEnabled(False)
        
        # 记录开始时间
        self.log_text.append(f"\n开始批量重命名操作...")
        type_names = {1: "前缀+数字编号", 2: "移除前缀字符", 3: "移除后缀字符"}
        self.log_text.append(f"模式: {type_names.get(rename_type, '未知')}")
        
        # 创建工作线程
        self.worker = RenameWorker(
            self.files, rename_type, prefix, remove_prefix_count, remove_suffix_count,
            keep_extension, new_extension, output_dir
        )
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self.on_rename_finished)
        self.worker.error.connect(self.on_rename_error)
        self.worker.start()

    def on_rename_finished(self, result):
        success_files, failed_files = result
        
        # 隐藏进度条
        self.progress_bar.setVisible(False)
        
        # 启用按钮
        self.execute_btn.setEnabled(True)
        self.preview_btn.setEnabled(True)
        
        # 显示结果
        self.log_text.append(f"\n批量重命名操作完成！")
        self.log_text.append(f"✅ 成功: {len(success_files)} 个文件")
        self.log_text.append(f"❌ 失败: {len(failed_files)} 个文件")
        
        if success_files:
            self.log_text.append("\n成功处理的文件:")
            for i, (original, new) in enumerate(success_files[:5]):  # 只显示前5个
                self.log_text.append(f"  {i+1}. {Path(original).name} → {Path(new).name}")
            if len(success_files) > 5:
                self.log_text.append(f"  ... 还有 {len(success_files)-5} 个文件")
        
        if failed_files:
            self.log_text.append("\n处理失败的文件:")
            for file_path, error in failed_files:
                self.log_text.append(f"  ❌ {Path(file_path).name}: {error}")

        # 显示完成对话框
        message = f"批量重命名操作完成！\n\n✅ 成功: {len(success_files)} 个文件\n❌ 失败: {len(failed_files)} 个文件"
        if failed_files:
            message += f"\n\n详细信息请查看操作日志。"
            
        QMessageBox.information(self, "操作完成", message)

    def on_rename_error(self, error):
        self.progress_bar.setVisible(False)
        self.execute_btn.setEnabled(True)
        self.preview_btn.setEnabled(True)
        self.log_text.append(f"\n❌ 操作失败: {error}")
        QMessageBox.critical(self, "错误", f"重命名过程中发生错误:\n{error}")

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 使用现代化样式
    
    window = FileRenamerApp()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
