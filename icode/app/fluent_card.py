from PyQt5.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QGraphicsDropShadowEffect
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWebEngineWidgets import QWebEngineView


class FluentCard(QFrame):
    """Fluent 风格卡片组件 - 用于显示图表"""

    expand_clicked = pyqtSignal()  # 展开详情信号

    def __init__(self, title: str, subtitle: str, description: str = "",
                 icon: str = "", parent=None):
        super().__init__(parent)

        # 基础设置
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setObjectName("FluentCard")
        self.setStyleSheet("""
            #FluentCard {
                background-color: #2d2d44;
                border-radius: 12px;
                border: 1px solid #3d3d5c;
            }
            #FluentCard:hover {
                background-color: #363654;
                border: 1px solid #5a5a8a;
            }
        """)

        # 阴影效果
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 16, 20, 16)
        self.main_layout.setSpacing(10)

        # ========== 标题区 ==========
        title_layout = QHBoxLayout()
        title_layout.setSpacing(10)

        # 图标
        if icon:
            self.icon_label = QLabel(icon)
            self.icon_label.setFont(QFont("Segoe UI Emoji", 16))
            self.icon_label.setStyleSheet("background: transparent;")
            title_layout.addWidget(self.icon_label)

        # 标题和副标题
        title_container = QWidget()
        title_layout_inner = QVBoxLayout(title_container)
        title_layout_inner.setContentsMargins(0, 0, 0, 0)
        title_layout_inner.setSpacing(2)

        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        self.title_label.setStyleSheet("color: #FFFFFF; background: transparent;")

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setFont(QFont("Microsoft YaHei", 10))
        self.subtitle_label.setStyleSheet("color: #888888; background: transparent;")

        title_layout_inner.addWidget(self.title_label)
        title_layout_inner.addWidget(self.subtitle_label)
        title_layout.addWidget(title_container)
        title_layout.addStretch()

        self.main_layout.addLayout(title_layout)

        # ========== 内容区 ==========
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 8, 0, 0)
        self.content_layout.setSpacing(8)
        self.main_layout.addWidget(self.content_widget)

        # ========== 展开说明 ==========
        self.description = description
        self.is_expanded = False

        if description:
            self.expand_label = QLabel("📖 点击查看详情")
            self.expand_label.setFont(QFont("Microsoft YaHei", 9))
            self.expand_label.setStyleSheet("""
                color: #00BFFF;
                background: transparent;
                padding: 4px 8px;
                border-radius: 4px;
            """)
            self.expand_label.setCursor(Qt.PointingHandCursor)
            self.expand_label.mousePressEvent = self._toggle_description
            self.main_layout.addWidget(self.expand_label)

            self.description_label = QLabel(description)
            self.description_label.setFont(QFont("Microsoft YaHei", 9))
            self.description_label.setStyleSheet("color: #666666; background: transparent;")
            self.description_label.setWordWrap(True)
            self.description_label.setVisible(False)
            self.main_layout.addWidget(self.description_label)

        # 最小尺寸
        self.setMinimumSize(340, 280)

    def _toggle_description(self, event):
        """切换详情显示"""
        self.is_expanded = not self.is_expanded
        self.description_label.setVisible(self.is_expanded)
        self.expand_label.setText("📖 收起详情" if self.is_expanded else "📖 点击查看详情")
        self.expand_clicked.emit()

    def add_web_view(self, html_content: str, height: int = 280):
        """添加 WebEngineView 显示 Plotly 图表"""
        web_view = QWebEngineView(self)
        web_view.setHtml(html_content)
        web_view.setMinimumHeight(height)
        web_view.setStyleSheet("background: transparent; border: none;")
        self.content_layout.addWidget(web_view)

    def update_title(self, title: str):
        """更新标题"""
        self.title_label.setText(title)

    def update_subtitle(self, subtitle: str):
        """更新副标题"""
        self.subtitle_label.setText(subtitle)