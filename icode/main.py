# -*- coding: utf-8 -*-
"""
main.py
入口文件：负责拉起 FluentWindow，将 `app/pages` 中的各个模块页面挂载到侧边栏。
工程化结构改造后此文件不再包含臃肿的算法分发逻辑。
"""

import sys
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication
from qfluentwidgets import (
    FluentWindow,
    NavigationItemPosition,
    setTheme,
    Theme,
    setThemeColor,
    qconfig,
    SystemThemeListener,
    isDarkTheme,
    FluentStyleSheet
)
from qfluentwidgets import FluentIcon as FIF
from app.common.style_sheet import StyleSheet
from app.common.config import cfg
import qfluentwidgets, sys

# 导入业务独立页面
from app.pages import (
    EEGSourcePage,
    EEGConnectivityPage,
    FMRIActivationPage,
    FMRIConnectivityPage,
    LogReportPage,
    SettingsPage
)

from app.common import resource

class EEGFMRIFluentApp(FluentWindow):
    def __init__(self):
        super().__init__()
        self.themeListener = SystemThemeListener(self)
        # 1. 优先基础设置与初始化
        self._init_window_spec()
        
        # 2. 依次实例化组件页面
        self.page_eeg_src = EEGSourcePage(self)
        self.page_eeg_conn = EEGConnectivityPage(self)
        self.page_fmri_act = FMRIActivationPage(self)
        self.page_fmri_conn = FMRIConnectivityPage(self)
        
        self.page_log = LogReportPage(self)
        self.page_setting = SettingsPage(self)

        self._all_pages = [
            self.page_eeg_src, self.page_eeg_conn,
            self.page_fmri_act, self.page_fmri_conn,
            self.page_log, self.page_setting
        ]

        # 3. 挂载到左侧导航树
        self._init_navigation()

        qconfig.themeChanged.connect(self._on_theme_changed)
        self.themeListener.start()

        self._on_theme_changed(cfg.theme)
        print(cfg.themeColor)
        StyleSheet.MAIN.apply(self)

    def _init_window_spec(self):
        self.resize(1100, 780)
        self.setWindowTitle("EEG/fMRI 模板脑可视化工具")

        # setThemeColor("#1677ff")
        setThemeColor(cfg.themeColor.value)

        self.setMicaEffectEnabled(True)
        
        desktop = QApplication.desktop().availableGeometry()
        self.move(
            desktop.width() // 2 - self.width() // 2,
            desktop.height() // 2 - self.height() // 2,
        )

    def _init_navigation(self):
        # 功能区
        self.addSubInterface(self.page_eeg_src, FIF.PHOTO, "EEG源定位")
        self.addSubInterface(self.page_eeg_conn, FIF.TILES, "EEG功能连接")
        self.addSubInterface(self.page_fmri_act, FIF.VIDEO, "fMRI激活定位")
        self.addSubInterface(self.page_fmri_conn, FIF.TAG, "fMRI功能连接")
        
        self.navigationInterface.addSeparator()
        
        # 最底部系统面板
        self.addSubInterface(self.page_log, FIF.DOCUMENT, "日志中心", NavigationItemPosition.BOTTOM)
        self.addSubInterface(self.page_setting, FIF.SETTING, "系统设置", NavigationItemPosition.BOTTOM)

    def _on_theme_changed(self, theme: Theme):
        StyleSheet.MAIN.apply(self)

        # 刷新所有子页面
        for page in self._all_pages:
            if hasattr(page, '_on_theme_changed'):
                page._on_theme_changed(theme)

        # 刷新窗口
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
        QApplication.processEvents()

    def closeEvent(self, e):
        self.themeListener.terminate()
        self.themeListener.deleteLater()
        super().closeEvent(e)

    def _onThemeChangedFinished(self):
        super()._onThemeChangedFinished()

        # retry
        if self.isMicaEffectEnabled():
            QTimer.singleShot(100, lambda: self.windowEffect.setMicaEffect(self.winId(), isDarkTheme()))

if __name__ == "__main__":
    # 高分屏支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    
    # 解决部分布局边缘可能触发的本地控件样式杂乱
    app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings)

    window = EEGFMRIFluentApp()
    window.show()
    sys.exit(app.exec_())