from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QWidget
)

from qfluentwidgets import (
    ScrollArea, ExpandLayout, SettingCardGroup,  setTheme, setThemeColor,
    SubtitleLabel, OptionsSettingCard
)
from qfluentwidgets import FluentIcon as FIF
from ..common.config import cfg
from ..common.style_sheet import StyleSheet

class SettingsPage(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("Global_Settings")
        self.setWidgetResizable(True)
        self.setFrameShape(self.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.view = QWidget(self)
        self.view.setObjectName("SettingsPageView")

        self.expand_layout = ExpandLayout(self.view)
        self.expand_layout.setContentsMargins(36, 36, 36, 36)

        self._init_ui()

    def _init_ui(self):
        title = SubtitleLabel("系统设置", self.view)
        self.expand_layout.addWidget(title)

        # 使用分组归类管理项
        self.personal_group = SettingCardGroup("界面与主题", self.view)

        self.theme_card = OptionsSettingCard(
            cfg.themeMode,
            FIF.BRUSH,
            self.tr("应用主题"),
            self.tr("更改应用的外观并重新映射内部颜色"),
            texts=[
                self.tr("浅色"), self.tr("深色"),
                self.tr("跟随系统")
            ],
            parent=self.personal_group
        )

        from qfluentwidgets import ColorSettingCard
        self.color_card = ColorSettingCard(
            cfg.themeColor,
            icon=FIF.PALETTE,
            title="主题色",
            content="自定义状态与高亮的指向色",
            parent=self.personal_group
        )

        self.personal_group.addSettingCard(self.theme_card)
        self.personal_group.addSettingCard(self.color_card)


        cfg.themeChanged.connect(setTheme)

        self.color_card.colorChanged.connect(lambda c: setThemeColor(c))

        self.expand_layout.addWidget(self.personal_group)
        self.setWidget(self.view)
        StyleSheet.MAIN.apply(self)

    def _on_theme_changed(self, theme):
        StyleSheet.MAIN.apply(self)

        # 刷新窗口
        self.update()
        self.repaint()
        QApplication.processEvents()