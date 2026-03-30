from deploy_gui.models import ProjectConfig
from deploy_gui.planner import build_plan


def test_zip_mode_generates_upload_and_remote_steps():
    project = ProjectConfig(name="Demo", mode="zip")
    project.zip_settings.local_zip_path = "Program.zip"
    project.zip_settings.remote_zip_path = "/opt/Program.zip"
    project.zip_settings.remote_extract_dir = "/tmp/newapp"
    project.zip_settings.remote_target_dir = "/opt/myapp"
    steps = build_plan(project)
    assert any(step.side == "upload" for step in steps)
    assert any(step.side == "remote" for step in steps)
