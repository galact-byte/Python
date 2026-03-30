from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .config_store import ConfigStore
from .models import CustomSettings, DeployOptions, GitSettings, ProjectConfig, ZipSettings
from .planner import build_plan
from .runner import DeploymentRunner
from .ssh_client import SSHConfig, SSHService


CONFIG_PATH = Path.home() / ".deploy_gui" / "projects.json"
PROGRAM_LOCAL_DIR = r"E:\vsCode\Programs\Web\Work\Program"
PROGRAM_ZIP_PATH = r"E:\vsCode\Programs\Web\Work\Program.zip"


def build_program_preset() -> ProjectConfig:
    return ProjectConfig(
        name="Program",
        mode="zip",
        local_project_dir=PROGRAM_LOCAL_DIR,
        remote_project_dir="/opt/myapp",
        zip_settings=ZipSettings(
            local_source_dir=PROGRAM_LOCAL_DIR,
            local_zip_path=PROGRAM_ZIP_PATH,
            remote_zip_path="/opt/Program.zip",
            remote_extract_dir="/tmp/newapp",
            remote_target_dir="/opt/myapp",
        ),
        options=DeployOptions(
            backup_database=True,
            restore_database=True,
            install_backend_deps=True,
            build_frontend=True,
            restart_backend=True,
            reload_nginx=False,
            health_check=True,
        ),
    )

