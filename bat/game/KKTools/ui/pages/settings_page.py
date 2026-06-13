"""软件设置页：配置游戏目录、Mod 目录、输出目录等。"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core import settings
from ui.applog import log
from ui.widgets import PageBase, hint, make_card, section_title


class SettingsPage(PageBase):
    def __init__(self):
        super().__init__("软件设置", "配置游戏目录、Mod 仓库与输出目录")
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        card = make_card()
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(10)
        v.addWidget(section_title("路径配置"))

        self.kk = self._dir_row(v, "恋活(KK)游戏根目录")
        self.kks = self._dir_row(v, "恋活日光浴(KKS)游戏根目录")
        self.output = self._dir_row(v, "通用输出目录")
        self.carrier = self._dir_row(v, "伪装载体目录")

        v.addWidget(section_title("额外 Mod 目录"))
        v.addWidget(hint("游戏目录下的 mods 会自动纳入；这里可补充其它存放 zipmod 的目录。"))
        self.mod_list = QListWidget()
        self.mod_list.setMaximumHeight(120)
        v.addWidget(self.mod_list)
        mrow = QHBoxLayout()
        b_add = QPushButton("添加目录"); b_add.clicked.connect(self._add_mod_dir)
        b_del = QPushButton("移除选中"); b_del.clicked.connect(self._del_mod_dir)
        mrow.addWidget(b_add); mrow.addWidget(b_del); mrow.addStretch(1)
        v.addLayout(mrow)

        save = QPushButton("保存设置"); save.setProperty("accent", "primary")
        save.clicked.connect(self._save)
        v.addWidget(save)
        v.addStretch(1)
        self.body_layout.addWidget(card)
        self.body_layout.addStretch(1)

    def _dir_row(self, parent, label) -> QLineEdit:
        row = QHBoxLayout()
        edit = QLineEdit()
        b = QPushButton("…"); b.setFixedWidth(34)
        b.clicked.connect(lambda: self._pick(edit, label))
        lbl = QLabel(label); lbl.setMinimumWidth(190)
        row.addWidget(lbl); row.addWidget(edit, 1); row.addWidget(b)
        parent.addLayout(row)
        return edit

    def _pick(self, edit, label) -> None:
        d = QFileDialog.getExistingDirectory(self, label, edit.text() or "")
        if d:
            edit.setText(d)

    def _add_mod_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择 Mod 目录")
        if d:
            self.mod_list.addItem(d)

    def _del_mod_dir(self) -> None:
        for it in self.mod_list.selectedItems():
            self.mod_list.takeItem(self.mod_list.row(it))

    def _load(self) -> None:
        cfg = settings.load()
        self.kk.setText(cfg.get("kk_game_dir", ""))
        self.kks.setText(cfg.get("kks_game_dir", ""))
        self.output.setText(cfg.get("output_dir", ""))
        self.carrier.setText(cfg.get("carrier_dir", ""))
        self.mod_list.clear()
        for d in cfg.get("mod_dirs", []):
            self.mod_list.addItem(d)

    def _save(self) -> None:
        cfg = settings.load()
        cfg["kk_game_dir"] = self.kk.text().strip()
        cfg["kks_game_dir"] = self.kks.text().strip()
        cfg["output_dir"] = self.output.text().strip()
        cfg["carrier_dir"] = self.carrier.text().strip()
        cfg["mod_dirs"] = [self.mod_list.item(i).text() for i in range(self.mod_list.count())]
        settings.save(cfg)
        log("设置已保存")
        QMessageBox.information(self, "已保存", "设置已保存。")
