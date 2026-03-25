"""变更追踪器 — 记录自动填充和手动修改"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable


@dataclass
class ChangeEntry:
    """一条变更记录"""
    timestamp: str
    field_name: str
    action: str       # "自动填充" | "手动修改"
    old_value: str
    new_value: str

    def format(self) -> str:
        ts = self.timestamp
        if self.action == "自动填充":
            return f"[{ts}] 自动填充  {self.field_name}: → {self._trunc(self.new_value)}"
        else:
            return (f"[{ts}] 手动修改  {self.field_name}: "
                    f"{self._trunc(self.old_value)} → {self._trunc(self.new_value)}")

    @staticmethod
    def _trunc(s, maxlen=40):
        s = s.replace("\n", " ").strip()
        return s[:maxlen] + "..." if len(s) > maxlen else s


class ChangeTracker:
    """追踪字段变更"""

    def __init__(self):
        self._log: list[ChangeEntry] = []
        self._loaded_values: dict[str, str] = {}  # field_name → loaded value
        self._listeners: list[Callable] = []
        self._suppressed = False  # 加载数据时抑制编辑事件

    def suppress(self, on: bool):
        """加载数据期间抑制编辑记录"""
        self._suppressed = on

    def record_load(self, field_name: str, value: str):
        """记录自动加载的值"""
        if not value or not value.strip():
            return
        self._loaded_values[field_name] = value
        entry = ChangeEntry(
            timestamp=self._now(),
            field_name=field_name,
            action="自动填充",
            old_value="",
            new_value=value
        )
        self._log.append(entry)
        self._notify()

    def record_edit(self, field_name: str, old_val: str, new_val: str):
        """记录手动编辑"""
        if self._suppressed:
            return
        if old_val == new_val:
            return
        entry = ChangeEntry(
            timestamp=self._now(),
            field_name=field_name,
            action="手动修改",
            old_value=old_val,
            new_value=new_val
        )
        self._log.append(entry)
        self._notify()

    def is_auto_filled(self, field_name: str) -> bool:
        """字段是否被自动填充过"""
        return field_name in self._loaded_values

    def get_log(self) -> list[ChangeEntry]:
        return list(self._log)

    def get_log_text(self) -> str:
        if not self._log:
            return "暂无变更记录"
        return "\n".join(e.format() for e in self._log)

    def add_listener(self, fn: Callable):
        """添加变更回调"""
        self._listeners.append(fn)

    def _notify(self):
        for fn in self._listeners:
            try:
                fn()
            except Exception:
                pass

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%H:%M:%S")
