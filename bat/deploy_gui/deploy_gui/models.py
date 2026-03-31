from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal


DeployMode = Literal["zip", "git", "custom"]
StepSide = Literal["local", "remote", "upload"]


@dataclass
class ZipSettings:
    local_source_dir: str = ""
    local_zip_path: str = ""
    remote_zip_path: str = ""
    remote_extract_dir: str = ""
    remote_target_dir: str = ""


@dataclass
class GitSettings:
    repo_dir: str = ""
    branch: str = "main"
    pre_pull_commands: list[str] = field(default_factory=list)
    post_pull_commands: list[str] = field(default_factory=list)


@dataclass
class CustomSettings:
    local_commands: list[str] = field(default_factory=list)
    remote_commands: list[str] = field(default_factory=list)


@dataclass
class DeployOptions:
    backup_database: bool = False
    restore_database: bool = False
    include_local_database_in_zip: bool = False
    install_backend_deps: bool = False
    build_frontend: bool = False
    restart_backend: bool = False
    reload_nginx: bool = False
    health_check: bool = False
    backend_requirements_path: str = "backend/requirements.txt"
    frontend_dir: str = "frontend"
    backend_service_name: str = "myapp-backend"
    health_check_url: str = "http://127.0.0.1:8000/health"
    database_path: str = "backend/project_completion.db"
    database_backup_path: str = "/tmp/project_completion.db.bak"


@dataclass
class ProjectConfig:
    name: str
    mode: DeployMode
    host: str = ""
    port: int = 22
    username: str = ""
    local_project_dir: str = ""
    remote_project_dir: str = ""
    zip_settings: ZipSettings = field(default_factory=ZipSettings)
    git_settings: GitSettings = field(default_factory=GitSettings)
    custom_settings: CustomSettings = field(default_factory=CustomSettings)
    options: DeployOptions = field(default_factory=DeployOptions)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectConfig":
        payload = dict(data)
        payload["zip_settings"] = ZipSettings(**payload.get("zip_settings", {}))
        payload["git_settings"] = GitSettings(**payload.get("git_settings", {}))
        payload["custom_settings"] = CustomSettings(**payload.get("custom_settings", {}))
        payload["options"] = DeployOptions(**payload.get("options", {}))
        return cls(**payload)


@dataclass
class DeployStep:
    name: str
    side: StepSide
    command: str
    risky: bool = False
    enabled: bool = True


@dataclass
class CommandResult:
    command: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


@dataclass
class DeploymentResult:
    success: bool
    failed_step: str = ""
    message: str = ""
