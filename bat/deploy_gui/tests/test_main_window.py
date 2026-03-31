import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QSplitter

from deploy_gui.main_window import MainWindow, build_program_preset
from deploy_gui.models import ProjectConfig


app = QApplication.instance() or QApplication([])


def test_main_window_exposes_key_panels():
    window = MainWindow()

    assert window.windowTitle() == "通用部署器"
    assert window.findChild(type(window.project_list), "projectList") is not None
    assert window.findChild(type(window.plan_preview), "planPreview") is not None
    assert window.findChild(type(window.log_output), "logOutput") is not None
    assert window.findChild(QSplitter, "previewSplitter") is not None


def test_mode_switch_keeps_user_selected_mode():
    window = MainWindow()
    window.projects = [ProjectConfig(name="Demo", mode="zip")]
    window.current_index = 0
    window._fill_form(window.projects[0])

    window.mode_combo.setCurrentIndex(window.mode_combo.findData("git"))

    assert window.mode_combo.currentData() == "git"
    assert "repo_dir" in window.mode_edits
    assert "local_zip_path" not in window.mode_edits


def test_project_list_item_shows_mode_and_host_summary():
    window = MainWindow()
    window.projects = [
        ProjectConfig(name="Demo", mode="git", host="10.0.0.8"),
    ]

    window._load_projects()

    item_widget = window.project_list.itemWidget(window.project_list.item(0))
    labels = item_widget.findChildren(QLabel)
    texts = [label.text() for label in labels]

    assert "Demo" in texts
    assert "GIT" in texts
    assert any("10.0.0.8" in text for text in texts)


def test_program_preset_uses_expected_zip_defaults():
    project = build_program_preset()

    assert project.name == "Program"
    assert project.mode == "zip"
    assert project.local_project_dir.endswith("Program")
    assert project.remote_project_dir == "/opt/myapp"
    assert project.zip_settings.remote_zip_path == "/opt/Program.zip"


def test_left_sidebar_uses_compact_actions_without_summary_card():
    window = MainWindow()

    assert not hasattr(window, "project_name_summary")
    assert window.findChild(type(window.project_list), "projectList") is not None


def test_window_exposes_include_local_database_checkbox():
    window = MainWindow()

    assert window.include_local_db_check.text() == "压缩包含本地数据库"
