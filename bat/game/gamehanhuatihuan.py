import sys
import os
import shutil
import hashlib
import time

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QTableWidget, QTableWidgetItem,
    QProgressBar, QTextEdit, QTabWidget, QHeaderView, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal
from PyQt6.QtGui import QIcon, QColor


# --- 样式表 ---
STYLESHEET = """
QWidget {
    font-family: 'Microsoft YaHei', 'Segoe UI', Arial, sans-serif;
    font-size: 10pt;
}
QMainWindow {
    background-color: #f0f0f0;
}
QTabWidget::pane {
    border: 1px solid #c5c5c5;
    border-top: none;
}
QTabBar::tab {
    background: #e1e1e1;
    border: 1px solid #c5c5c5;
    border-bottom: none;
    padding: 8px 20px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    background: #ffffff;
    margin-bottom: -1px;
}
QPushButton {
    background-color: #0078d7;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
}
QPushButton:hover {
    background-color: #005a9e;
}
QPushButton:disabled {
    background-color: #a0a0a0;
    color: #c0c0c0;
}
QTableWidget {
    border: 1px solid #c5c5c5;
    gridline-color: #e0e0e0;
}
QHeaderView::section {
    background-color: #f0f0f0;
    padding: 4px;
    border: 1px solid #c5c5c5;
    font-weight: bold;
}
QProgressBar {
    border: 1px solid #c5c5c5;
    border-radius: 4px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #0078d7;
    border-radius: 4px;
}
QTextEdit {
    background-color: #ffffff;
    border: 1px solid #c5c5c5;
    border-radius: 4px;
}
QLabel#pathLabel {
    background-color: #ffffff;
    border: 1px solid #c5c5c5;
    padding: 4px;
    border-radius: 4px;
}
"""

# --- 多线程工作逻辑 ---
class Worker(QObject):
    """
    执行文件处理任务的工作者，运行在独立的线程中。
    """
    # 信号定义
    progress = pyqtSignal(int)  # 进度更新信号 (0-100)
    log = pyqtSignal(str)       # 日志消息信号
    finished = pyqtSignal()     # 任务完成信号
    row_update = pyqtSignal(int, str, str)  # (行号, 输出文件名, 状态)

    def __init__(self, tasks, dir_a, output_dir):
        super().__init__()
        self.tasks = tasks
        self.dir_a = dir_a
        self.output_dir = output_dir
        self.is_running = True

    def run(self):
        """执行替换任务"""
        total_tasks = len(self.tasks)
        if total_tasks == 0:
            self.log.emit("没有需要处理的任务。")
            self.finished.emit()
            return

        self.log.emit(f"开始处理 {total_tasks} 个文件...")
        for i, task_info in enumerate(self.tasks):
            if not self.is_running:
                self.log.emit("任务被用户中止。")
                break

            row, file_a, file_b = task_info
            source_path = os.path.join(self.dir_a, file_a)
            output_filename = file_b # 输出文件名与b目录文件名一致
            dest_path = os.path.join(self.output_dir, output_filename)

            status = "失败"
            try:
                # 确保输出目录存在
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                
                # 复制并重命名文件
                shutil.copy2(source_path, dest_path)
                self.log.emit(f"文件复制: {file_a} -> {output_filename}")

                # 哈希校验
                hash_a = self.calculate_hash(source_path)
                hash_dest = self.calculate_hash(dest_path)

                if hash_a == hash_dest:
                    status = "完成"
                    self.log.emit(f"校验成功: {output_filename} (SHA256: {hash_a[:8]}...)")
                else:
                    status = "校验失败"
                    self.log.emit(f"[错误] 校验失败: {output_filename}. 源哈希与目标哈希不匹配。")

            except Exception as e:
                status = "执行错误"
                self.log.emit(f"[错误] 处理文件 {file_a} 时发生错误: {e}")
            
            # 发送行更新信号
            self.row_update.emit(row, output_filename, status)
            
            # 更新总体进度
            progress_value = int(((i + 1) / total_tasks) * 100)
            self.progress.emit(progress_value)
            
            # 稍微延时，让UI有时间刷新
            time.sleep(0.01)

        self.log.emit("所有任务处理完毕。")
        self.finished.emit()

    def stop(self):
        self.is_running = False

    @staticmethod
    def calculate_hash(filepath, block_size=65536):
        """计算文件的SHA256哈希值"""
        sha256 = hashlib.sha256()
        try:
            with open(filepath, 'rb') as f:
                for block in iter(lambda: f.read(block_size), b''):
                    sha256.update(block)
            return sha256.hexdigest()
        except FileNotFoundError:
            return None


