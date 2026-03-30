"""Step 1: 文件选择页"""

import os
import glob
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFileDialog, QGroupBox, QFormLayout
)
from PyQt6.QtCore import Qt


# 默认模版路径（项目自带）
DEFAULT_TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "templates"
)


class Step1FilesPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 快速选择：项目目录
        quick_group = QGroupBox("快速开始 — 选择旧项目目录，自动识别文件")
        quick_layout = QHBoxLayout(quick_group)
        self.project_dir_edit = QLineEdit()
        self.project_dir_edit.setPlaceholderText("选择包含旧备案表和旧定级报告的文件夹...")
        btn_scan = QPushButton("选择项目目录")
        btn_scan.setProperty("class", "primary")
        btn_scan.setFixedWidth(120)
        btn_scan.clicked.connect(self._scan_project_dir)
        quick_layout.addWidget(self.project_dir_edit)
        quick_layout.addWidget(btn_scan)
        layout.addWidget(quick_group)

        # 项目名称
        name_group = QGroupBox("项目信息")
        name_layout = QFormLayout(name_group)
        self.project_name = QLineEdit()
        self.project_name.setPlaceholderText("例如：乡宁焦煤物资采购平台")
        name_layout.addRow("项目名称：", self.project_name)
        layout.addWidget(name_group)

        # 新模版
        tpl_group = QGroupBox("新模版文件（已内置默认模版，一般无需修改）")
        tpl_layout = QFormLayout(tpl_group)
        self.beian_template = self._file_row(
            "新备案表模版", self._default_path("01-新备案表（领取备案证明时提交盖章件一式两份）.docx"))
        tpl_layout.addRow("备案表模版：", self.beian_template["row"])
        self.report_template = self._file_row(
            "新定级报告模版", self._default_path("02-定级报告.docx"))
        tpl_layout.addRow("定级报告模版：", self.report_template["row"])
        layout.addWidget(tpl_group)

        # 旧文件（可选）
        old_group = QGroupBox("旧文件（自动检测或手动选择）")
        old_layout = QFormLayout(old_group)
        self.old_beian = self._file_row("旧备案表 (.doc/.docx)", "")
        old_layout.addRow("旧备案表：", self.old_beian["row"])
        self.old_report = self._file_row("旧定级报告 (.docx)", "")
        old_layout.addRow("旧定级报告：", self.old_report["row"])
        layout.addWidget(old_group)

        # 输出目录
        out_group = QGroupBox("输出设置")
        out_layout = QFormLayout(out_group)
        self.output_dir = self._dir_row("输出目录")
        out_layout.addRow("输出目录：", self.output_dir["row"])
        layout.addWidget(out_group)

        layout.addStretch()

    def _scan_project_dir(self):
        """选择项目目录，自动扫描旧文件"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择旧项目目录")
        if not dir_path:
            return

        self.project_dir_edit.setText(dir_path)

        # 自动检测旧备案表（优先 .docx，其次 .doc）
        beian_found = ""
        for pattern in ["*备案表*.docx", "*备案表*.doc", "*新备案表*.docx"]:
            matches = glob.glob(os.path.join(dir_path, pattern))
            if matches:
                # 优先选文件名最短的（通常是主文件）
                beian_found = min(matches, key=len)
                break
        if beian_found:
            self.old_beian["edit"].setText(beian_found)

        # 自动检测旧定级报告
        report_found = ""
        for pattern in ["*定级报告*.docx", "*定级报告*.doc"]:
            matches = glob.glob(os.path.join(dir_path, pattern))
            if matches:
                report_found = min(matches, key=len)
                break
        if report_found:
            self.old_report["edit"].setText(report_found)

        # 输出目录设为同一位置
        self.output_dir["edit"].setText(dir_path)

        # 尝试从目录名或文件名猜测项目名
        if not self.project_name.text().strip():
            dir_name = os.path.basename(dir_path)
            # 如果找到备案表，从文件名提取
            if beian_found:
                fname = os.path.splitext(os.path.basename(beian_found))[0]
                for prefix in ["备案表_", "01-新备案表", "新备案表"]:
                    if prefix in fname:
                        name = fname.split(prefix)[-1].strip()
                        if name and "领取" not in name:
                            self.project_name.setText(name)
                            break
            # fallback 用目录名
            if not self.project_name.text().strip():
                self.project_name.setText(dir_name)

        # 显示检测结果
        found = []
        if beian_found:
            found.append(f"备案表: {os.path.basename(beian_found)}")
        if report_found:
            found.append(f"定级报告: {os.path.basename(report_found)}")
        if not found:
            found.append("未找到旧文件，可手动选择或直接填写")

        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, "扫描结果",
            "检测到以下文件：\n" + "\n".join(f"  {f}" for f in found))

    def _default_path(self, filename):
        path = os.path.join(DEFAULT_TEMPLATE_DIR, filename)
        return path if os.path.exists(path) else ""

    def _file_row(self, label, default=""):
        edit = QLineEdit(default)
        edit.setMinimumWidth(400)
        btn = QPushButton("浏览...")
        btn.setFixedWidth(70)
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(edit)
        h.addWidget(btn)
        btn.clicked.connect(lambda: self._browse_file(edit))
        return {"row": row, "edit": edit}

    def _dir_row(self, label):
        edit = QLineEdit()
        edit.setMinimumWidth(400)
        btn = QPushButton("浏览...")
        btn.setFixedWidth(70)
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(edit)
        h.addWidget(btn)
        btn.clicked.connect(lambda: self._browse_dir(edit))
        return {"row": row, "edit": edit}

    def _browse_file(self, edit):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "", "Word文档 (*.docx *.doc);;所有文件 (*)")
        if path:
            edit.setText(path)

    def _browse_dir(self, edit):
        path = QFileDialog.getExistingDirectory(self, "选择目录")
        if path:
            edit.setText(path)

    def get_paths(self):
        """返回所有路径"""
        return {
            "project_name": self.project_name.text().strip(),
            "beian_template": self.beian_template["edit"].text().strip(),
            "report_template": self.report_template["edit"].text().strip(),
            "old_beian": self.old_beian["edit"].text().strip(),
            "old_report": self.old_report["edit"].text().strip(),
            "output_dir": self.output_dir["edit"].text().strip(),
        }

    def validate(self):
        """验证必填项"""
        paths = self.get_paths()
        errors = []
        if not paths["project_name"]:
            errors.append("请输入项目名称")
        if not paths["beian_template"] or not os.path.exists(paths["beian_template"]):
            errors.append("请选择有效的备案表模版")
        if not paths["report_template"] or not os.path.exists(paths["report_template"]):
            errors.append("请选择有效的定级报告模版")
        if not paths["output_dir"]:
            errors.append("请选择输出目录")
        return errors
