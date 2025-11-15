import sys
import os
import json
import itertools
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import re

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTreeWidget, QTreeWidgetItem,
    QGraphicsScene, QGraphicsView, QGraphicsPixmapItem, QFileDialog, QMessageBox, QSplitter, QSpinBox, QLabel, QDialog,
    QDialogButtonBox, QFormLayout, QMenu, QToolBar, QStatusBar,
    QProgressDialog, QGraphicsTextItem
)
from PyQt6.QtCore import (
    Qt, QPoint, pyqtSignal, QMimeData, QSettings, QByteArray, QDataStream, QIODevice
)
from PyQt6.QtGui import (
    QPixmap, QPainter, QColor, QBrush, QAction, QIcon,
    QDrag, QFont
)

from PIL import Image


class MutexSettingsDialog(QDialog):
    """互斥设置对话框"""
    def __init__(self, parent=None, layer_tree=None, current_group=None, current_image_path=None):
        super().__init__(parent)
        self.setWindowTitle("互斥设置")
        self.setModal(True)
        self.setMinimumSize(600, 400)
        
        self.layer_tree = layer_tree
        self.current_group = current_group
        self.current_image_path = current_image_path
        self.mutex_items = set()  # 存储选中的互斥项
        
        # 从当前组获取现有的互斥设置
        if hasattr(current_group, 'mutex_settings'):
            if current_image_path in current_group.mutex_settings:
                self.mutex_items = current_group.mutex_settings[current_image_path].copy()
        
        self.setStyleSheet("""
            QDialog {
                background-color: #f0f0f0;
            }
            QTreeWidget {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton {
                padding: 5px 15px;
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        
        layout = QVBoxLayout()
        
        # 说明标签
        info_label = QLabel(f"为 '{os.path.basename(current_image_path)}' 设置互斥图片:")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 创建树形控件显示所有图层和图片
        self.mutex_tree = QTreeWidget()
        self.mutex_tree.setHeaderLabel("选择互斥的图片或图层组")
        layout.addWidget(self.mutex_tree)
        
        # 填充树形控件
        self.populate_tree()
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def populate_tree(self):
        """填充树形控件"""
        # 暂时断开信号连接，避免初始化时触发
        self.is_updating = True
        
        for i in range(self.layer_tree.topLevelItemCount()):
            group_item = self.layer_tree.topLevelItem(i)
            if isinstance(group_item, LayerGroupItem):
                # 跳过当前图层组
                if group_item == self.current_group:
                    continue
                    
                # 创建组节点
                tree_group = QTreeWidgetItem()
                tree_group.setText(0, f"[图层组] {group_item.layer_name}")
                tree_group.setData(0, Qt.ItemDataRole.UserRole, ("group", group_item))
                
                # 添加复选框
                tree_group.setCheckState(0, Qt.CheckState.Unchecked)
                
                self.mutex_tree.addTopLevelItem(tree_group)
                
                # 添加图片子节点
                for image_path in group_item.images:
                    image_item = QTreeWidgetItem(tree_group)
                    image_item.setText(0, os.path.basename(image_path))
                    image_item.setData(0, Qt.ItemDataRole.UserRole, ("image", image_path))
                    
                    # 添加复选框
                    image_item.setCheckState(0, Qt.CheckState.Unchecked)
                
                tree_group.setExpanded(True)
        
        # 恢复已有的互斥设置
        for i in range(self.mutex_tree.topLevelItemCount()):
            group_item = self.mutex_tree.topLevelItem(i)
            group_data = group_item.data(0, Qt.ItemDataRole.UserRole)
            if group_data:
                _, layer_group = group_data
                group_id = f"group:{layer_group.layer_name}"
                
                # 如果整个组被选中
                if group_id in self.mutex_items:
                    group_item.setCheckState(0, Qt.CheckState.Checked)
                    # 同时选中所有子项
                    for j in range(group_item.childCount()):
                        child = group_item.child(j)
                        child.setCheckState(0, Qt.CheckState.Checked)
                else:
                    # 检查子项
                    any_child_checked = False
                    for j in range(group_item.childCount()):
                        child = group_item.child(j)
                        child_data = child.data(0, Qt.ItemDataRole.UserRole)
                        if child_data:
                            _, image_path = child_data
                            image_id = f"image:{image_path}"
                            if image_id in self.mutex_items:
                                child.setCheckState(0, Qt.CheckState.Checked)
                                any_child_checked = True
                    
                    # 如果有子项被选中，设置父项为部分选中状态
                    if any_child_checked:
                        group_item.setCheckState(0, Qt.CheckState.PartiallyChecked)
        
        self.is_updating = False
        
        # 连接信号
        self.mutex_tree.itemChanged.connect(self.on_item_changed)
    
    def on_item_changed(self, item, column):
        """处理复选框状态变化"""
        if hasattr(self, 'is_updating') and self.is_updating:
            return
            
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        
        item_type, item_value = data
        
        self.is_updating = True
        
        if item_type == "group":
            group_id = f"group:{item_value.layer_name}"
            if item.checkState(0) == Qt.CheckState.Checked:
                self.mutex_items.add(group_id)
                # 同时选中所有子项并添加到互斥集合
                for i in range(item.childCount()):
                    child = item.child(i)
                    child.setCheckState(0, Qt.CheckState.Checked)
                    child_data = child.data(0, Qt.ItemDataRole.UserRole)
                    if child_data:
                        _, image_path = child_data
                        image_id = f"image:{image_path}"
                        self.mutex_items.add(image_id)
            else:
                self.mutex_items.discard(group_id)
                # 取消选中所有子项
                for i in range(item.childCount()):
                    child = item.child(i)
                    child.setCheckState(0, Qt.CheckState.Unchecked)
                    child_data = child.data(0, Qt.ItemDataRole.UserRole)
                    if child_data:
                        _, image_path = child_data
                        image_id = f"image:{image_path}"
                        self.mutex_items.discard(image_id)
        
        elif item_type == "image":
            image_id = f"image:{item_value}"
            parent = item.parent()
            
            if item.checkState(0) == Qt.CheckState.Checked:
                self.mutex_items.add(image_id)
            else:
                self.mutex_items.discard(image_id)
            
            # 更新父项状态
            if parent:
                parent_data = parent.data(0, Qt.ItemDataRole.UserRole)
                if parent_data:
                    _, layer_group = parent_data
                    group_id = f"group:{layer_group.layer_name}"
                    
                    # 检查所有子项状态
                    all_checked = True
                    any_checked = False
                    for i in range(parent.childCount()):
                        child = parent.child(i)
                        if child.checkState(0) == Qt.CheckState.Checked:
                            any_checked = True
                        else:
                            all_checked = False
                    
                    # 更新父项状态
                    if all_checked:
                        parent.setCheckState(0, Qt.CheckState.Checked)
                        self.mutex_items.add(group_id)
                    elif any_checked:
                        parent.setCheckState(0, Qt.CheckState.PartiallyChecked)
                        self.mutex_items.discard(group_id)
                    else:
                        parent.setCheckState(0, Qt.CheckState.Unchecked)
                        self.mutex_items.discard(group_id)
        
        self.is_updating = False
    
    def get_mutex_items(self) -> Set[str]:
        """获取选中的互斥项"""
        return self.mutex_items


class LayerNameDialog(QDialog):
    """图层命名对话框"""
    def __init__(self, parent=None, initial_name="", initial_order=1, taken_orders=None):
        super().__init__(parent)
        self.setWindowTitle("图层设置")
        self.setModal(True)
        self.setMinimumWidth(300)
        self.taken_orders = taken_orders or []
        
        # 设置样式
        self.setStyleSheet("""
            QDialog {
                background-color: #f0f0f0;
            }
            QLineEdit {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
            QPushButton {
                padding: 5px 15px;
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        
        layout = QFormLayout()
        
        # 名称输入框
        from PyQt6.QtWidgets import QLineEdit
        self.name_input = QLineEdit(initial_name)
        layout.addRow("图层名称:", self.name_input)
        
        # 顺序输入框
        self.order_input = QSpinBox()
        self.order_input.setMinimum(1)
        self.order_input.setMaximum(999)
        self.order_input.setValue(initial_order)
        self.order_input.valueChanged.connect(self.check_order)
        layout.addRow("图层顺序:", self.order_input)
        
        # 提示标签
        self.hint_label = QLabel("")
        self.hint_label.setStyleSheet("color: red;")
        layout.addRow("", self.hint_label)
        
        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addWidget(buttons)
        self.setLayout(main_layout)
        
        # 初始检查
        self.check_order()
    
    def check_order(self):
        """检查顺序是否已被占用"""
        order = self.order_input.value()
        if order in self.taken_orders:
            self.hint_label.setText(f"顺序 {order} 已被占用")
            return False
        else:
            self.hint_label.setText("")
            return True
    
    def validate_and_accept(self):
        """验证并接受"""
        if self.check_order():
            self.accept()
        else:
            QMessageBox.warning(self, "警告", "该顺序号已被占用，请选择其他顺序号")
    
    def get_values(self) -> Tuple[str, int]:
        return self.name_input.text(), self.order_input.value()


class DraggableLayerTree(QTreeWidget):
    """支持拖拽的图层树"""
    itemsReordered = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)  # 支持多选
        
        self.drag_item = None
        self.drag_start_position = None
        self.main_window = None  # 存储主窗口引用
    
    def set_main_window(self, main_window):
        """设置主窗口引用"""
        self.main_window = main_window
    
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            if item and isinstance(item, LayerGroupItem):
                # 检查是否点击在拖拽图标区域（前30像素）
                item_rect = self.visualItemRect(item)
                if event.position().x() < item_rect.left() + 30:
                    self.drag_item = item
                    self.drag_start_position = event.position()
                    return  # 阻止默认的选择行为
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self.drag_item and self.drag_start_position:
            if event.buttons() & Qt.MouseButton.LeftButton:
                distance = (event.position() - self.drag_start_position).manhattanLength()
                if distance >= QApplication.startDragDistance():
                    self.performDrag()
                    return
        
        super().mouseMoveEvent(event)
    
    def performDrag(self):
        """执行拖拽操作"""
        if not self.drag_item:
            return
            
        drag = QDrag(self)
        mime_data = QMimeData()
        
        # 存储拖拽项的数据
        data = QByteArray()
        stream = QDataStream(data, QIODevice.OpenModeFlag.WriteOnly)
        stream.writeInt(self.indexOfTopLevelItem(self.drag_item))
        
        mime_data.setData("application/x-layer-group", data)
        drag.setMimeData(mime_data)
        
        # 创建拖拽时的图标
        pixmap = QPixmap(200, 30)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.fillRect(pixmap.rect(), QColor(200, 200, 200, 128))
        painter.setPen(Qt.GlobalColor.black)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, self.drag_item.layer_name)
        painter.end()
        drag.setPixmap(pixmap)
        
        # 执行拖拽
        drag.exec(Qt.DropAction.MoveAction)
        
        self.drag_item = None
        self.drag_start_position = None
    
    def dragEnterEvent(self, event):
        """拖拽进入事件"""
        if event.mimeData().hasFormat("application/x-layer-group"):
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dragMoveEvent(self, event):
        """拖拽移动事件"""
        if event.mimeData().hasFormat("application/x-layer-group"):
            event.acceptProposedAction()
            # 高亮显示放置位置
            self.setDropIndicatorShown(True)
        else:
            event.ignore()
    
    def dropEvent(self, event):
        """放下事件"""
        if not event.mimeData().hasFormat("application/x-layer-group"):
            event.ignore()
            return
            
        # 获取源项索引
        data = event.mimeData().data("application/x-layer-group")
        stream = QDataStream(data, QIODevice.OpenModeFlag.ReadOnly)
        source_index = stream.readInt()
        
        # 获取目标位置
        drop_position = event.position().toPoint()
        target_item = self.itemAt(drop_position)
        
        if not target_item or not isinstance(target_item, LayerGroupItem):
            event.ignore()
            return
            
        # 获取源项和目标项
        source_item = self.topLevelItem(source_index)
        if not source_item or source_item == target_item:
            event.ignore()
            return
            
        # 执行位置交换
        source_order = source_item.layer_order
        target_order = target_item.layer_order
        
        # 交换顺序值
        source_item.layer_order = target_order
        target_item.layer_order = source_order
        
        # 更新显示
        source_item.update_display()
        target_item.update_display()
        
        # 重新排序显示
        if self.main_window:
            self.main_window.sort_layer_groups()
        
        # 发送重排信号
        self.itemsReordered.emit()
        
        event.acceptProposedAction()
    
    def keyPressEvent(self, event):
        """处理键盘事件"""
        if event.key() == Qt.Key.Key_Delete:
            # 删除选中的图片
            selected_items = self.selectedItems()
            if selected_items:
                # 筛选出图片项
                image_items = [item for item in selected_items if isinstance(item, ImageItem)]
                if image_items:
                    reply = QMessageBox.question(
                        self,
                        "确认删除",
                        f"确定要删除选中的 {len(image_items)} 个图片吗？",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    
                    if reply == QMessageBox.StandardButton.Yes:
                        for item in image_items:
                            parent = item.parent()
                            if isinstance(parent, LayerGroupItem):
                                parent.remove_image(item.image_path)
                        
                        # 触发更新
                        self.itemsReordered.emit()
        
        super().keyPressEvent(event)


class ImageItem(QTreeWidgetItem):
    """图片项"""
    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.image_name = os.path.basename(image_path)
        self.setText(0, self.image_name)
        
        # 提取序号
        self.sequence_number = self.extract_sequence_number()
        
        # 加载缩略图
        try:
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                thumbnail = pixmap.scaled(30, 30, Qt.AspectRatioMode.KeepAspectRatio, 
                                         Qt.TransformationMode.SmoothTransformation)
                self.setIcon(0, QIcon(thumbnail))
        except:
            pass
    
    def extract_sequence_number(self) -> str:
        """提取图片名称的序号（前两位数字）"""
        basename = os.path.basename(self.image_path)
        match = re.match(r'^(\d{2})', basename)
        if match:
            return match.group(1)
        return "99"  # 默认序号


class LayerGroupItem(QTreeWidgetItem):
    """图层组项"""
    def __init__(self, name: str, order: int, parent=None):
        super().__init__(parent)
        self.layer_name = name
        self.layer_order = order
        self.images: List[str] = []
        self.current_image_index = 0
        self.mutex_settings: Dict[str, Set[str]] = {}  # 互斥设置 {图片路径: {互斥项集合}}
        self.is_enabled = True  # 是否启用
        
        # 设置可展开
        self.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
        
        self.update_display()
        self.setExpanded(True)
    
    def update_display(self):
        """更新显示文本"""
        mutex_count = len(self.mutex_settings)
        status = "启用" if self.is_enabled else "隐藏"
        
        if mutex_count > 0:
            self.setText(0, f"≡ {self.layer_name} (顺序: {self.layer_order}) [{status}] [互斥: {mutex_count}]")
        else:
            self.setText(0, f"≡ {self.layer_name} (顺序: {self.layer_order}) [{status}]")
        
        # 更新显示样式
        if not self.is_enabled:
            self.setForeground(0, QColor(128, 128, 128))  # 灰色显示隐藏的图层
        else:
            self.setForeground(0, QColor(0, 0, 0))  # 黑色显示启用的图层
        
        # 确保有子项时显示展开指示器
        if self.childCount() > 0:
            self.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
    
    def toggle_enabled(self):
        """切换启用/隐藏状态"""
        self.is_enabled = not self.is_enabled
        self.update_display()
    
    def add_image(self, image_path: str):
        """添加图片"""
        self.images.append(image_path)
        ImageItem(image_path, self)
        self.update_display()  # 更新显示以确保展开指示器正确显示
    
    def remove_image(self, image_path: str):
        """移除图片"""
        if image_path in self.images:
            self.images.remove(image_path)
            # 移除互斥设置
            if image_path in self.mutex_settings:
                del self.mutex_settings[image_path]
            # 移除对应的子项
            for i in range(self.childCount()):
                child = self.child(i)
                if isinstance(child, ImageItem) and child.image_path == image_path:
                    self.removeChild(child)
                    break
            self.update_display()
            
            # 调整当前索引
            if self.current_image_index >= len(self.images) and self.images:
                self.current_image_index = len(self.images) - 1
    
    def get_current_image(self) -> Optional[str]:
        """获取当前选中的图片"""
        if self.images and 0 <= self.current_image_index < len(self.images):
            return self.images[self.current_image_index]
        return None
    
    def get_images_by_sequence(self, sequence: str) -> List[str]:
        """获取指定序号的图片列表"""
        result = []
        for i in range(self.childCount()):
            child = self.child(i)
            if isinstance(child, ImageItem):
                if child.sequence_number == sequence or child.sequence_number == "00":
                    result.append(child.image_path)
        return result
    
    def sort_images(self):
        """按文件名排序图片"""
        # 定义排序函数，提取数字进行自然排序
        def natural_sort_key(path):
            import re
            basename = os.path.basename(path)
            # 分割文件名为文本和数字部分
            parts = re.split(r'(\d+)', basename)
            # 将数字部分转换为整数进行排序
            return [int(part) if part.isdigit() else part.lower() for part in parts]
        
        # 排序图片列表
        self.images.sort(key=natural_sort_key)
        
        # 清空子项
        self.takeChildren()
        
        # 重新添加排序后的图片项
        for image_path in self.images:
            ImageItem(image_path, self)
        
        self.update_display()


class PreviewCanvas(QGraphicsView):
    """预览画布"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        
        # 设置棋盘格背景以显示透明度
        self.setBackgroundBrush(self._create_checkerboard_brush())
        
        # 画布大小
        self.canvas_width = 922
        self.canvas_height = 922
        self.scene.setSceneRect(0, 0, self.canvas_width, self.canvas_height)
        
        # 设置视图模式 - 保持高质量渲染
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing, False)
        
        # 自动缩放以适应视图
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        
        # 图层项
        self.layer_items: Dict[str, QGraphicsPixmapItem] = {}
        
        # 设置样式
        self.setStyleSheet("""
            QGraphicsView {
                border: 2px solid #ccc;
                border-radius: 5px;
            }
        """)
        
        # 互斥提示文本项
        self.mutex_text_item = None
    
    def _create_checkerboard_brush(self) -> QBrush:
        """创建棋盘格背景画刷"""
        # 创建棋盘格图案
        pixmap = QPixmap(20, 20)
        pixmap.fill(QColor(255, 255, 255))
        painter = QPainter(pixmap)
        painter.fillRect(0, 0, 10, 10, QColor(220, 220, 220))
        painter.fillRect(10, 10, 10, 10, QColor(220, 220, 220))
        painter.end()
        return QBrush(pixmap)
    
    def resizeEvent(self, event):
        """视图大小改变时自动缩放"""
        super().resizeEvent(event)
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
    
    def set_canvas_size(self, width: int, height: int):
        """设置画布大小"""
        self.canvas_width = width
        self.canvas_height = height
        self.scene.setSceneRect(0, 0, width, height)
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
    
    def show_mutex_error(self, mutex_pairs: List[Tuple[str, str]]):
        """显示互斥错误信息"""
        self.scene.clear()
        self.layer_items.clear()
        
        # 创建错误提示文本
        error_text = "当前组合存在互斥:\n\n"
        for group1, img1, group2, img2 in mutex_pairs:
            error_text += f"• {group1} 的 {os.path.basename(img1)}\n"
            error_text += f"  与 {group2} 的 {os.path.basename(img2)} 互斥\n\n"
        
        # 显示文本
        text_item = QGraphicsTextItem(error_text)
        font = QFont("Arial", 12)
        text_item.setFont(font)
        text_item.setDefaultTextColor(QColor(255, 0, 0))
        
        # 居中显示
        text_rect = text_item.boundingRect()
        x = (self.canvas_width - text_rect.width()) / 2
        y = (self.canvas_height - text_rect.height()) / 2
        text_item.setPos(x, y)
        
        self.scene.addItem(text_item)
        self.mutex_text_item = text_item
    
    def update_layers(self, layer_groups: List[LayerGroupItem], parent_widget=None):
        """更新图层显示"""
        self.scene.clear()
        self.layer_items.clear()
        self.mutex_text_item = None
        
        # 过滤启用的图层组
        enabled_groups = [group for group in layer_groups if group.is_enabled]
        
        # 准备当前组合用于检查互斥
        current_combination = []
        for group in enabled_groups:
            image_path = group.get_current_image()
            if image_path:
                current_combination.append((group, image_path))
        
        # 检查互斥
        mutex_pairs = []
        for i, (group1, image1) in enumerate(current_combination):
            if image1 in group1.mutex_settings:
                mutex_items = group1.mutex_settings[image1]
                
                # 检查与其他图层的互斥
                for j, (group2, image2) in enumerate(current_combination):
                    if i != j:  # 不与自己比较
                        # 检查是否与整个组互斥
                        if f"group:{group2.layer_name}" in mutex_items:
                            mutex_pairs.append((group1.layer_name, image1, group2.layer_name, image2))
                        # 检查是否与特定图片互斥
                        elif f"image:{image2}" in mutex_items:
                            mutex_pairs.append((group1.layer_name, image1, group2.layer_name, image2))
        
        # 如果存在互斥，显示错误信息
        if mutex_pairs:
            self.show_mutex_error(mutex_pairs)
            return
        
        # 按顺序排序图层（数字越大越上层）
        sorted_groups = sorted(enabled_groups, key=lambda x: x.layer_order)
        
        for group in sorted_groups:
            image_path = group.get_current_image()
            if image_path and os.path.exists(image_path):
                try:
                    pixmap = QPixmap(image_path)
                    if not pixmap.isNull():
                        # 创建图形项并设置高质量渲染
                        item = QGraphicsPixmapItem(pixmap)
                        item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
                        item.setPos(0, 0)
                        self.scene.addItem(item)
                        self.layer_items[group.layer_name] = item
                except:
                    pass
        
        # 确保适应视图
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
    
    def export_composite(self, images_combination: List[str], output_path: str):
        """导出合成图片（保持透明度）"""
        # 创建透明背景的图片
        composite = Image.new('RGBA', (self.canvas_width, self.canvas_height), (0, 0, 0, 0))
        
        # 按顺序合成图层
        for image_path in images_combination:
            if os.path.exists(image_path):
                try:
                    layer = Image.open(image_path).convert('RGBA')
                    # 使用alpha_composite确保正确的alpha混合
                    composite = Image.alpha_composite(composite, layer)
                except:
                    pass
        
        # 保存为PNG（保持透明度）
        composite.save(output_path, 'PNG', optimize=False, compress_level=0)


class CanvasSizeDialog(QDialog):
    """画布大小设置对话框"""
    def __init__(self, parent=None, current_width=922, current_height=922):
        super().__init__(parent)
        self.setWindowTitle("设置画布大小")
        self.setModal(True)
        
        layout = QFormLayout()
        
        # 宽度输入
        self.width_input = QSpinBox()
        self.width_input.setMinimum(100)
        self.width_input.setMaximum(5000)
        self.width_input.setValue(current_width)
        self.width_input.setSuffix(" px")
        layout.addRow("宽度:", self.width_input)
        
        # 高度输入
        self.height_input = QSpinBox()
        self.height_input.setMinimum(100)
        self.height_input.setMaximum(5000)
        self.height_input.setValue(current_height)
        self.height_input.setSuffix(" px")
        layout.addRow("高度:", self.height_input)
        
        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addWidget(buttons)
        self.setLayout(main_layout)
    
    def get_size(self) -> Tuple[int, int]:
        return self.width_input.value(), self.height_input.value()


class LayerManager(QMainWindow):
    """主窗口"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("图层管理器")
        self.setGeometry(100, 100, 1400, 900)
        
        # 设置应用样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QTreeWidget {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 5px;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 5px;
                margin: 2px;
            }
            QTreeWidget::item:selected {
                background-color: #4CAF50;
                color: white;
            }
            QPushButton {
                padding: 8px 15px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
                border-color: #999;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
            QToolBar {
                background-color: #f0f0f0;
                border: none;
                spacing: 5px;
                padding: 5px;
            }
            QStatusBar {
                background-color: #e0e0e0;
                border-top: 1px solid #ccc;
            }
        """)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建工具栏
        self.create_toolbar()
        
        # 创建分割窗口
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧面板
        left_panel = self.create_left_panel()
        left_panel.setMinimumWidth(350)  # 设置左侧面板最小宽度
        
        # 右侧预览面板
        self.preview_canvas = PreviewCanvas()
        
        # 添加到分割窗口
        splitter.addWidget(left_panel)
        splitter.addWidget(self.preview_canvas)
        splitter.setSizes([400, 1000])  # 设置初始大小比例
        
        main_layout.addWidget(splitter)
        
        # 底部按钮区域
        bottom_layout = self.create_bottom_panel()
        main_layout.addLayout(bottom_layout)
        
        # 创建状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")
        
        # 初始化变量
        self.project_file = None
        
        # 设置
        self.settings = QSettings("LayerManager", "Settings")
        
        # 加载上次的项目
        self.load_last_project()
    
    def create_toolbar(self):
        """创建工具栏"""
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        # 新建项目
        new_action = QAction("新建项目", self)
        new_action.triggered.connect(self.new_project)
        toolbar.addAction(new_action)
        
        # 打开项目
        open_action = QAction("打开项目", self)
        open_action.triggered.connect(self.load_project)
        toolbar.addAction(open_action)
        
        # 保存项目
        save_action = QAction("保存项目", self)
        save_action.triggered.connect(self.save_project)
        toolbar.addAction(save_action)
        
        # 另存为项目
        save_as_action = QAction("另存为...", self)
        save_as_action.triggered.connect(self.save_project_as)
        toolbar.addAction(save_as_action)
        
        toolbar.addSeparator()
        
        # 设置画布大小
        canvas_size_action = QAction("画布设置", self)
        canvas_size_action.triggered.connect(self.set_canvas_size)
        toolbar.addAction(canvas_size_action)
        
        toolbar.addSeparator()
        
        # 排序图层组
        sort_layers_action = QAction("排序图层", self)
        sort_layers_action.triggered.connect(self.sort_layer_groups)
        toolbar.addAction(sort_layers_action)
    
    def create_left_panel(self) -> QWidget:
        """创建左侧面板"""
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # 标题
        title = QLabel("图层管理")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                padding: 10px;
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
            }
        """)
        left_layout.addWidget(title)
        
        # 提示信息
        hint_label = QLabel("提示：拖动≡图标排序，选中图片后按Delete键删除\n序号规则：相同序号组合，00序号可与任意组合")
        hint_label.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
        left_layout.addWidget(hint_label)
        
        # 图层树
        self.layer_tree = DraggableLayerTree()
        self.layer_tree.setHeaderLabel("图层列表")
        self.layer_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.layer_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.layer_tree.itemClicked.connect(self.on_item_clicked)
        self.layer_tree.itemsReordered.connect(self.update_preview)
        self.layer_tree.set_main_window(self)  # 设置主窗口引用
        left_layout.addWidget(self.layer_tree)
        
        # 添加图层按钮
        add_layer_btn = QPushButton("添加图层组")
        add_layer_btn.clicked.connect(self.add_layer_group)
        add_layer_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        left_layout.addWidget(add_layer_btn)
        
        return left_widget
    
    def create_bottom_panel(self) -> QHBoxLayout:
        """创建底部面板"""
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        
        # 导出按钮
        export_btn = QPushButton("导出组合图片")
        export_btn.clicked.connect(self.export_combinations)
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        bottom_layout.addWidget(export_btn)
        
        bottom_layout.addStretch()
        
        return bottom_layout
    
    def sort_layer_groups(self):
        """按顺序号排序图层组"""
        # 收集所有图层组
        layer_groups = []
        
        # 先从树中移除所有项（但不删除）
        while self.layer_tree.topLevelItemCount() > 0:
            item = self.layer_tree.takeTopLevelItem(0)
            if isinstance(item, LayerGroupItem):
                layer_groups.append((item.layer_order, item))
        
        # 按顺序号排序
        layer_groups.sort(key=lambda x: x[0])
        
        # 按新顺序重新添加
        for _, item in layer_groups:
            self.layer_tree.addTopLevelItem(item)
        
        self.update_preview()
        self.status_bar.showMessage("图层已按顺序排序")

    
    def get_taken_orders(self, exclude_item=None) -> List[int]:
        """获取已占用的顺序号"""
        orders = []
        for i in range(self.layer_tree.topLevelItemCount()):
            item = self.layer_tree.topLevelItem(i)
            if isinstance(item, LayerGroupItem) and item != exclude_item:
                orders.append(item.layer_order)
        return orders
    
    def add_layer_group(self):
        """添加图层组"""
        taken_orders = self.get_taken_orders()
        
        # 找出下一个可用的顺序号
        next_order = 1
        while next_order in taken_orders:
            next_order += 1
        
        dialog = LayerNameDialog(self, initial_order=next_order, taken_orders=taken_orders)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, order = dialog.get_values()
            if name:
                # 检查是否有重名
                for i in range(self.layer_tree.topLevelItemCount()):
                    item = self.layer_tree.topLevelItem(i)
                    if isinstance(item, LayerGroupItem) and item.layer_name == name:
                        QMessageBox.warning(self, "警告", "图层名称已存在！")
                        return
                
                # 添加图层组
                layer_group = LayerGroupItem(name, order)
                self.layer_tree.addTopLevelItem(layer_group)
                
                # 更新预览
                self.update_preview()
                self.status_bar.showMessage(f"已添加图层组: {name}")
    
    def show_context_menu(self, position: QPoint):
        """显示右键菜单"""
        item = self.layer_tree.itemAt(position)
        selected_items = self.layer_tree.selectedItems()
        
        if not item:
            return
        
        menu = QMenu()
        
        if isinstance(item, LayerGroupItem):
            # 图层组菜单
            # 检查是否多选了图层组
            selected_groups = [i for i in selected_items if isinstance(i, LayerGroupItem)]
            
            if len(selected_groups) > 1:
                # 多选菜单
                toggle_action = menu.addAction("切换选中图层组的显示状态")
                toggle_action.triggered.connect(self.toggle_selected_layer_groups)
                
                menu.addSeparator()
                
                delete_action = menu.addAction(f"删除选中的 {len(selected_groups)} 个图层组")
                delete_action.triggered.connect(self.delete_selected_layer_groups)
            else:
                # 单选菜单
                toggle_action = menu.addAction("隐藏图层组" if item.is_enabled else "启用图层组")
                toggle_action.triggered.connect(lambda: self.toggle_layer_group(item))
                
                menu.addSeparator()
                
                import_action = menu.addAction("导入图片")
                import_action.triggered.connect(lambda: self.import_images(item))
                
                import_folder_action = menu.addAction("导入文件夹")
                import_folder_action.triggered.connect(lambda: self.import_folder(item))
                
                menu.addSeparator()
                
                sort_images_action = menu.addAction("排序组内图片")
                sort_images_action.triggered.connect(lambda: self.sort_group_images(item))
                
                menu.addSeparator()
                
                edit_action = menu.addAction("编辑图层")
                edit_action.triggered.connect(lambda: self.edit_layer_group(item))
                
                delete_action = menu.addAction("删除图层组")
                delete_action.triggered.connect(lambda: self.delete_layer_group(item))
            
        elif isinstance(item, ImageItem):
            # 图片项菜单
            parent = item.parent()
            if isinstance(parent, LayerGroupItem):
                mutex_action = menu.addAction("互斥设置")
                mutex_action.triggered.connect(lambda: self.set_mutex(parent, item.image_path))
                
                menu.addSeparator()
                
            delete_action = menu.addAction("删除图片")
            delete_action.triggered.connect(lambda: self.delete_image(item))
            
            # 如果有多选，添加批量删除选项
            if len(selected_items) > 1:
                menu.addSeparator()
                delete_selected_action = menu.addAction(f"删除选中的 {len(selected_items)} 个项目")
                delete_selected_action.triggered.connect(self.delete_selected_images)
        
        menu.exec(self.layer_tree.mapToGlobal(position))
    
    def toggle_selected_layer_groups(self):
        """切换选中的图层组的显示状态"""
        selected_items = self.layer_tree.selectedItems()
        selected_groups = [item for item in selected_items if isinstance(item, LayerGroupItem)]
        
        if not selected_groups:
            return
        
        # 统计当前启用和隐藏的数量
        enabled_count = sum(1 for group in selected_groups if group.is_enabled)
        
        # 如果大部分是启用的，则全部隐藏；否则全部启用
        target_state = enabled_count < len(selected_groups) / 2
        
        for group in selected_groups:
            group.is_enabled = target_state
            group.update_display()
        
        self.update_preview()
        action = "启用" if target_state else "隐藏"
        self.status_bar.showMessage(f"已{action} {len(selected_groups)} 个图层组")
    
    def delete_selected_layer_groups(self):
        """删除选中的图层组"""
        selected_items = self.layer_tree.selectedItems()
        selected_groups = [item for item in selected_items if isinstance(item, LayerGroupItem)]
        
        if not selected_groups:
            return
        
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除选中的 {len(selected_groups)} 个图层组吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            for group in selected_groups:
                index = self.layer_tree.indexOfTopLevelItem(group)
                if index != -1:
                    self.layer_tree.takeTopLevelItem(index)
            
            self.update_preview()
            self.status_bar.showMessage(f"已删除 {len(selected_groups)} 个图层组")
    
    def toggle_layer_group(self, layer_group: LayerGroupItem):
        """切换图层组的启用/隐藏状态"""
        layer_group.toggle_enabled()
        self.update_preview()
        status = "已启用" if layer_group.is_enabled else "已隐藏"
        self.status_bar.showMessage(f"{status}图层组: {layer_group.layer_name}")
    
    def delete_selected_images(self):
        """删除选中的图片"""
        selected_items = self.layer_tree.selectedItems()
        image_items = [item for item in selected_items if isinstance(item, ImageItem)]
        
        if not image_items:
            return
            
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除选中的 {len(image_items)} 个图片吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            for item in image_items:
                parent = item.parent()
                if isinstance(parent, LayerGroupItem):
                    parent.remove_image(item.image_path)
            
            self.update_preview()
            self.status_bar.showMessage(f"已删除 {len(image_items)} 个图片")
    
    def sort_group_images(self, layer_group: LayerGroupItem):
        """排序图层组内的图片"""
        layer_group.sort_images()
        self.update_preview()
        self.status_bar.showMessage(f"已排序 {layer_group.layer_name} 组内的图片")
    
    def set_mutex(self, layer_group: LayerGroupItem, image_path: str):
        """设置互斥"""
        dialog = MutexSettingsDialog(self, self.layer_tree, layer_group, image_path)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            mutex_items = dialog.get_mutex_items()
            if mutex_items:
                layer_group.mutex_settings[image_path] = mutex_items
            else:
                # 如果没有选择任何项，删除互斥设置
                if image_path in layer_group.mutex_settings:
                    del layer_group.mutex_settings[image_path]
            
            layer_group.update_display()
            # 更新预览以检查当前组合是否有互斥
            self.update_preview()
            self.status_bar.showMessage(f"已更新互斥设置")
    
    def import_images(self, layer_group: LayerGroupItem):
        """导入图片"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif);;所有文件 (*.*)"
        )
        
        if files:
            for file in files:
                layer_group.add_image(file)
            
            # 自动排序新导入的图片
            layer_group.sort_images()
            
            self.update_preview()
            self.status_bar.showMessage(f"已导入 {len(files)} 个图片到 {layer_group.layer_name}")
    
    def import_folder(self, layer_group: LayerGroupItem):
        """导入文件夹中的PNG图片"""
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        
        if folder:
            png_files = list(Path(folder).glob("*.png"))
            for file in png_files:
                layer_group.add_image(str(file))
            
            # 自动排序新导入的图片
            layer_group.sort_images()
            
            self.update_preview()
            self.status_bar.showMessage(f"已从文件夹导入 {len(png_files)} 个PNG图片到 {layer_group.layer_name}")
    
    def delete_layer_group(self, layer_group: LayerGroupItem):
        """删除图层组"""
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除图层组 '{layer_group.layer_name}' 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            index = self.layer_tree.indexOfTopLevelItem(layer_group)
            self.layer_tree.takeTopLevelItem(index)
            self.update_preview()
            self.status_bar.showMessage(f"已删除图层组: {layer_group.layer_name}")
    
    def delete_image(self, image_item: ImageItem):
        """删除图片"""
        parent = image_item.parent()
        if isinstance(parent, LayerGroupItem):
            parent.remove_image(image_item.image_path)
            self.update_preview()
            self.status_bar.showMessage(f"已删除图片: {image_item.image_name}")
    
    def edit_layer_group(self, layer_group: LayerGroupItem):
        """编辑图层组"""
        taken_orders = self.get_taken_orders(exclude_item=layer_group)
        dialog = LayerNameDialog(self, layer_group.layer_name, layer_group.layer_order, taken_orders)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, order = dialog.get_values()
            if name:
                layer_group.layer_name = name
                layer_group.layer_order = order
                layer_group.update_display()
                self.update_preview()
                self.status_bar.showMessage(f"已更新图层组: {name}")
    
    def on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """处理项目点击"""
        if isinstance(item, ImageItem):
            parent = item.parent()
            if isinstance(parent, LayerGroupItem):
                # 更新当前选中的图片
                for i in range(parent.childCount()):
                    if parent.child(i) == item:
                        parent.current_image_index = i
                        break
                
                self.update_preview()
                self.status_bar.showMessage(f"已选择图片: {item.image_name}")
    
    def update_preview(self):
        """更新预览"""
        layer_groups = []
        for i in range(self.layer_tree.topLevelItemCount()):
            item = self.layer_tree.topLevelItem(i)
            if isinstance(item, LayerGroupItem):
                layer_groups.append(item)
        
        self.preview_canvas.update_layers(layer_groups, self)
    
    def set_canvas_size(self):
        """设置画布大小"""
        dialog = CanvasSizeDialog(
            self, 
            self.preview_canvas.canvas_width,
            self.preview_canvas.canvas_height
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            width, height = dialog.get_size()
            self.preview_canvas.set_canvas_size(width, height)
            self.update_preview()
            self.status_bar.showMessage(f"画布大小已设置为 {width}x{height}")
    
    def check_mutex(self, combination: List[Tuple[LayerGroupItem, str]]) -> bool:
        """检查组合是否包含互斥项"""
        # 构建当前组合的标识集合
        current_items = set()
        for group, image_path in combination:
            current_items.add(f"group:{group.layer_name}")
            current_items.add(f"image:{image_path}")
        
        # 检查每个图片的互斥设置
        for group, image_path in combination:
            if image_path in group.mutex_settings:
                mutex_items = group.mutex_settings[image_path]
                # 检查是否有互斥项在当前组合中
                if mutex_items & current_items:
                    return True  # 存在互斥，返回True
        
        return False  # 不存在互斥
    
    def export_combination_task(self, combination: List[Tuple[LayerGroupItem, str]], output_folder: str) -> Tuple[bool, str]:
        """导出单个组合的任务函数"""
        try:
            # 提取图片路径和生成文件名
            image_paths = []
            names = []
            for group, image_path in combination:
                image_paths.append(image_path)
                name = os.path.splitext(os.path.basename(image_path))[0]
                names.append(f"{group.layer_name}_{name}")
            
            output_filename = "_".join(names) + ".png"
            output_path = os.path.join(output_folder, output_filename)
            
            # 导出组合
            self.preview_canvas.export_composite(image_paths, output_path)
            
            return True, output_filename
        except Exception as e:
            return False, str(e)
    
    def export_combinations(self):
        """导出所有组合（使用多线程）"""
        # 收集所有启用的图层组
        layer_groups = []
        for i in range(self.layer_tree.topLevelItemCount()):
            item = self.layer_tree.topLevelItem(i)
            if isinstance(item, LayerGroupItem) and item.images and item.is_enabled:
                layer_groups.append(item)
        
        if not layer_groups:
            QMessageBox.warning(self, "警告", "没有可导出的启用图层！")
            return
        
        # 选择输出文件夹
        output_folder = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if not output_folder:
            return
        
        # 按图层顺序排序
        layer_groups.sort(key=lambda x: x.layer_order)
        
        # 收集所有序号
        all_sequences = set()
        for group in layer_groups:
            for i in range(group.childCount()):
                child = group.child(i)
                if isinstance(child, ImageItem):
                    if child.sequence_number != "00":  # 00可以与任意序号组合
                        all_sequences.add(child.sequence_number)
        
        # 生成每个序号的组合
        all_combinations = []
        
        for sequence in sorted(all_sequences):
            # 收集每个图层组中该序号的图片
            sequence_groups = []
            
            for group in layer_groups:
                # 获取该序号的图片（包括00序号）
                sequence_images = []
                for i in range(group.childCount()):
                    child = group.child(i)
                    if isinstance(child, ImageItem):
                        if child.sequence_number == sequence or child.sequence_number == "00":
                            sequence_images.append((group, child.image_path))
                
                if sequence_images:
                    sequence_groups.append(sequence_images)
            
            # 生成该序号的所有组合
            if sequence_groups:
                for combination in itertools.product(*sequence_groups):
                    # 检查互斥
                    if not self.check_mutex(combination):
                        all_combinations.append(combination)
        
        if not all_combinations:
            QMessageBox.warning(self, "警告", "所有组合都包含互斥项，没有可导出的组合！")
            return
        
        # 创建进度对话框
        progress_dialog = QProgressDialog(
            "正在导出组合...",
            "取消",
            0,
            len(all_combinations),
            self
        )
        progress_dialog.setWindowTitle("导出进度")
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setValue(0)
        
        # 使用线程池并发导出
        max_workers = min(8, os.cpu_count() or 4)  # 限制最大线程数
        completed_count = 0
        failed_count = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_combination = {}
            for combination in all_combinations:
                future = executor.submit(self.export_combination_task, combination, output_folder)
                future_to_combination[future] = combination
            
            # 处理完成的任务
            for future in as_completed(future_to_combination):
                if progress_dialog.wasCanceled():
                    executor.shutdown(wait=False)
                    break
                
                success, result = future.result()
                if success:
                    completed_count += 1
                else:
                    failed_count += 1
                
                # 更新进度
                progress_dialog.setValue(completed_count + failed_count)
                progress_dialog.setLabelText(
                    f"正在导出: {completed_count + failed_count}/{len(all_combinations)}\n"
                    f"成功: {completed_count}, 失败: {failed_count}"
                )
                QApplication.processEvents()
        
        progress_dialog.close()
        
        if not progress_dialog.wasCanceled():
            QMessageBox.information(
                self, 
                "完成", 
                f"导出完成！\n"
                f"成功: {completed_count} 个文件\n"
                f"失败: {failed_count} 个文件\n"
                f"输出目录: {output_folder}"
            )
            self.status_bar.showMessage(f"导出完成: {completed_count} 个文件")
    
    def new_project(self):
        """新建项目"""
        reply = QMessageBox.question(
            self,
            "新建项目",
            "是否保存当前项目？",
            QMessageBox.StandardButton.Yes | 
            QMessageBox.StandardButton.No | 
            QMessageBox.StandardButton.Cancel
        )
        
        if reply == QMessageBox.StandardButton.Cancel:
            return
        elif reply == QMessageBox.StandardButton.Yes:
            self.save_project()
        
        # 清空当前项目
        self.layer_tree.clear()
        self.preview_canvas.scene.clear()
        self.project_file = None
        self.setWindowTitle("图层管理器 - 新项目")
        self.status_bar.showMessage("已创建新项目")
        
        # 清除最后的项目记录
        self.settings.remove("last_project")
    
    def save_project(self, auto_save=False):
        """保存项目"""
        if not auto_save and not self.project_file:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "保存项目",
                "",
                "项目文件 (*.lmp);;所有文件 (*.*)"
            )
            if not file_path:
                return
            self.project_file = file_path
        
        if not self.project_file:
            return
        
        # 收集项目数据
        project_data = {
            "canvas_width": self.preview_canvas.canvas_width,
            "canvas_height": self.preview_canvas.canvas_height,
            "layers": []
        }
        
        for i in range(self.layer_tree.topLevelItemCount()):
            item = self.layer_tree.topLevelItem(i)
            if isinstance(item, LayerGroupItem):
                layer_data = {
                    "name": item.layer_name,
                    "order": item.layer_order,
                    "images": item.images,
                    "current_index": item.current_image_index,
                    "mutex_settings": {k: list(v) for k, v in item.mutex_settings.items()},
                    "is_enabled": item.is_enabled  # 保存启用状态
                }
                project_data["layers"].append(layer_data)
        
        # 保存到文件
        try:
            with open(self.project_file, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=2, ensure_ascii=False)
            
            self.setWindowTitle(f"图层管理器 - {os.path.basename(self.project_file)}")
            if not auto_save:
                self.status_bar.showMessage(f"项目已保存: {self.project_file}")
            
            # 保存最后打开的项目路径
            self.settings.setValue("last_project", self.project_file)
        except Exception as e:
            if not auto_save:
                QMessageBox.critical(self, "错误", f"保存项目失败:\n{str(e)}")
    
    def save_project_as(self):
        """另存为项目"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "另存为项目",
            "",
            "项目文件 (*.lmp);;所有文件 (*.*)"
        )
        
        if file_path:
            old_project_file = self.project_file
            self.project_file = file_path
            self.save_project()
            
            # 如果保存失败，恢复原来的路径
            if not os.path.exists(file_path):
                self.project_file = old_project_file
    
    def load_project(self, file_path=None):
        """加载项目"""
        if not file_path:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "打开项目",
                "",
                "项目文件 (*.lmp);;所有文件 (*.*)"
            )
        
        if not file_path or not os.path.exists(file_path):
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
            
            # 清空当前项目
            self.layer_tree.clear()
            
            # 设置画布大小
            self.preview_canvas.set_canvas_size(
                project_data.get("canvas_width", 922),
                project_data.get("canvas_height", 922)
            )
            
            # 加载图层
            for layer_data in project_data.get("layers", []):
                layer_group = LayerGroupItem(
                    layer_data["name"],
                    layer_data["order"]
                )
                
                # 加载图片
                for image_path in layer_data.get("images", []):
                    if os.path.exists(image_path):
                        layer_group.add_image(image_path)
                
                # 恢复互斥设置
                mutex_settings = layer_data.get("mutex_settings", {})
                layer_group.mutex_settings = {k: set(v) for k, v in mutex_settings.items()}
                
                layer_group.current_image_index = layer_data.get("current_index", 0)
                layer_group.is_enabled = layer_data.get("is_enabled", True)  # 恢复启用状态
                layer_group.update_display()
                self.layer_tree.addTopLevelItem(layer_group)
            
            self.project_file = file_path
            self.setWindowTitle(f"图层管理器 - {os.path.basename(file_path)}")
            self.update_preview()
            self.status_bar.showMessage(f"项目已加载: {file_path}")
            
            # 保存最后打开的项目路径
            self.settings.setValue("last_project", file_path)
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载项目失败:\n{str(e)}")
    
    def load_last_project(self):
        """加载上次的项目"""
        last_project = self.settings.value("last_project")
        if last_project and os.path.exists(last_project):
            self.load_project(last_project)
    
    def closeEvent(self, event):
        """关闭事件"""
        # 自动保存当前项目
        if self.project_file:
            self.save_project(auto_save=True)
        event.accept()


def main():
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyle("Fusion")
    
    # 设置应用程序信息（用于QSettings）
    app.setOrganizationName("LayerManager")
    app.setApplicationName("LayerManager")
    
    # 创建主窗口
    window = LayerManager()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

