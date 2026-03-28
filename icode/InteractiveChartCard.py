import os
import shutil
from PyQt5.QtCore import Qt, QUrl, pyqtSignal, QEvent
from PyQt5.QtGui import QColor, QDesktopServices
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QFileDialog, QWidget, QSizePolicy
from CustomWebEnginePage import CustomWebEngineView
from qfluentwidgets import (
    CardWidget, SubtitleLabel, CaptionLabel, TransparentToolButton,
    FluentIcon as FIF, BodyLabel, InfoBar, InfoBarPosition, IconWidget, Flyout, FlyoutAnimationType, PushButton,
    FlyoutView, FluentIcon, PrimaryPushButton
)
from app.common.style_sheet import StyleSheet

class ClickableInfoWidget(QWidget):
    def __init__(self, text, detail_text, chart_name ,tutorial_url="", image_url = "",parent=None):
        super().__init__(parent)
        self.detail_text = detail_text
        self.chart_name = chart_name
        self.image_url = image_url
        self.tutorial_url = tutorial_url
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 'i' 图标 (Info)
        self.icon = IconWidget(FIF.INFO, self)
        self.icon.setFixedSize(16, 16)

        # 说明文字，使用 Fluent 的弱化标签
        self.label = CaptionLabel(text, self)

        layout.addWidget(self.icon)
        layout.addWidget(self.label)
        layout.addStretch(1)

        self.setCursor(Qt.PointingHandCursor)
        self.installEventFilter(self)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._show_explanation_flyout()
        super().mousePressEvent(event)

    def _show_explanation_flyout(self):
        """鼠标点击时，平滑弹出气泡卡片展示详细释义"""
        original_title = self.chart_name
        original_content = self.detail_text

        view = FlyoutView(
            title=self.chart_name,
            content=self.detail_text,
            image=self.image_url,
            isClosable=True
        )

        view.titleLabel.setText(original_title)
        view.contentLabel.setText(original_content)

        view.titleLabel.setWordWrap(True)
        view.contentLabel.setWordWrap(True)

        view.titleLabel.setFixedWidth(550)
        view.contentLabel.setFixedWidth(550)

        if self.image_url:
            view.imageLabel.setFixedWidth(400)
            view.imageLabel.setFixedHeight(200)
            view.imageLabel.setScaledContents(True)

        if self.tutorial_url != "":
            button = PrimaryPushButton(self.tr('教程'), self, FluentIcon.BOOK_SHELF)
            button.setMinimumWidth(120)
            view.addWidget(button, align=Qt.AlignRight)
            button.clicked.connect(lambda : QDesktopServices.openUrl(QUrl(self.tutorial_url)))
            view.widgetLayout.insertSpacing(1, 4)

            view.widgetLayout.setContentsMargins(0, 4, 0, 4)

            view.viewLayout.setContentsMargins(6, 2, 6, 2)

            view.vBoxLayout.setSpacing(0)

        view.setObjectName("FlyoutView")
        # show view
        w = Flyout.make(view, self.label, self.window(),aniType=FlyoutAnimationType.DROP_DOWN)
        view.closed.connect(w.close)
        StyleSheet.INTERACTIVE_CHART_CARD.apply(view)


    def _on_flyout_closed(self):
        self._flyout_shown = False