# --- 主窗口 ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("文件内容替换工具")
        self.setGeometry(100, 100, 1000, 800)
        self.setWindowIcon(QIcon.fromTheme("document-save", QIcon(":/qt-project.org/styles/commonstyle/images/standardbutton-save-32.png")))

        # --- 成员变量 ---
        self.dir_a = ""
        self.dir_b = ""
        self.output_dir = ""
        self.thread = None
        self.worker = None

        # --- UI 初始化 ---
        self.init_ui()
        self.update_control_states()

    def init_ui(self):
        # --- 主选项卡布局 ---
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # 创建“操作”和“设置”两个选项卡
        self.ops_tab = QWidget()
        self.settings_tab = QWidget()

        self.tabs.addTab(self.ops_tab, "操作")
        self.tabs.addTab(self.settings_tab, "设置")

        # --- “操作”选项卡布局 ---
        ops_layout = QVBoxLayout(self.ops_tab)

        # 目录选择区
        dir_layout = QHBoxLayout()
        self.btn_load_a = QPushButton("加载目录 A")
        self.btn_load_b = QPushButton("加载目录 B")
        self.label_dir_a = QLabel("未选择")
        self.label_dir_a.setObjectName("pathLabel")
        self.label_dir_b = QLabel("未选择")
        self.label_dir_b.setObjectName("pathLabel")

        dir_layout.addWidget(self.btn_load_a)
        dir_layout.addWidget(self.label_dir_a, 1)
        dir_layout.addSpacing(20)
        dir_layout.addWidget(self.btn_load_b)
        dir_layout.addWidget(self.label_dir_b, 1)
        ops_layout.addLayout(dir_layout)

        # 文件列表表格
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["目录A 文件", "目录B 文件", "输出文件", "状态"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        ops_layout.addWidget(self.table)

        # 控制按钮区
        control_layout = QHBoxLayout()
        self.btn_start = QPushButton("开始替换")
        self.btn_retry = QPushButton("重试失败项")
        control_layout.addWidget(self.btn_start)
        control_layout.addWidget(self.btn_retry)
        control_layout.addStretch()
        ops_layout.addLayout(control_layout)

        # 进度条和日志区
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        ops_layout.addWidget(self.progress_bar)

        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        ops_layout.addWidget(self.log_widget)

        # --- “设置”选项卡布局 ---
        settings_layout = QVBoxLayout(self.settings_tab)
        output_dir_layout = QHBoxLayout()

        self.btn_output_dir = QPushButton("选择输出目录")
        self.label_output_dir = QLabel("未选择")
        self.label_output_dir.setObjectName("pathLabel")

        output_dir_layout.addWidget(self.btn_output_dir)
        output_dir_layout.addWidget(self.label_output_dir, 1)
        settings_layout.addLayout(output_dir_layout)
        settings_layout.addStretch()

        # --- 连接信号和槽 ---
        self.btn_load_a.clicked.connect(self.select_dir_a)
        self.btn_load_b.clicked.connect(self.select_dir_b)
        self.btn_output_dir.clicked.connect(self.select_output_dir)
        self.btn_start.clicked.connect(self.start_replacement)
        self.btn_retry.clicked.connect(self.retry_failed)
        
    def select_dir_a(self):
        """选择目录A"""
        path = QFileDialog.getExistingDirectory(self, "选择目录 A")
        if path:
            self.dir_a = path
            self.label_dir_a.setText(path)
            self.log(f"已加载目录 A: {path}")
            self.match_files()
            self.update_control_states()

    def select_dir_b(self):
        """选择目录B"""
        path = QFileDialog.getExistingDirectory(self, "选择目录 B")
        if path:
            self.dir_b = path
            self.label_dir_b.setText(path)
            self.log(f"已加载目录 B: {path}")
            self.match_files()
            self.update_control_states()

    def select_output_dir(self):
        """选择输出目录"""
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.output_dir = path
            self.label_output_dir.setText(path)
            self.log(f"已设置输出目录: {path}")
            self.update_control_states()

    def log(self, message):
        """向日志窗口添加消息"""
        self.log_widget.append(f"[{time.strftime('%H:%M:%S')}] {message}")

    def match_files(self):
        """匹配目录A和目录B中的文件，并更新表格"""
        if not self.dir_a or not self.dir_b:
            return

        self.log("开始匹配文件...")
        self.table.setRowCount(0)

        files_a = [f for f in os.listdir(self.dir_a) if f.endswith('.txt')]
        files_b = [f for f in os.listdir(self.dir_b) if f.endswith('.txt')]

        map_a = {os.path.splitext(f)[0]: f for f in files_a}
        
        matches = []
        for file_b in files_b:
            base_b = os.path.splitext(file_b)[0]
            for base_a, file_a in map_a.items():
                if base_b.startswith(base_a + '-'):
                    matches.append((file_a, file_b))
                    break
        
        self.table.setRowCount(len(matches))
        for row, (file_a, file_b) in enumerate(matches):
            self.table.setItem(row, 0, QTableWidgetItem(file_a))
            self.table.setItem(row, 1, QTableWidgetItem(file_b))
            self.table.setItem(row, 2, QTableWidgetItem(""))
            self.table.setItem(row, 3, QTableWidgetItem("待处理"))

        self.log(f"文件匹配完成，共找到 {len(matches)} 对文件。")

    def start_replacement(self):
        """开始全部替换任务"""
        tasks = []
        for row in range(self.table.rowCount()):
            file_a = self.table.item(row, 0).text()
            file_b = self.table.item(row, 1).text()
            tasks.append((row, file_a, file_b))
        
        if not tasks:
            QMessageBox.warning(self, "提示", "没有可执行的任务。请先加载目录并匹配文件。")
            return
            
        self.run_tasks(tasks)

    def retry_failed(self):
        """重试状态为“失败”或“错误”的任务"""
        tasks = []
        failed_statuses = {"校验失败", "执行错误", "失败"}
        for row in range(self.table.rowCount()):
            status_item = self.table.item(row, 3)
            if status_item and status_item.text() in failed_statuses:
                file_a = self.table.item(row, 0).text()
                file_b = self.table.item(row, 1).text()
                tasks.append((row, file_a, file_b))
        
        if not tasks:
            QMessageBox.information(self, "提示", "没有找到失败的任务。")
            return
        
        self.log(f"准备重试 {len(tasks)} 个失败的任务。")
        self.run_tasks(tasks)

    def run_tasks(self, tasks):
        """通用任务执行函数"""
        if not self.output_dir:
            QMessageBox.warning(self, "错误", "请先在“设置”页面中指定输出目录！")
            self.tabs.setCurrentIndex(1) # 切换到设置页
            return
            
        self.set_controls_enabled(False)
        self.progress_bar.setValue(0)

        self.thread = QThread()
        self.worker = Worker(tasks, self.dir_a, self.output_dir)
        self.worker.moveToThread(self.thread)

        # 连接信号
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.log.connect(self.log)
        self.worker.progress.connect(self.update_progress)
        self.worker.row_update.connect(self.update_row)
        self.thread.finished.connect(lambda: self.set_controls_enabled(True))

        self.thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_row(self, row, output_filename, status):
        """更新表格中特定行的状态"""
        self.table.setItem(row, 2, QTableWidgetItem(output_filename))
        status_item = QTableWidgetItem(status)
        
        color = QColor("#ffffff") # 默认白色
        if status == "完成":
            color = QColor("#c8e6c9") # 淡绿色
        elif "失败" in status or "错误" in status:
            color = QColor("#ffcdd2") # 淡红色
        
        status_item.setBackground(color)
        self.table.setItem(row, 3, status_item)

    def update_control_states(self):
        """根据当前状态启用或禁用按钮"""
        ready_to_start = bool(self.dir_a and self.dir_b and self.output_dir and self.table.rowCount() > 0)
        self.btn_start.setEnabled(ready_to_start)
        self.btn_retry.setEnabled(ready_to_start)

    def set_controls_enabled(self, enabled):
        """统一设置所有控制按钮的可用状态"""
        self.btn_load_a.setEnabled(enabled)
        self.btn_load_b.setEnabled(enabled)
        self.btn_output_dir.setEnabled(enabled)
        self.btn_start.setEnabled(enabled)
        self.btn_retry.setEnabled(enabled)
        self.tabs.setTabEnabled(1, enabled) # 设置页面

    def closeEvent(self, event):
        """关闭窗口时确保线程已停止"""
        if self.thread and self.thread.isRunning():
            self.log("正在中止任务...")
            self.worker.stop()
            self.thread.quit()
            self.thread.wait() # 等待线程完全退出
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