WINDOW_STYLESHEET = """
QMainWindow {
    background: #edf2f7;
}
QWidget {
    color: #102a43;
    font-family: 'Microsoft YaHei UI', 'Segoe UI', sans-serif;
    font-size: 13px;
}
QFrame#heroCard,
QFrame[card="true"],
QGroupBox {
    background: #ffffff;
    border: 1px solid #d9e2ec;
    border-radius: 20px;
}
QFrame#heroCard {
    border: 1px solid #c7d2fe;
    background: #f8fbff;
}
QLabel[role="heroTitle"] {
    font-size: 28px;
    font-weight: 700;
    color: #102a43;
}
QLabel[role="heroSubtitle"] {
    color: #52606d;
    font-size: 13px;
}
QLabel#modeBadge {
    background: #e0f2fe;
    color: #075985;
    border: 1px solid #bae6fd;
    border-radius: 999px;
    padding: 6px 14px;
    font-weight: 700;
}
QLabel[role="sectionTitle"] {
    font-size: 16px;
    font-weight: 700;
    color: #102a43;
}
QLabel[role="sectionHint"] {
    color: #7b8794;
    font-size: 12px;
}
QLabel[role="toolbarTitle"] {
    color: #486581;
    font-size: 11px;
    font-weight: 700;
}
QLabel[role="eyebrow"] {
    color: #627d98;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.5px;
}
QFrame#projectActionCard {
    background: #eef5ff;
    border: 1px solid #dbe7ff;
    border-radius: 16px;
}
QFrame#projectSidebar {
    background: #f5f9ff;
    border: 1px solid #dbe7ff;
    border-radius: 24px;
}
QFrame#projectListItem {
    background: #ffffff;
    border: 1px solid #dbe7ff;
    border-radius: 16px;
}
QLabel[role="itemTitle"] {
    font-size: 14px;
    font-weight: 700;
    color: #102a43;
}
QLabel[role="itemMeta"] {
    color: #7b8794;
    font-size: 12px;
}
QLabel[role="itemBadge"] {
    background: #eff6ff;
    color: #1d4ed8;
    border: 1px solid #bfdbfe;
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
}
QListWidget#projectList {
    background: #f7fbff;
    border: 1px solid #dbe7ff;
    border-radius: 20px;
    padding: 12px;
    outline: none;
}
QListWidget#projectList::item {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 16px;
    padding: 4px;
    margin: 8px 0;
}
QListWidget#projectList::item:selected {
    background: #dbeafe;
    border: 1px solid #60a5fa;
    color: #0f172a;
}
QListWidget#projectList::item:hover {
    background: #eff6ff;
}
QLineEdit,
QComboBox,
QSpinBox,
QPlainTextEdit {
    background: #f8fafc;
    border: 1px solid #cbd2d9;
    border-radius: 12px;
    padding: 10px 12px;
    selection-background-color: #bfdbfe;
}
QLineEdit:focus,
QComboBox:focus,
QSpinBox:focus,
QPlainTextEdit:focus {
    border: 1px solid #3b82f6;
    background: #ffffff;
}
QComboBox::drop-down {
    border: none;
    width: 28px;
}
QGroupBox {
    margin-top: 12px;
    padding: 18px 16px 16px 16px;
    font-weight: 700;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
    color: #243b53;
}
QCheckBox {
    spacing: 8px;
    color: #243b53;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 6px;
    border: 1px solid #9fb3c8;
    background: #ffffff;
}
QCheckBox::indicator:checked {
    background: #2563eb;
    border: 1px solid #2563eb;
}
QPushButton {
    min-height: 42px;
    background: #ffffff;
    border: 1px solid #cbd2d9;
    border-radius: 12px;
    padding: 10px 16px;
    font-weight: 600;
}
QPushButton:hover {
    background: #f8fafc;
    border-color: #9fb3c8;
}
QPushButton[variant="primary"] {
    background: #2563eb;
    color: #ffffff;
    border: 1px solid #2563eb;
}
QPushButton[variant="primary"]:hover {
    background: #1d4ed8;
    border-color: #1d4ed8;
}
QPushButton[variant="accent"] {
    background: #0f766e;
    color: #ffffff;
    border: 1px solid #0f766e;
}
QPushButton[variant="accent"]:hover {
    background: #115e59;
    border-color: #115e59;
}
QPushButton[variant="danger"] {
    color: #b42318;
    border: 1px solid #f1b7ad;
    background: #fff5f3;
}
QPushButton[variant="danger"]:hover {
    background: #ffe4e0;
}
QPlainTextEdit#planPreview {
    background: #f8fafc;
    color: #102a43;
}
QPlainTextEdit#logOutput {
    background: #0f172a;
    color: #dbeafe;
    border: 1px solid #1e293b;
    font-family: 'Cascadia Code', 'Consolas', monospace;
}
QScrollArea {
    border: none;
    background: transparent;
}
QSplitter::handle {
    background: transparent;
    width: 10px;
}
QPushButton[compact="true"] {
    min-height: 32px;
    padding: 4px 10px;
    border-radius: 10px;
}
QDialog {
    background: #f8fbff;
}
QFrame[dialogCard="true"] {
    background: #ffffff;
    border: 1px solid #dbe7ff;
    border-radius: 18px;
}
"""


class DeployWorker(QThread):
    log_emitted = pyqtSignal(str)
    finished_result = pyqtSignal(bool, str)

    def __init__(self, project: ProjectConfig, password: str, parent=None):
        super().__init__(parent)
        self.project = project
        self.password = password
        self._runner: DeploymentRunner | None = None

    def run(self) -> None:
        ssh = SSHService(
            SSHConfig(
                host=self.project.host,
                port=self.project.port,
                username=self.project.username,
                password=self.password,
            )
        )
        try:
            self.log_emitted.emit("[连接] 正在连接服务器...")
            ssh.connect()
            self.log_emitted.emit("[连接] SSH 连接成功")
            self._runner = DeploymentRunner(ssh, log=self.log_emitted.emit)
            result = self._runner.run(self.project, build_plan(self.project))
            self.finished_result.emit(result.success, result.message or result.failed_step)
        except Exception as exc:
            self.finished_result.emit(False, str(exc))
        finally:
            ssh.close()

    def stop(self) -> None:
        if self._runner:
            self._runner.stop()


