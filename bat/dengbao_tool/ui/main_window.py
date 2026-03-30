"""主窗口 — 向导式 3 步流程 + 变更日志"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStackedWidget, QLabel, QMessageBox,
    QTextEdit, QSplitter, QFrame
)
from PyQt6.QtCore import Qt

from ui.step1_files import Step1FilesPage
from ui.step2_editor import Step2EditorPage
from ui.step3_generate import Step3GeneratePage
from ui.change_tracker import ChangeTracker


class StepIndicator(QWidget):
    """三段式步骤指示器"""
    STEPS = ["选择文件", "编辑数据", "生成文档"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current = 0
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        self.labels = []
        self.connectors = []

        for i, name in enumerate(self.STEPS):
            # 圆圈 + 文字
            lbl = QLabel(f"  {i+1}. {name}  ")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.labels.append(lbl)
            layout.addWidget(lbl)

            if i < len(self.STEPS) - 1:
                line = QFrame()
                line.setFrameShape(QFrame.Shape.HLine)
                line.setFixedHeight(2)
                line.setMinimumWidth(40)
                self.connectors.append(line)
                layout.addWidget(line)

        self._update_style()

    def set_step(self, idx):
        self._current = idx
        self._update_style()

    def _update_style(self):
        for i, lbl in enumerate(self.labels):
            if i < self._current:
                # 已完成
                lbl.setStyleSheet(
                    "color: #30d158; font-weight: bold; font-size: 13px;"
                    "background: #1a2e1a; border-radius: 4px; padding: 4px 8px;")
            elif i == self._current:
                # 当前
                lbl.setStyleSheet(
                    "color: #0a84ff; font-weight: bold; font-size: 13px;"
                    "background: #1a2a4a; border-radius: 4px; padding: 4px 8px;")
            else:
                # 未到
                lbl.setStyleSheet(
                    "color: #8e8e93; font-size: 13px;"
                    "background: transparent; padding: 4px 8px;")

        for i, line in enumerate(self.connectors):
            if i < self._current:
                line.setStyleSheet("background-color: #30d158;")
            else:
                line.setStyleSheet("background-color: #3a3a3c;")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("等保文档迁移工具 v1.0")
        self.setMinimumSize(950, 750)
        self.tracker = ChangeTracker()
        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # 步骤指示器
        self.step_indicator = StepIndicator()
        layout.addWidget(self.step_indicator)

        # 主内容区 + 变更日志 splitter
        self.splitter = QSplitter(Qt.Orientation.Vertical)

        # 页面栈
        self.stack = QStackedWidget()
        self.step1 = Step1FilesPage()
        self.step2 = Step2EditorPage(tracker=self.tracker)
        self.step3 = Step3GeneratePage()
        self.stack.addWidget(self.step1)
        self.stack.addWidget(self.step2)
        self.stack.addWidget(self.step3)
        self.splitter.addWidget(self.stack)

        # 变更日志面板
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 4, 0, 0)
        log_layout.setSpacing(4)

        log_header = QHBoxLayout()
        log_title = QLabel("变更日志")
        log_title.setStyleSheet("color: #8e8e93; font-size: 12px; font-weight: bold;")
        self.log_toggle = QPushButton("收起")
        self.log_toggle.setFixedSize(48, 22)
        self.log_toggle.setStyleSheet("font-size: 11px; padding: 2px 6px;")
        self.log_toggle.clicked.connect(self._toggle_log)
        log_header.addWidget(log_title)
        log_header.addStretch()
        log_header.addWidget(self.log_toggle)
        log_layout.addLayout(log_header)

        self.change_log = QTextEdit()
        self.change_log.setReadOnly(True)
        self.change_log.setProperty("class", "changeLog")
        self.change_log.setMaximumHeight(140)
        self.change_log.setPlainText("暂无变更记录")
        log_layout.addWidget(self.change_log)

        self.splitter.addWidget(log_container)
        self.splitter.setStretchFactor(0, 4)
        self.splitter.setStretchFactor(1, 1)
        layout.addWidget(self.splitter)

        # 导航按钮
        nav = QHBoxLayout()
        nav.setContentsMargins(0, 4, 0, 4)
        self.btn_prev = QPushButton("上一步")
        self.btn_prev.setFixedHeight(36)
        self.btn_prev.setFixedWidth(100)
        self.btn_next = QPushButton("下一步")
        self.btn_next.setFixedHeight(36)
        self.btn_next.setFixedWidth(100)
        self.btn_next.setProperty("class", "primary")

        nav.addStretch()
        nav.addWidget(self.btn_prev)
        nav.addWidget(self.btn_next)
        nav.addStretch()
        layout.addLayout(nav)

        # 连接
        self.btn_prev.clicked.connect(self._prev)
        self.btn_next.clicked.connect(self._next)
        self.step3.generate_btn.clicked.connect(self._generate)
        self.tracker.add_listener(self._refresh_log)

        self._update_nav()

    def _toggle_log(self):
        visible = self.change_log.isVisible()
        self.change_log.setVisible(not visible)
        self.log_toggle.setText("展开" if visible else "收起")

    def _refresh_log(self):
        self.change_log.setPlainText(self.tracker.get_log_text())
        # 滚到底部
        sb = self.change_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _update_nav(self):
        idx = self.stack.currentIndex()
        self.step_indicator.set_step(idx)
        self.btn_prev.setEnabled(idx > 0)
        self.btn_next.setText("下一步" if idx < 2 else "完成")
        self.btn_next.setVisible(idx < 2)

    def _prev(self):
        idx = self.stack.currentIndex()
        if idx > 0:
            self.stack.setCurrentIndex(idx - 1)
            self._update_nav()

    def _next(self):
        idx = self.stack.currentIndex()
        if idx == 0:
            errors = self.step1.validate()
            if errors:
                QMessageBox.warning(self, "提示", "\n".join(errors))
                return
            if not self._load_old_data():
                return  # 加载失败，留在当前步骤
            self.stack.setCurrentIndex(1)
        elif idx == 1:
            # Step2 → Step3: 把当前数据传给 Step3 供预览
            paths = self.step1.get_paths()
            data = self.step2.collect_data()
            report = self.step2.collect_report()
            report.system_name = paths["project_name"]
            self.step3.set_context(paths, data, report)
            self.stack.setCurrentIndex(2)
        self._update_nav()

    def _load_old_data(self):
        """从旧文件加载数据到编辑器。返回 True 表示可以继续。"""
        paths = self.step1.get_paths()

        if paths["project_name"]:
            self.step2.b_name.setText(paths["project_name"])

        loaded_any = False

        # 加载旧备案表
        old_beian = paths["old_beian"]
        if old_beian and os.path.exists(old_beian):
            try:
                if old_beian.lower().endswith('.doc'):
                    from core.doc_converter import convert_doc_to_docx
                    converted = convert_doc_to_docx(old_beian)
                    if converted:
                        old_beian = converted
                    else:
                        QMessageBox.warning(
                            self, "格式转换",
                            ".doc 文件自动转换失败。\n"
                            "请手动用 Word 打开该文件，另存为 .docx 格式后重新选择。")
                        return False

                from core.doc_reader import read_beian_docx
                data = read_beian_docx(old_beian)
                self.step2.load_data(data)
                loaded_any = True
                if not paths["project_name"] and data.project_name:
                    self.step1.project_name.setText(data.project_name)
            except Exception as e:
                QMessageBox.warning(self, "读取旧备案表失败", str(e))
                return False

        # 加载旧定级报告
        old_report = paths["old_report"]
        if old_report and os.path.exists(old_report):
            try:
                from core.doc_reader import read_report_docx
                report = read_report_docx(old_report)
                self.step2.load_report(report)
                loaded_any = True
            except Exception as e:
                QMessageBox.warning(self, "读取旧定级报告失败", str(e))
                return False

        if loaded_any:
            auto_count = len(self.tracker.get_log())
            QMessageBox.information(
                self, "数据加载完成",
                f"已从旧文件自动填充 {auto_count} 个字段。\n\n"
                "以下内容需要手动确认或填写：\n"
                "  - 表四：新技术应用场景（传统系统选\"否\"跳过）\n"
                "  - 表五：提交材料情况（一般前两项\"有\"）\n"
                "  - 定级报告：网络拓扑图（需重新选择图片）\n\n"
                "其余字段已自动填充，蓝色底色标记。")

        return True

    def _generate(self):
        paths = self.step1.get_paths()
        data = self.step2.collect_data()
        report = self.step2.collect_report()
        report.system_name = paths["project_name"]
        self.step3.start_generate(paths, data, report)
