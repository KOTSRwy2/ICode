import os
import shutil
from PyQt5.QtCore import Qt, QUrl, pyqtSignal, QEvent
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QFileDialog, QWidget, QSizePolicy
from CustomWebEnginePage import CustomWebEngineView
from qfluentwidgets import (
    CardWidget, SubtitleLabel, CaptionLabel, TransparentToolButton,
    FluentIcon as FIF, BodyLabel, InfoBar, InfoBarPosition, IconWidget, Flyout, FlyoutAnimationType
)

class ClickableInfoWidget(QWidget):
    """自定义带 'i' 图标的可悬浮说明小字区域"""
    def __init__(self, text, detail_text, parent=None):
        super().__init__(parent)
        self.detail_text = detail_text
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 'i' 图标 (Info)
        self.icon = IconWidget(FIF.INFO, self)
        self.icon.setFixedSize(14, 14)

        # 说明文字，使用 Fluent 的弱化标签
        self.label = CaptionLabel(text, self)

        layout.addWidget(self.icon)
        layout.addWidget(self.label)
        layout.addStretch(1)

        self.setCursor(Qt.PointingHandCursor)
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self:
            if event.type() == QEvent.Enter:
                self._show_explanation_flyout()
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._show_explanation_flyout()
        super().mousePressEvent(event)

    def _show_explanation_flyout(self):
        """鼠标悬浮或点击时，平滑弹出气泡卡片展示详细释义"""
        if not hasattr(self, '_flyout_shown') or not self._flyout_shown:
            view = BodyLabel(self.detail_text)
            view.setWordWrap(True)
            view.setMinimumWidth(250)
            view.setContentsMargins(12, 12, 12, 12)
            flyout = Flyout.make(
                view,
                self.label,
                self.window(),
                FlyoutAnimationType.PULL_UP
            )
            self._flyout_shown = True
            flyout.closed.connect(self._on_flyout_closed)
            
    def _on_flyout_closed(self):
        self._flyout_shown = False


class InteractiveChartCard(CardWidget):
    """
    重构后的交互式 Web 图表卡片控件
    具备：自适应主题、一行一图、卡片内容展开/收起、悬浮提示说明、右上角下载
    """

    def __init__(self, title: str, description: str, html_path: str, detail_text: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.description = description
        self.html_path = html_path
        self.detail_text = detail_text
        self.is_expanded = True  # 初始状态设为展开

        self._init_ui()

    def _init_ui(self):
        # 整体竖向布局
        self.v_layout = QVBoxLayout(self)
        self.v_layout.setContentsMargins(20, 20, 20, 20)
        self.v_layout.setSpacing(12)

        # === 1. 顶部栏 (Header) ===
        self.header_layout = QHBoxLayout()
        self.title_layout = QVBoxLayout()
        self.title_layout.setSpacing(6)

        # 主标题
        self.title_label = SubtitleLabel(self.title, self)

        # 带有 i 图标的可悬浮说明区
        self.info_widget = ClickableInfoWidget(self.description, self.detail_text, self)

        self.title_layout.addWidget(self.title_label)
        self.title_layout.addWidget(self.info_widget)

        # 右上角导出/下载按钮
        self.btn_export = TransparentToolButton(FIF.DOWNLOAD, self)
        self.btn_export.setToolTip("保存 HTML 交互图表")
        self.btn_export.clicked.connect(self._export_html)

        # 展开/收起按钮
        self.btn_expand = TransparentToolButton(FIF.INFO, self)
        self.btn_expand.setToolTip("收起图表")
        self.btn_expand.clicked.connect(self._toggle_chart)

        self.header_layout.addLayout(self.title_layout)
        self.header_layout.addStretch(1)
        self.header_layout.addWidget(self.btn_export, 0, Qt.AlignTop)
        self.header_layout.addWidget(self.btn_expand, 0, Qt.AlignTop)

        # === 2. Web 渲染区 (Content) ===
        self.web_view = CustomWebEngineView(self)
        self.web_view.setMinimumHeight(400)
        self.web_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # self.web_view.page().setBackgroundColor(Qt.transparent)
        self.web_view.setStyleSheet("background-color: #f9f9f9;")

        if os.path.exists(self.html_path):
            self.web_view.load(QUrl.fromLocalFile(os.path.abspath(self.html_path)))

        # 组装总体布局
        self.v_layout.addLayout(self.header_layout)
        self.v_layout.addWidget(self.web_view)

    def _toggle_chart(self):
        """控制图表渲染区的展开与收起"""
        self.is_expanded = not self.is_expanded
        self.web_view.setVisible(self.is_expanded)
        icon = FIF.CHEVRON_UP if self.is_expanded else FIF.CHEVRON_DOWN
        self.btn_expand.setIcon(icon)
        self.btn_expand.setToolTip("收起图表" if self.is_expanded else "展开图表")

    def _export_html(self):
        if not os.path.exists(self.html_path):
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self, "导出交互图表", f"{self.title}.html", "HTML Files (*.html)"
        )
        if save_path:
            try:
                shutil.copyfile(self.html_path, save_path)
                InfoBar.success("导出成功", f"图表已保存至: {save_path}", parent=self.window(),
                                position=InfoBarPosition.BOTTOM_RIGHT)
            except Exception as e:
                InfoBar.error("导出失败", str(e), parent=self.window(), position=InfoBarPosition.BOTTOM_RIGHT)
