from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import paramiko

from .models import CommandResult


@dataclass
class SSHConfig:
    host: str
    port: int
    username: str
    password: str


class SSHService:
    def __init__(self, config: SSHConfig):
        self.config = config
        self.client: paramiko.SSHClient | None = None

    def connect(self) -> None:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=self.config.host,
            port=self.config.port,
            username=self.config.username,
            password=self.config.password,
            look_for_keys=False,
            allow_agent=False,
            timeout=15,
        )
        self.client = client

    def close(self) -> None:
        if self.client:
            self.client.close()
            self.client = None

    def test_connection(self) -> CommandResult:
        return self.run_command("echo connected")

    def run_command(self, command: str) -> CommandResult:
        if not self.client:
            raise RuntimeError("SSH 未连接")
        stdin, stdout, stderr = self.client.exec_command(command)
        exit_code = stdout.channel.recv_exit_status()
        return CommandResult(
            command=command,
            exit_code=exit_code,
            stdout=stdout.read().decode("utf-8", errors="replace"),
            stderr=stderr.read().decode("utf-8", errors="replace"),
        )

    def upload_file(self, local_path: Path | str, remote_path: str) -> None:
        if not self.client:
            raise RuntimeError("SSH 未连接")
        with self.client.open_sftp() as sftp:
            sftp.put(str(local_path), remote_path)
