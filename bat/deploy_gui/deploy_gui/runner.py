from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

from .models import CommandResult, DeployStep, DeploymentResult, ProjectConfig
from .packager import create_zip


LogFn = Callable[[str], None]


class DeploymentRunner:
    def __init__(self, ssh_service, log: LogFn | None = None):
        self.ssh_service = ssh_service
        self.log = log or (lambda _: None)
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    def run(self, project: ProjectConfig, steps: list[DeployStep]) -> DeploymentResult:
        for step in steps:
            if self._stopped:
                return DeploymentResult(False, step.name, "部署已停止")
            self.log(f"[开始] {step.name}")
            try:
                if step.side == "local":
                    result = self._run_local_step(project, step)
                elif step.side == "remote":
                    result = self.ssh_service.run_command(step.command)
                elif step.side == "upload":
                    result = self._run_upload_step(project, step)
                else:
                    return DeploymentResult(False, step.name, f"未知步骤类型: {step.side}")
            except Exception as exc:
                self.log(f"[异常] {step.name}: {exc}")
                return DeploymentResult(False, step.name, str(exc))

            self._emit_result(result)
            if not result.ok:
                return DeploymentResult(False, step.name, result.stderr or result.stdout or "步骤失败")
        return DeploymentResult(True, message="部署完成")

    def _run_local_step(self, project: ProjectConfig, step: DeployStep) -> CommandResult:
        if project.mode == "zip" and step.name == "本地打包 ZIP":
            source = Path(project.zip_settings.local_source_dir)
            target = Path(project.zip_settings.local_zip_path)
            create_zip(source, target)
            return CommandResult(step.command, 0, stdout=f"已生成 {target}", stderr="")

        completed = subprocess.run(
            step.command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=project.local_project_dir or None,
        )
        return CommandResult(step.command, completed.returncode, completed.stdout, completed.stderr)

    def _run_upload_step(self, project: ProjectConfig, step: DeployStep) -> CommandResult:
        local_zip = Path(project.zip_settings.local_zip_path)
        remote_zip = project.zip_settings.remote_zip_path
        self.ssh_service.upload_file(local_zip, remote_zip)
        return CommandResult(step.command, 0, stdout=f"已上传到 {remote_zip}", stderr="")

    def _emit_result(self, result: CommandResult) -> None:
        self.log(f"[命令] {result.command}")
        if result.stdout.strip():
            self.log(result.stdout.rstrip())
        if result.stderr.strip():
            self.log(result.stderr.rstrip())
        self.log(f"[结果] exit={result.exit_code}")
