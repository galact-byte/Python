"""主窗口：左侧导航 + 右侧页面堆叠。功能型布局，克制无装饰。"""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.pages.browser_page import BrowserPage
from ui.pages.editor_page import EditorPage
from ui.pages.log_page import LogPage
from ui.pages.mod_page import ModPage
from ui.pages.pack_page import PackPage
from ui.pages.scene_page import ScenePage
from ui.pages.settings_page import SettingsPage
from ui.pages.share_page import SharePage

# 导航顺序与页面索引
NAV = [
    "角色卡编辑",
    "卡片浏览器",
    "解包 / 打包",
    "分享整理导入",
    "Mod 仓库",
    "场景卡工具",
    "运行日志",
    "软件设置",
]
EDITOR_ROW = 0


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KKTools - 恋活角色卡工具箱")
        self.resize(1200, 780)
        self.setMinimumSize(QSize(1000, 640))
        self.setAcceptDrops(True)

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)
        root.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        # 实例化页面
        self.editor = EditorPage()
        self.browser = BrowserPage(on_open_card=self._open_in_editor)
        self.pages = [
            self.editor,
            self.browser,
            PackPage(),
            SharePage(),
            ModPage(),
            ScenePage(),
            LogPage(),
            SettingsPage(),
        ]
        for p in self.pages:
            self.stack.addWidget(p)

        self.nav.setCurrentRow(0)
        self.statusBar().showMessage("就绪 — 可把角色卡拖到窗口直接编辑")

    def _build_sidebar(self) -> QWidget:
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(220)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(12, 16, 12, 12)
        sl.setSpacing(4)

        title = QLabel("KKTools")
        title.setObjectName("BrandTitle")
        sub = QLabel("恋活 / 日光浴 角色卡工具箱")
        sub.setObjectName("BrandSub")
        sl.addWidget(title)
        sl.addWidget(sub)
        sl.addSpacing(10)

        self.nav = QListWidget()
        self.nav.setObjectName("NavList")
        for name in NAV:
            QListWidgetItem(name, self.nav)
        self.nav.currentRowChanged.connect(self._on_nav)
        sl.addWidget(self.nav, 1)

        ver = QLabel("v0.3.0")
        ver.setObjectName("BrandSub")
        ver.setAlignment(Qt.AlignmentFlag.AlignRight)
        sl.addWidget(ver)
        return side

    def _on_nav(self, row: int) -> None:
        if 0 <= row < self.stack.count():
            self.stack.setCurrentIndex(row)

    def _open_in_editor(self, path: str) -> None:
        self.nav.setCurrentRow(EDITOR_ROW)
        self.editor.load_card(path)

    # ---- 拖拽角色卡直接编辑 ----

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".png"):
                self._open_in_editor(path)
                break
