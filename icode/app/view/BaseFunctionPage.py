# -*- coding: utf-8 -*-
import os
import ast
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QMainWindow
)

from qfluentwidgets import (
    ScrollArea,  Theme, InfoBar, InfoBarPosition,
    IndeterminateProgressBar,
    SubtitleLabel, BodyLabel
)
from .CustomWebEngineView import CustomWebEngineView
from ..common.style_sheet import StyleSheet
from pathlib import Path

class VisualizationWebWindow(QMainWindow):
    """仅负责显示 HTML 可视化结果的子窗口（可全屏/可交互）"""

    def __init__(self, html_path: str, title: str = "可视化结果", parent=None):
        super().__init__(parent)
        self._html_path = html_path
        self.setWindowTitle(title)
        self.resize(1280, 860)

        self.web = CustomWebEngineView(self)

        self.setCentralWidget(self.web)
        self.web.load(QUrl.fromLocalFile(os.path.abspath(html_path)))

        self.web.load(QUrl.fromLocalFile(os.path.abspath(html_path)))


# ==========================================
# 基础功能页面模板 (包含固定底部的进度状态栏)
# ==========================================
class BaseFunctionPage(ScrollArea):
    """提取四大功能页的共用逻辑：标题、文件选择、运行按钮、以及置底的进度条"""
    def __init__(self, title: str, description: str, module_name: str, parent=None):
        super().__init__(parent=parent)
        self.module_name = module_name
        self.setObjectName(title.replace(" ", "_"))
        # 保留圆角与无边框，不覆盖 Fluent 的主题背景绘制
        self.setWidgetResizable(True)
        self.setFrameShape(self.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # 移除强制样式覆盖，改用 FluentWidgets 推荐的透明化配置
        self.viewport().setObjectName("FunctionPageViewport")

        self.view = QWidget(self)
        self.view.setObjectName("FunctionPageView")

        # 主布局
        self.main_layout = QVBoxLayout(self.view)
        self.main_layout.setContentsMargins(36, 36, 36, 36)
        self.main_layout.setSpacing(24)

        # 建立标题区
        self.title_label = SubtitleLabel(title, self.view)
        self.desc_label = BodyLabel(description, self.view)
        self.desc_label.setWordWrap(True)
        # 使用 QFluentWidgets 默认配色，确保在深浅主题下均有良好的可读性

        self.main_layout.addWidget(self.title_label)
        self.main_layout.addWidget(self.desc_label)

        # 内容填充区 (子类在这里添加自己的输入和设置控件)
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(16)
        self.main_layout.addLayout(self.content_layout)

        self.main_layout.addStretch(1)

        # 底部状态展示区 (固定在页面下方)
        self._build_status_bar()
        self.main_layout.addWidget(self.status_container)

        self.setWidget(self.view)
        self.worker = None # 后台工作线程引用，防止被回收
        self.view.setObjectName('view')
        self.base_dir = Path(__file__).resolve().parent.parent.parent

    def _build_status_bar(self):
        # 进度状态外层布局
        self.status_container = QWidget(self.view)
        self.status_layout = QVBoxLayout(self.status_container)
        self.status_layout.setContentsMargins(0, 0, 0, 0)
        self.status_layout.setSpacing(6)

        # 状态小字，靠右对齐
        self.status_label = BodyLabel("当前状态...", self.status_container)
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_label.setStyleSheet("font-size: 13px;")

        # 左右循环播放的进度条
        self.progress_bar = IndeterminateProgressBar(self.status_container,0.4)
        self.status_layout.addWidget(self.status_label)
        self.status_layout.addWidget(self.progress_bar)

        # 默认隐藏整个组件，运行时才展现
        self.status_container.setVisible(False)

    def set_running_state(self, is_running: bool, msg: str = "运行中..."):
        """统一切换底部状态：运行时显示并开启控件锁，否则关闭条幅"""
        self.status_container.setVisible(is_running)
        self.status_label.setText(msg)
        self.view.setEnabled(not is_running) # 运行期间锁定页面除状态栏外的操作

    def check_file_selected(self, file_path: str, ext_tuple: tuple, err_msg: str):
        if not file_path:
            InfoBar.warning("提示", "请选择需要处理的文件。", parent=self, position=InfoBarPosition.TOP_RIGHT)
            return False
        if not os.path.exists(file_path):
            InfoBar.error("错误", "所选文件不存在。", parent=self, position=InfoBarPosition.TOP_RIGHT)
            return False
        if not file_path.endswith(ext_tuple):
            InfoBar.error("错误", err_msg, parent=self, position=InfoBarPosition.TOP_RIGHT)
            return False
        return True

    def show_success_dialog(self, title: str, content: str):
        # 优化原有的弹窗，使用 InfoBar 组件在页面内进行不打断的通知
        InfoBar.success(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=3000,
            parent=self.window()
        )

    def show_error_dialog(self, title: str, content: str):
        InfoBar.error(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=-1,
            parent=self.window()
        )

    def show_html_in_subwindow(self, html_path: str, title: str):
        """仅显示逻辑：将 HTML 在 QWebEngineView 子窗口中打开"""
        if not html_path or not os.path.exists(html_path):
            return
        self._viz_window = VisualizationWebWindow(html_path, title=title, parent=self.window())
        self._viz_window.show()

    def _on_theme_changed(self, theme: Theme):
        StyleSheet.MAIN.apply(self)

        # 刷新窗口
        self.update()
        self.repaint()
        QApplication.processEvents()

    def _clear_previous_cards(self):
        """清空之前生成的卡片容器（防止多次运行后无限往下叠加）"""
        if hasattr(self, 'cards_container') and self.cards_container is not None:
            self.content_layout.removeWidget(self.cards_container)
            self.cards_container.deleteLater()
            self.cards_container = None
