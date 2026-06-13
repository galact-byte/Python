"""可复用的小部件与辅助函数，避免各页面重复造轮子。"""

from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


def make_card(parent: QWidget | None = None) -> QFrame:
    """一个带卡片样式的容器（实色背景 + 细描边 + 小圆角）。"""
    frame = QFrame(parent)
    frame.setProperty("card", True)
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
        hl.setContentsMargins(20, 14, 20, 14)
        hl.setSpacing(2)
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
        self.body_layout.setContentsMargins(20, 16, 20, 16)
        self.body_layout.setSpacing(14)
        self._outer.addWidget(self.body, 1)
