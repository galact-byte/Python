"""Step 3: 生成页 + Word 预览"""

import os
import tempfile
import traceback
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QTextEdit, QProgressBar, QHBoxLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal


class GenerateWorker(QThread):
    """后台生成文档"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str, list)  # success, msg, output_files

    def __init__(self, paths, data, report, temp_dir=None):
        super().__init__()
        self.paths = paths
        self.data = data
        self.report = report
        self.temp_dir = temp_dir  # 预览时用临时目录

    def run(self):
        try:
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            from core.doc_writer import generate_beian, generate_report

            out_dir = self.temp_dir or self.paths["output_dir"]
            os.makedirs(out_dir, exist_ok=True)
            name = self.paths["project_name"]
            output_files = []

            self.progress.emit("正在生成备案表...")
            beian_out = os.path.join(out_dir, f"备案表_{name}.docx")
            generate_beian(self.paths["beian_template"], beian_out, self.data)
            output_files.append(beian_out)
            self.progress.emit(f"备案表已生成: {beian_out}")

            self.progress.emit("正在生成定级报告...")
            report_out = os.path.join(out_dir, f"定级报告_{name}.docx")
            generate_report(
                self.paths["report_template"], report_out,
                self.report, name
            )
            output_files.append(report_out)
            self.progress.emit(f"定级报告已生成: {report_out}")

            self.finished.emit(True, "生成完成!", output_files)
        except Exception as e:
            self.finished.emit(False, f"生成失败: {e}\n{traceback.format_exc()}", [])


class Step3GeneratePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._output_files = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        title = QLabel("生成文档")
        title.setProperty("class", "stepTitle")
        layout.addWidget(title)

        desc = QLabel(
            "先点\"预览\"用 Word 查看效果，确认无误后再\"正式生成\"到输出目录。"
        )
        desc.setWordWrap(True)
        desc.setProperty("class", "hint")
        layout.addWidget(desc)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 日志
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setProperty("class", "changeLog")
        self.log.setMinimumHeight(180)
        layout.addWidget(self.log)

        # 按钮行 1：预览
        preview_row = QHBoxLayout()
        preview_row.addStretch()

        self.preview_beian_btn = QPushButton("预览备案表")
        self.preview_beian_btn.setFixedHeight(36)
        self.preview_beian_btn.setMinimumWidth(120)
        self.preview_beian_btn.clicked.connect(lambda: self._preview("beian"))
        preview_row.addWidget(self.preview_beian_btn)

        self.preview_report_btn = QPushButton("预览定级报告")
        self.preview_report_btn.setFixedHeight(36)
        self.preview_report_btn.setMinimumWidth(120)
        self.preview_report_btn.clicked.connect(lambda: self._preview("report"))
        preview_row.addWidget(self.preview_report_btn)

        preview_row.addStretch()
        layout.addLayout(preview_row)

        # 按钮行 2：正式生成
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.generate_btn = QPushButton("正式生成")
        self.generate_btn.setFixedHeight(40)
        self.generate_btn.setProperty("class", "primary")
        self.generate_btn.setMinimumWidth(140)
        btn_row.addWidget(self.generate_btn)

        self.open_dir_btn = QPushButton("打开输出目录")
        self.open_dir_btn.setFixedHeight(40)
        self.open_dir_btn.setVisible(False)
        btn_row.addWidget(self.open_dir_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addStretch()

    def set_context(self, paths, data, report):
        """保存生成上下文，供预览和正式生成使用"""
        self._paths = paths
        self._data = data
        self._report = report

    def _preview(self, doc_type):
        """预览：生成到临时目录，用 Word 打开"""
        if not hasattr(self, '_paths'):
            return

        self.log.clear()
        self.log.append(f"正在生成预览...")

        try:
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            from core.doc_writer import generate_beian, generate_report

            temp_dir = os.path.join(tempfile.gettempdir(), "dengbao_preview")
            os.makedirs(temp_dir, exist_ok=True)
            name = self._paths["project_name"]

            if doc_type == "beian":
                out_path = os.path.join(temp_dir, f"预览_备案表_{name}.docx")
                generate_beian(self._paths["beian_template"], out_path, self._data)
                self.log.append(f"备案表预览已生成，正在用 Word 打开...")
            else:
                out_path = os.path.join(temp_dir, f"预览_定级报告_{name}.docx")
                generate_report(
                    self._paths["report_template"], out_path,
                    self._report, name
                )
                self.log.append(f"定级报告预览已生成，正在用 Word 打开...")

            os.startfile(out_path)
            self.log.append("已打开 Word，请检查内容是否正确。")
            self.log.append("确认无误后点\"正式生成\"保存到输出目录。")

        except Exception as e:
            self.log.append(f"预览失败: {e}")

    def start_generate(self, paths, data, report):
        """正式生成"""
        self.set_context(paths, data, report)
        self.log.clear()
        self.log.append("正在生成到输出目录...")
        self.progress_bar.setVisible(True)
        self.generate_btn.setEnabled(False)

        self._worker = GenerateWorker(paths, data, report)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._output_dir = paths["output_dir"]
        self._worker.start()

    def _on_progress(self, msg):
        self.log.append(msg)

    def _on_finished(self, success, msg, files):
        self.progress_bar.setVisible(False)
        self.generate_btn.setEnabled(True)
        if success:
            self._output_files = files
            self.log.append(f"\n{msg}")
            for f in files:
                self.log.append(f"  {f}")
            self.open_dir_btn.setVisible(True)
            # 避免重复连接
            try:
                self.open_dir_btn.clicked.disconnect()
            except TypeError:
                pass
            self.open_dir_btn.clicked.connect(self._open_output)
        else:
            self.log.append(f"\n{msg}")

    def _open_output(self):
        if hasattr(self, '_output_dir') and self._output_dir:
            os.startfile(self._output_dir)