class TextPromptDialog(QDialog):
    def __init__(self, title: str, label: str, parent=None, *, password: bool = False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(360)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)

        card = QFrame()
        card.setProperty("dialogCard", "true")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        layout.addWidget(QLabel(label))
        self.input_edit = QLineEdit()
        if password:
            self.input_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.input_edit)

        buttons = QDialogButtonBox()
        ok_button = QPushButton("确定")
        ok_button.setProperty("variant", "primary")
        cancel_button = QPushButton("取消")
        buttons.addButton(ok_button, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(cancel_button, QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        outer.addWidget(card)

    def value(self) -> str:
        return self.input_edit.text().strip()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("通用部署器")
        self.resize(1520, 920)
        self.setMinimumSize(1320, 780)
        self.setStyleSheet(WINDOW_STYLESHEET)

        self.store = ConfigStore(CONFIG_PATH)
        self.projects = self.store.load_all()
        if not self.projects:
            self.projects = [build_program_preset()]
        self.current_index = -1
        self.password = ""
        self.worker: DeployWorker | None = None
        self.mode_edits: dict[str, QLineEdit] = {}
        self._is_loading_project = False

        self._build_ui()
        self._load_projects()
        self._update_mode_badge()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(18)
        root_layout.addWidget(self._build_header_card())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_project_panel())
        splitter.addWidget(self._build_form_panel())
        splitter.addWidget(self._build_preview_panel())
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([440, 640, 560])
        root_layout.addWidget(splitter, 1)
        self.setCentralWidget(root)

    def _build_header_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("heroCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(20)

        text_col = QVBoxLayout()
        eyebrow = self._make_label("DEPLOYMENT WORKBENCH", "eyebrow")
        title = self._make_label("部署工作台", "heroTitle")
        subtitle = self._make_label("把项目配置、执行计划和远端日志放在同一视图里，减少来回切换。", "heroSubtitle")
        text_col.addWidget(eyebrow)
        text_col.addWidget(title)
        text_col.addWidget(subtitle)
        layout.addLayout(text_col, 1)

        status_col = QVBoxLayout()
        status_col.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.mode_badge = QLabel()
        self.mode_badge.setObjectName("modeBadge")
        summary = self._make_label("默认浅色界面，日志区保持深色终端风格", "sectionHint")
        summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        status_col.addWidget(self.mode_badge, 0, Qt.AlignmentFlag.AlignRight)
        status_col.addWidget(summary)
        layout.addLayout(status_col)
        return card

    def _build_project_panel(self) -> QWidget:
        card, layout = self._create_card(
            "项目导航",
            "集中管理多个部署配置，便于快速切换和复制模板。",
        )
        card.setObjectName("projectSidebar")
        layout.setSpacing(10)

        action_card = QFrame()
        action_card.setObjectName("projectActionCard")
        action_card.setMaximumHeight(88)
        action_layout = QVBoxLayout(action_card)
        action_layout.setContentsMargins(10, 10, 10, 10)
        action_layout.setSpacing(6)
        action_layout.addWidget(self._make_label("工具栏", "toolbarTitle"))

        tool_row = QHBoxLayout()
        tool_row.setSpacing(6)
        add_btn = self._create_button("新增", "primary", self._add_project, compact=True)
        preset_btn = self._create_button("Program 预设", "accent", self._add_program_preset, compact=True)
        copy_btn = self._create_button("复制", None, self._copy_project, compact=True)
        delete_btn = self._create_button("删除", "danger", self._delete_project, compact=True)
        tool_row.addWidget(preset_btn, 1)
        tool_row.addWidget(add_btn)
        tool_row.addWidget(copy_btn)
        tool_row.addWidget(delete_btn)
        action_layout.addLayout(tool_row)
        layout.addWidget(action_card)

        list_header = QHBoxLayout()
        list_header.setContentsMargins(4, 2, 4, 0)
        list_header.addWidget(self._make_label("项目列表", "sectionTitle"))
        layout.addLayout(list_header)

        self.project_list = QListWidget()
        self.project_list.setObjectName("projectList")
        self.project_list.setMinimumHeight(360)
        self.project_list.currentRowChanged.connect(self._on_project_selected)
        layout.addWidget(self.project_list, 1)
        return card

    def _build_form_panel(self) -> QWidget:
        card, layout = self._create_card(
            "部署配置",
            "按模式组织连接、路径和部署选项，保持单页可读。",
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(14)

        basic_group = QGroupBox("基础配置")
        basic_form = QFormLayout(basic_group)
        basic_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        basic_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        basic_form.setSpacing(12)
        self.name_edit = QLineEdit()
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("ZIP 上传部署", "zip")
        self.mode_combo.addItem("Git 拉取部署", "git")
        self.mode_combo.addItem("自定义命令部署", "custom")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.host_edit = QLineEdit()
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(22)
        self.user_edit = QLineEdit()
        self.local_project_edit = QLineEdit()
        self.remote_project_edit = QLineEdit()
        browse_btn = self._create_button("选择目录", None, self._browse_local_project)
        local_row = QHBoxLayout()
        local_row.setSpacing(10)
        local_row.addWidget(self.local_project_edit)
        local_row.addWidget(browse_btn)
        basic_form.addRow("项目名称", self.name_edit)
        basic_form.addRow("部署模式", self.mode_combo)
        basic_form.addRow("服务器 IP", self.host_edit)
        basic_form.addRow("SSH 端口", self.port_spin)
        basic_form.addRow("用户名", self.user_edit)
        basic_form.addRow("本地项目目录", self._wrap_layout(local_row))
        basic_form.addRow("远端项目目录", self.remote_project_edit)
        content_layout.addWidget(basic_group)

        self.mode_group = QGroupBox("模式配置")
        self.mode_form = QFormLayout(self.mode_group)
        self.mode_form.setSpacing(12)
        content_layout.addWidget(self.mode_group)

        options_group = QGroupBox("部署选项")
        options_grid = QGridLayout(options_group)
        options_grid.setHorizontalSpacing(12)
        options_grid.setVerticalSpacing(14)
        self.backup_db_check = QCheckBox("备份数据库")
        self.restore_db_check = QCheckBox("恢复数据库")
        self.install_deps_check = QCheckBox("安装后端依赖")
        self.build_frontend_check = QCheckBox("前端构建")
        self.restart_backend_check = QCheckBox("重启后端")
        self.reload_nginx_check = QCheckBox("重载 Nginx")
        self.health_check_check = QCheckBox("健康检查")
        checks = [
            self.backup_db_check,
            self.restore_db_check,
            self.install_deps_check,
            self.build_frontend_check,
            self.restart_backend_check,
            self.reload_nginx_check,
            self.health_check_check,
        ]
        for idx, check in enumerate(checks):
            options_grid.addWidget(check, idx // 2, idx % 2)
        content_layout.addWidget(options_group)

        action_group = QGroupBox("执行操作")
        action_layout = QHBoxLayout(action_group)
        action_layout.setSpacing(10)
        save_btn = self._create_button("保存配置", "primary", self._save_current_project)
        test_btn = self._create_button("测试连接", None, self._test_connection)
        plan_btn = self._create_button("生成计划", None, self._generate_plan)
        deploy_btn = self._create_button("开始部署", "accent", self._start_deploy)
        stop_btn = self._create_button("停止", "danger", self._stop_deploy)
        action_layout.addWidget(save_btn)
        action_layout.addWidget(test_btn)
        action_layout.addWidget(plan_btn)
        action_layout.addWidget(deploy_btn)
        action_layout.addWidget(stop_btn)
        content_layout.addWidget(action_group)
        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        self._refresh_mode_fields()
        return card

    def _build_preview_panel(self) -> QWidget:
        card, layout = self._create_card(
            "执行视图",
            "先看计划，再看实时日志；同一列里完成部署闭环。",
        )

        layout.addWidget(self._make_label("执行计划", "sectionTitle"))
        self.plan_preview = QPlainTextEdit()
        self.plan_preview.setObjectName("planPreview")
        self.plan_preview.setReadOnly(True)
        self.plan_preview.setPlaceholderText("生成计划后，这里会列出每一步将要执行的命令。")
        layout.addWidget(self.plan_preview, 1)

        layout.addWidget(self._make_label("远端日志", "sectionTitle"))
        self.log_output = QPlainTextEdit()
        self.log_output.setObjectName("logOutput")
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("开始部署后，这里会持续输出连接、执行和失败信息。")
        layout.addWidget(self.log_output, 2)
        return card

    def _create_card(self, title: str, hint: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setProperty("card", "true")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        layout.addWidget(self._make_label("WORKSPACE", "eyebrow"))
        layout.addWidget(self._make_label(title, "sectionTitle"))
        hint_label = self._make_label(hint, "sectionHint")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)
        return card, layout

    def _make_label(self, text: str, role: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("role", role)
        return label

    def _mode_label(self, mode: str) -> str:
        labels = {
            "zip": "ZIP 上传部署",
            "git": "Git 拉取部署",
            "custom": "自定义命令部署",
        }
        return labels.get(mode, mode)

    def _mode_badge_label(self, mode: str) -> str:
        labels = {
            "zip": "ZIP",
            "git": "GIT",
            "custom": "命令",
        }
        return labels.get(mode, mode)

    def _build_project_item_widget(self, project: ProjectConfig) -> QWidget:
        widget = QFrame()
        widget.setObjectName("projectListItem")
        widget.setMinimumHeight(92)

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(10)
        top_row.addWidget(self._make_label(project.name or "未命名项目", "itemTitle"), 1)
        top_row.addWidget(self._make_label(self._mode_badge_label(project.mode), "itemBadge"), 0, Qt.AlignmentFlag.AlignRight)

        host = project.host or "未填写服务器"
        remote_dir = project.remote_project_dir or "未填写远端目录"
        layout.addLayout(top_row)
        layout.addWidget(self._make_label(f"主机: {host}", "itemMeta"))
        layout.addWidget(self._make_label(f"目录: {remote_dir}", "itemMeta"))
        return widget

    def _create_button(self, text: str, variant: str | None, handler, compact: bool = False) -> QPushButton:
        button = QPushButton(text)
        if variant:
            button.setProperty("variant", variant)
        if compact:
            button.setProperty("compact", "true")
        button.clicked.connect(handler)
        return button

    def _wrap_layout(self, layout) -> QWidget:
        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def _on_mode_changed(self) -> None:
        if self._is_loading_project:
            return
        self._refresh_mode_fields()
        self._update_mode_badge()

    def _update_mode_badge(self) -> None:
        labels = {
            "zip": "ZIP 上传模式",
            "git": "Git 拉取模式",
            "custom": "自定义命令模式",
        }
        self.mode_badge.setText(labels.get(self.mode_combo.currentData(), "部署模式"))

    def _refresh_mode_fields(self) -> None:
        while self.mode_form.rowCount():
            self.mode_form.removeRow(0)
        mode = self.mode_combo.currentData()
        self.mode_edits = {}

        if mode == "zip":
            fields = [
                ("本地源目录", "local_source_dir"),
                ("本地 ZIP 路径", "local_zip_path"),
                ("远端 ZIP 路径", "remote_zip_path"),
                ("远端解压目录", "remote_extract_dir"),
                ("远端覆盖目录", "remote_target_dir"),
            ]
        elif mode == "git":
            fields = [
                ("仓库目录", "repo_dir"),
                ("分支", "branch"),
                ("拉取前命令(;分隔)", "pre_pull_commands"),
                ("拉取后命令(;分隔)", "post_pull_commands"),
            ]
        else:
            fields = [
                ("本地命令(;分隔)", "local_commands"),
                ("远端命令(;分隔)", "remote_commands"),
            ]

        for label, key in fields:
            edit = QLineEdit()
            self.mode_edits[key] = edit
            self.mode_form.addRow(label, edit)

    def _load_projects(self) -> None:
        self.project_list.clear()
        for project in self.projects:
            widget = self._build_project_item_widget(project)
            item = QListWidgetItem()
            item.setSizeHint(widget.sizeHint())
            self.project_list.addItem(item)
            self.project_list.setItemWidget(item, widget)
        if self.projects:
            self.project_list.setCurrentRow(0)

    def _on_project_selected(self, index: int) -> None:
        self.current_index = index
        if 0 <= index < len(self.projects):
            self._fill_form(self.projects[index])

    def _fill_form(self, project: ProjectConfig) -> None:
        self._is_loading_project = True
        self.name_edit.setText(project.name)
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(project.mode)))
        self._refresh_mode_fields()
        self.host_edit.setText(project.host)
        self.port_spin.setValue(project.port)
        self.user_edit.setText(project.username)
        self.local_project_edit.setText(project.local_project_dir)
        self.remote_project_edit.setText(project.remote_project_dir)

        if project.mode == "zip":
            data = project.zip_settings
        elif project.mode == "git":
            data = project.git_settings
        else:
            data = project.custom_settings

        for key, widget in self.mode_edits.items():
            value = getattr(data, key, "")
            if isinstance(value, list):
                value = "; ".join(value)
            widget.setText(str(value))

        options = project.options
        self.backup_db_check.setChecked(options.backup_database)
        self.restore_db_check.setChecked(options.restore_database)
        self.install_deps_check.setChecked(options.install_backend_deps)
        self.build_frontend_check.setChecked(options.build_frontend)
        self.restart_backend_check.setChecked(options.restart_backend)
        self.reload_nginx_check.setChecked(options.reload_nginx)
        self.health_check_check.setChecked(options.health_check)
        self._is_loading_project = False
        self._update_mode_badge()

    def _collect_form(self) -> ProjectConfig:
        mode = self.mode_combo.currentData()
        options = DeployOptions(
            backup_database=self.backup_db_check.isChecked(),
            restore_database=self.restore_db_check.isChecked(),
            install_backend_deps=self.install_deps_check.isChecked(),
            build_frontend=self.build_frontend_check.isChecked(),
            restart_backend=self.restart_backend_check.isChecked(),
            reload_nginx=self.reload_nginx_check.isChecked(),
            health_check=self.health_check_check.isChecked(),
        )

        project = ProjectConfig(
            name=self.name_edit.text().strip() or "未命名项目",
            mode=mode,
            host=self.host_edit.text().strip(),
            port=self.port_spin.value(),
            username=self.user_edit.text().strip(),
            local_project_dir=self.local_project_edit.text().strip(),
            remote_project_dir=self.remote_project_edit.text().strip(),
            options=options,
        )

        if mode == "zip":
            project.zip_settings = ZipSettings(
                local_source_dir=self.mode_edits["local_source_dir"].text().strip(),
                local_zip_path=self.mode_edits["local_zip_path"].text().strip(),
                remote_zip_path=self.mode_edits["remote_zip_path"].text().strip(),
                remote_extract_dir=self.mode_edits["remote_extract_dir"].text().strip(),
                remote_target_dir=self.mode_edits["remote_target_dir"].text().strip(),
            )
        elif mode == "git":
            project.git_settings = GitSettings(
                repo_dir=self.mode_edits["repo_dir"].text().strip(),
                branch=self.mode_edits["branch"].text().strip() or "main",
                pre_pull_commands=self._split_commands(self.mode_edits["pre_pull_commands"].text()),
                post_pull_commands=self._split_commands(self.mode_edits["post_pull_commands"].text()),
            )
        else:
            project.custom_settings = CustomSettings(
                local_commands=self._split_commands(self.mode_edits["local_commands"].text()),
                remote_commands=self._split_commands(self.mode_edits["remote_commands"].text()),
            )
        return project

    def _split_commands(self, raw: str) -> list[str]:
        return [part.strip() for part in raw.split(";") if part.strip()]

    def _save_current_project(self) -> None:
        project = self._collect_form()
        if self.current_index == -1:
            self.projects.append(project)
            self.current_index = len(self.projects) - 1
        else:
            self.projects[self.current_index] = project
        self.store.save_all(self.projects)
        self._load_projects()
        self.project_list.setCurrentRow(self.current_index)
        QMessageBox.information(self, "保存成功", "项目配置已保存。")

    def _add_program_preset(self) -> None:
        project = build_program_preset()
        existing_names = {item.name for item in self.projects}
        if project.name in existing_names:
            suffix = 2
            while f"{project.name}-{suffix}" in existing_names:
                suffix += 1
            project.name = f"{project.name}-{suffix}"
        self.projects.append(project)
        self.store.save_all(self.projects)
        self._load_projects()
        self.project_list.setCurrentRow(len(self.projects) - 1)

    def _add_project(self) -> None:
        dialog = TextPromptDialog("新增项目", "项目名称", self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name = dialog.value()
        if not name:
            return
        self.projects.append(ProjectConfig(name=name, mode="zip"))
        self.store.save_all(self.projects)
        self._load_projects()
        self.project_list.setCurrentRow(len(self.projects) - 1)

    def _copy_project(self) -> None:
        if not (0 <= self.current_index < len(self.projects)):
            return
        source = self._collect_form()
        source.name = f"{source.name}-副本"
        self.projects.append(source)
        self.store.save_all(self.projects)
        self._load_projects()
        self.project_list.setCurrentRow(len(self.projects) - 1)

    def _delete_project(self) -> None:
        if not (0 <= self.current_index < len(self.projects)):
            return
        del self.projects[self.current_index]
        self.store.save_all(self.projects)
        self._load_projects()
        self.plan_preview.clear()
        self.log_output.clear()

    def _browse_local_project(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择本地项目目录", self.local_project_edit.text() or os.getcwd())
        if path:
            self.local_project_edit.setText(path)

    def _generate_plan(self) -> None:
        project = self._collect_form()
        steps = build_plan(project)
        lines = [f"{idx + 1}. [{step.side}] {step.name}: {step.command}" for idx, step in enumerate(steps)]
        self.plan_preview.setPlainText("\n".join(lines) if lines else "当前配置未生成任何步骤。")

    def _ensure_password(self) -> bool:
        dialog = TextPromptDialog("SSH 密码", "请输入服务器密码", self, password=True)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        password = dialog.value()
        if not password:
            return False
        self.password = password
        return True

    def _test_connection(self) -> None:
        project = self._collect_form()
        if not self._ensure_password():
            return
        try:
            ssh = SSHService(SSHConfig(project.host, project.port, project.username, self.password))
            ssh.connect()
            result = ssh.test_connection()
            ssh.close()
            QMessageBox.information(self, "连接成功", result.stdout.strip() or "SSH 连接测试通过。")
        except Exception as exc:
            QMessageBox.critical(self, "连接失败", str(exc))

    def _start_deploy(self) -> None:
        project = self._collect_form()
        self._generate_plan()
        if not self._ensure_password():
            return
        self.log_output.clear()
        self.worker = DeployWorker(project, self.password, self)
        self.worker.log_emitted.connect(self._append_log)
        self.worker.finished_result.connect(self._on_deploy_finished)
        self.worker.start()

    def _stop_deploy(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self._append_log("[停止] 已请求停止部署。")

    def _append_log(self, text: str) -> None:
        self.log_output.appendPlainText(text)

    def _on_deploy_finished(self, success: bool, message: str) -> None:
        if success:
            QMessageBox.information(self, "部署完成", message or "部署完成。")
        else:
            QMessageBox.critical(self, "部署失败", message or "部署失败。")


def main() -> int:
    app = QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
