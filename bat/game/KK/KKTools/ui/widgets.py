"""可复用的小部件与辅助函数，避免各页面重复造轮子。"""

from __future__ import annotations

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QVBoxLayout,
    QWidget,
)


def make_card(parent: QWidget | None = None) -> QFrame:
    """卡片容器：实色填充 + 大圆角 + 一层极轻投影。

    QSS 不支持 box-shadow，故用 QGraphicsDropShadowEffect 给平面界面加"浮起"层次——
    这是让界面"像软件而非线框"的关键一招。投影克制（功能型上限），不发光不发散。
    """
    frame = QFrame(parent)
    frame.setProperty("card", True)
    shadow = QGraphicsDropShadowEffect(frame)
    shadow.setBlurRadius(18)
    shadow.setColor(QColor(0, 0, 0, 48))
    shadow.setOffset(0, 3)
    frame.setGraphicsEffect(shadow)
    return frame


def section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("SectionTitle")
    return label


def hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("HintLabel")
    label.setWordWrap(True)
    return label


def field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("FieldLabel")
    return label


class PageBase(QWidget):
    """所有页面的基类：统一提供页头(标题+副标题) + 内容区。"""

    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._title = title
        self._subtitle = subtitle
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(0)

        header = QFrame()
        header.setObjectName("PageHeader")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(28, 20, 28, 18)
        hl.setSpacing(4)
        t = QLabel(title)
        t.setObjectName("PageTitle")
        hl.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setObjectName("PageSubtitle")
            hl.addWidget(s)
        self._outer.addWidget(header)

        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(28, 22, 28, 24)
        self.body_layout.setSpacing(18)
        self._outer.addWidget(self.body, 1)
