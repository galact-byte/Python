from __future__ import annotations

from pathlib import PurePosixPath

from .models import DeployStep, ProjectConfig


def _append_option_steps(steps: list[DeployStep], project: ProjectConfig) -> None:
    options = project.options
    remote_root = PurePosixPath(project.remote_project_dir) if project.remote_project_dir else PurePosixPath(".")

    if options.backup_database:
        source = remote_root / PurePosixPath(options.database_path)
        backup = PurePosixPath(options.database_backup_path)
        steps.append(DeployStep("备份数据库", "remote", f"cp {source.as_posix()} {backup.as_posix()}", risky=True))
    if options.restore_database:
        source = PurePosixPath(options.database_backup_path)
        target = remote_root / PurePosixPath(options.database_path)
        steps.append(DeployStep("恢复数据库", "remote", f"cp {source.as_posix()} {target.as_posix()}", risky=True))
    if options.install_backend_deps:
        req = remote_root / PurePosixPath(options.backend_requirements_path)
        steps.append(DeployStep("安装后端依赖", "remote", f"python3 -m pip install -r {req.as_posix()}"))
    if options.build_frontend:
        frontend_dir = remote_root / PurePosixPath(options.frontend_dir)
        steps.append(DeployStep("前端构建", "remote", f"cd {frontend_dir.as_posix()} && npm run build"))
    if options.restart_backend:
        steps.append(DeployStep("重启后端服务", "remote", f"systemctl restart {project.options.backend_service_name}", risky=True))
    if options.reload_nginx:
        steps.append(DeployStep("重载 Nginx", "remote", "systemctl reload nginx", risky=True))
    if options.health_check:
        steps.append(DeployStep("健康检查", "remote", f"curl -f {project.options.health_check_url}"))


def build_plan(project: ProjectConfig) -> list[DeployStep]:
    steps: list[DeployStep] = []

    if project.mode == "zip":
        settings = project.zip_settings
        source_dir = settings.local_source_dir or "<本地源目录>"
        zip_path = settings.local_zip_path or "<生成 ZIP>"
        steps.append(DeployStep("本地打包 ZIP", "local", f"压缩 {source_dir} -> {zip_path}"))
        steps.append(DeployStep("上传 ZIP", "upload", settings.remote_zip_path or "<上传 ZIP>"))
        steps.append(
            DeployStep(
                "远端解压覆盖",
                "remote",
                (
                    f"mkdir -p {settings.remote_extract_dir} && "
                    f"unzip -o {settings.remote_zip_path} -d {settings.remote_extract_dir} && "
                    f"cp -rf {settings.remote_extract_dir.rstrip('/')}/Program/* {settings.remote_target_dir}"
                ),
                risky=True,
            )
        )
    elif project.mode == "git":
        settings = project.git_settings
        for command in settings.pre_pull_commands:
            if command.strip():
                steps.append(DeployStep("拉取前命令", "remote", command.strip()))
        branch = settings.branch or "main"
        steps.append(DeployStep("Git 拉取", "remote", f"cd {settings.repo_dir} && git pull origin {branch}"))
        for command in settings.post_pull_commands:
            if command.strip():
                steps.append(DeployStep("拉取后命令", "remote", command.strip()))
    elif project.mode == "custom":
        settings = project.custom_settings
        for command in settings.local_commands:
            if command.strip():
                steps.append(DeployStep("本地命令", "local", command.strip()))
        for command in settings.remote_commands:
            if command.strip():
                steps.append(DeployStep("远端命令", "remote", command.strip()))

    _append_option_steps(steps, project)
    return [step for step in steps if step.enabled]
