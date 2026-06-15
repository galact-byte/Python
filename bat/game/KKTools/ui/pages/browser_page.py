"""卡片浏览器：选目录 -> 扫描识别 -> 缩略图墙预览，支持类型筛选 / 搜索 /
双击进编辑器 / 导出目录卡片信息 CSV。"""

from __future__ import annotations

import csv
import os
import subprocess
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
)

from core import card_scan, settings
from core.card_scan import TYPE_LABELS, CardItem
from ui.applog import log
from ui.widgets import PageBase, make_card
from ui.worker import Worker

ROLE_ITEM = Qt.ItemDataRole.UserRole

# 克制的类型色标（功能型状态色，非装饰）
TYPE_COLORS = {
    "character": "#58a6ff",   # 角色卡 蓝
    "coordinate": "#3fb950",  # 服装卡 绿
    "scene": "#d29922",       # 场景卡 琥珀
    "other": "#8b949e",       # 其它 灰
}

# 单次最多在网格里渲染的卡片数（整合版场景卡上万，全渲染会拖垮 UI 与内存）
MAX_DISPLAY = 3000


class BrowserPage(PageBase):
    def __init__(self, on_open_card: Callable[[str], None] | None = None):
        super().__init__("卡片浏览器", "扫描目录，识别角色卡 / 服装卡 / 场景卡，缩略图墙预览")
        self.on_open_card = on_open_card
        self._items: list[CardItem] = []
        self._icon_cache: dict[str, QIcon] = {}
        self._worker: Worker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        bar = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("选择或输入要浏览的目录")
        self.path_edit.setText(settings.get("last_browse_dir", "") or "")
        btn_browse = QPushButton("选择目录")
        btn_browse.clicked.connect(self._choose_dir)
        self.chk_recursive = QCheckBox("递归子目录")
        btn_scan = QPushButton("扫描")
        btn_scan.setProperty("accent", "primary")
        btn_scan.clicked.connect(self._start_scan)
        bar.addWidget(QLabel("目录"))
        bar.addWidget(self.path_edit, 1)
        bar.addWidget(btn_browse)
        bar.addWidget(self.chk_recursive)
        bar.addWidget(btn_scan)
        self.body_layout.addLayout(bar)

        filt = QHBoxLayout()
        self.cb_type = QComboBox()
        self.cb_type.addItem("全部类型", "all")
        for key, lbl in TYPE_LABELS.items():
            self.cb_type.addItem(lbl, key)
        self.cb_type.currentIndexChanged.connect(self._apply_filter)
        self.search = QLineEdit()
        self.search.setPlaceholderText("按名称 / 文件名搜索")
        self.search.textChanged.connect(self._apply_filter)
        self.btn_csv = QPushButton("导出CSV")
        self.btn_csv.clicked.connect(self._export_csv)
        self.btn_csv.setEnabled(False)
        filt.addWidget(QLabel("筛选"))
        filt.addWidget(self.cb_type)
        filt.addWidget(self.search, 1)
        filt.addWidget(self.btn_csv)
        self.body_layout.addLayout(filt)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.body_layout.addWidget(self.progress)

        card = make_card()
        from PyQt6.QtWidgets import QVBoxLayout

        cl = QVBoxLayout(card)
        cl.setContentsMargins(8, 8, 8, 8)
        self.grid = QListWidget()
        self.grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.grid.setIconSize(QSize(120, 135))
        self.grid.setGridSize(QSize(146, 188))
        self.grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.grid.setMovement(QListWidget.Movement.Static)
        self.grid.setSpacing(6)
        self.grid.setWordWrap(True)
        self.grid.itemDoubleClicked.connect(self._on_double)
        self.grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid.customContextMenuRequested.connect(self._menu)
        cl.addWidget(self.grid)
        self.status = QLabel("选择一个目录开始扫描")
        self.status.setObjectName("HintLabel")
        cl.addWidget(self.status)
        self.body_layout.addWidget(card, 1)

    # ---- 扫描 ----

    def _choose_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择目录", self.path_edit.text() or "")
        if d:
            self.path_edit.setText(d)

    def _start_scan(self) -> None:
        directory = self.path_edit.text().strip()
        if not directory or not Path(directory).is_dir():
            QMessageBox.warning(self, "目录无效", "请选择一个有效目录。")
            return
        settings.set_value("last_browse_dir", directory)
        if self._worker and self._worker.isRunning():
            return
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.status.setText("扫描中…")
        log(f"开始扫描目录: {directory} (递归={self.chk_recursive.isChecked()})")
        self._worker = Worker(
            card_scan.scan_dir, directory, recursive=self.chk_recursive.isChecked()
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_scanned)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, cur: int, total: int, desc: str) -> None:
        if total:
            self.progress.setRange(0, total)
            self.progress.setValue(cur)
        self.status.setText(f"扫描中… {cur}/{total}  {desc}")

    def _on_scanned(self, items: list[CardItem]) -> None:
        self.progress.setVisible(False)
        self._items = items
        self._icon_cache.clear()   # 新一批卡片，旧图标缓存作废
        self.btn_csv.setEnabled(bool(items))
        log(f"扫描完成，共 {len(items)} 张卡片")
        self._apply_filter()

    def _on_failed(self, msg: str) -> None:
        self.progress.setVisible(False)
        self.status.setText("扫描失败")
        QMessageBox.critical(self, "扫描失败", msg.splitlines()[0])

    # ---- 展示与筛选 ----

    def _apply_filter(self) -> None:
        type_key = self.cb_type.currentData()
        kw = self.search.text().strip().lower()
        self.grid.clear()
        shown = 0
        capped = False
        for it in self._items:
            if type_key != "all" and it.type != type_key:
                continue
            hay = f"{it.name} {Path(it.path).name}".lower()
            if kw and kw not in hay:
                continue
            if shown >= MAX_DISPLAY:
                capped = True
                break
            self._add_item(it)
            shown += 1
        counts = {}
        for it in self._items:
            counts[it.type] = counts.get(it.type, 0) + 1
        summary = "  ".join(f"{TYPE_LABELS.get(k,k)}:{v}" for k, v in counts.items())
        tail = f"（已达显示上限 {MAX_DISPLAY}，请用筛选/搜索缩小或扫描子目录）" if capped else ""
        self.status.setText(f"显示 {shown} / {len(self._items)} 张    [{summary}]{tail}")

    def _add_item(self, it: CardItem) -> None:
        # 图标缓存：按路径缓存降采样后的小 QPixmap，原始缩略图字节用完即释放。
        # 这样重新筛选/搜索时能复用，且不会让上千张全尺寸 PNG 常驻内存。
        icon = self._icon_cache.get(it.path)
        if icon is None:
            pix = QPixmap()
            if it.thumbnail:
                pix.loadFromData(it.thumbnail)
            if not pix.isNull():
                pix = pix.scaled(self.grid.iconSize(), Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
                icon = QIcon(pix)
            else:
                icon = QIcon()
            self._icon_cache[it.path] = icon
            it.thumbnail = b""   # 已转成小图标，释放原始字节
        label = it.name or Path(it.path).stem
        tag = TYPE_LABELS.get(it.type, it.type)
        if it.game in ("KK", "KKS"):
            tag = f"{it.game}·{tag}"
        wi = QListWidgetItem(icon, f"{label}\n[{tag}]")
        wi.setData(ROLE_ITEM, it)
        wi.setToolTip(it.path)
        wi.setForeground(QColor(TYPE_COLORS.get(it.type, "#c9d1d9")))
        wi.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.grid.addItem(wi)

    # ---- 交互 ----

    def _on_double(self, wi: QListWidgetItem) -> None:
        it: CardItem = wi.data(ROLE_ITEM)
        if it.type == "character" and self.on_open_card:
            self.on_open_card(it.path)
        else:
            self._open_in_explorer(it.path)

    def _menu(self, pos) -> None:
        wi = self.grid.itemAt(pos)
        if not wi:
            return
        it: CardItem = wi.data(ROLE_ITEM)
        menu = QMenu(self)
        if it.type == "character":
            menu.addAction("在编辑器打开", lambda: self.on_open_card and self.on_open_card(it.path))
        menu.addAction("打开所在文件夹", lambda: self._open_in_explorer(it.path))
        menu.exec(self.grid.mapToGlobal(pos))

    def _open_in_explorer(self, path: str) -> None:
        try:
            if os.name == "nt":
                subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            else:
                subprocess.Popen(["xdg-open", str(Path(path).parent)])
        except OSError as exc:
            QMessageBox.warning(self, "打开失败", str(exc))

    def _export_csv(self) -> None:
        if not self._items:
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出卡片信息 CSV", "cards.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["文件名", "类型", "游戏", "角色名", "路径"])
            for it in self._items:
                w.writerow([Path(it.path).name, TYPE_LABELS.get(it.type, it.type),
                            it.game, it.name, it.path])
        log(f"导出 CSV: {path}")
        QMessageBox.information(self, "已导出", f"已导出 {len(self._items)} 条到:\n{path}")