class InteractiveChartCard(CardWidget):
    """
    重构后的交互式 Web 图表卡片控件
    具备：自适应主题、一行一图、卡片内容展开/收起、悬浮提示说明、右上角下载
    """

    def __init__(self, title: str, description: str, html_path: str, detail_text: str,chart_name:str ,tutorial_url="", image_url = "", parent=None,enable_animation=False):
        super().__init__(parent)
        self.title = title
        self.description = description
        self.html_path = html_path
        self.detail_text = detail_text
        self.chart_name = chart_name
        self.image_url = image_url
        self.tutorial_url = tutorial_url
        self.enable_animation = enable_animation
        self.is_expanded = True

        self._init_ui()

        StyleSheet.INTERACTIVE_CHART_CARD.apply(self)

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
        self.info_widget = ClickableInfoWidget(self.description, self.detail_text, self.chart_name,self.tutorial_url,self.image_url)

        self.title_layout.addWidget(self.title_label)
        self.title_layout.addWidget(self.info_widget)

        # 右上角导出/下载按钮
        self.btn_export = TransparentToolButton(FIF.DOWNLOAD, self)
        self.btn_export.setToolTip("保存 HTML 交互图表")
        self.btn_export.clicked.connect(self._export_html)

        # 展开/收起按钮
        self.btn_expand = TransparentToolButton(FIF.CHEVRON_DOWN_MED, self)
        self.btn_expand.setToolTip("收起图表")
        self.btn_expand.clicked.connect(self._toggle_chart)

        self.header_layout.addLayout(self.title_layout)
        self.header_layout.addStretch(1)

        if self.enable_animation:
            # 播放按钮
            self.btn_play = TransparentToolButton(FIF.PLAY, self)
            self.btn_play.clicked.connect(self._play_animation)

            # 暂停按钮
            self.btn_pause = TransparentToolButton(FIF.PAUSE, self)
            self.btn_pause.clicked.connect(self._pause_animation)
            self.btn_pause.setEnabled(False)

            # 重播按钮
            self.btn_replay = TransparentToolButton(FIF.UPDATE, self)
            self.btn_replay.clicked.connect(self._replay_animation)

            self.header_layout.addWidget(self.btn_play, 0, Qt.AlignTop)
            self.header_layout.addWidget(self.btn_pause, 0, Qt.AlignTop)
            self.header_layout.addWidget(self.btn_replay, 0, Qt.AlignTop)

        self.header_layout.addWidget(self.btn_export, 0, Qt.AlignTop)
        self.header_layout.addWidget(self.btn_expand, 0, Qt.AlignTop)

        # === 2. Web 渲染区 (Content) ===
        self.web_view = CustomWebEngineView(self)
        self.web_view.setMinimumHeight(400)
        self.web_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # self.web_view.page().setBackgroundColor(Qt.transparent)
        # self.web_view.page().setBackgroundColor(Qt.transparent)
        # self.web_view.setStyleSheet("background-color: #f9f9f9;")

        self.web_view.setObjectName("web_view")

        if os.path.exists(self.html_path):
            self.web_view.load(QUrl.fromLocalFile(os.path.abspath(self.html_path)))

        # 组装总体布局
        self.v_layout.addLayout(self.header_layout)
        self.v_layout.addWidget(self.web_view)



    def _toggle_chart(self):
        """控制图表渲染区的展开与收起"""
        self.is_expanded = not self.is_expanded
        self.web_view.setVisible(self.is_expanded)
        icon = FIF.REMOVE if self.is_expanded else FIF.CHEVRON_DOWN_MED
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

    # ===== 新增：动画控制方法 =====
    def _play_animation(self):
        """播放动画"""
        js_code = """
        (function() {
            console.log('[PyQt] 播放按钮被点击');
            if (window.PlotlyAnimationControl) {
                window.PlotlyAnimationControl.play();
            } else {
                console.error('[PyQt] PlotlyAnimationControl 未初始化');
            }
        })();
        """
        self.web_view.page().runJavaScript(js_code)
        self.btn_play.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.is_playing = True

    def _pause_animation(self):
        """暂停动画"""
        js_code = """
        (function() {
            console.log('[PyQt] 暂停按钮被点击');
            if (window.PlotlyAnimationControl) {
                window.PlotlyAnimationControl.pause();
            } else {
                console.error('[PyQt] PlotlyAnimationControl 未初始化');
            }
        })();
        """
        self.web_view.page().runJavaScript(js_code)
        self.btn_play.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.is_playing = False

    def _replay_animation(self):
        """重新加载页面"""
        self.web_view.reload()
        self.btn_play.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.is_playing = True