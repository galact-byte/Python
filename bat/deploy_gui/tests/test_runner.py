from deploy_gui.models import CommandResult, DeployStep, ProjectConfig
from deploy_gui.runner import DeploymentRunner


class FakeSSHService:
    def __init__(self):
        self.commands = []

    def run_command(self, command: str) -> CommandResult:
        self.commands.append(command)
        if command == "bad":
            return CommandResult(command, 1, "", "failed")
        return CommandResult(command, 0, "ok", "")

    def upload_file(self, local_path, remote_path) -> None:
        return None


def test_runner_stops_on_failed_step(tmp_path):
    ssh = FakeSSHService()
    runner = DeploymentRunner(ssh)
    project = ProjectConfig(name="Demo", mode="custom", local_project_dir=str(tmp_path))
    result = runner.run(project, [DeployStep("ok", "remote", "good"), DeployStep("bad", "remote", "bad")])
    assert result.success is False
    assert result.failed_step == "bad"
