# -*- coding: utf-8 -*-
"""
main.py
入口文件：负责拉起 FluentWindow，将 `app/pages` 中的各个模块页面挂载到侧边栏。
工程化结构改造后此文件不再包含臃肿的算法分发逻辑。
"""

import sys
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QApplication

from qfluentwidgets import (
    FluentWindow,
    NavigationItemPosition,
    setTheme, 
    Theme,
    setThemeColor
)
from qfluentwidgets import FluentIcon as FIF

# 导入业务独立页面
from app.pages import (
    EEGSourcePage,
    EEGConnectivityPage,
    FMRIActivationPage,
    FMRIConnectivityPage,
    LogReportPage,
    SettingsPage
)

class EEGFMRIFluentApp(FluentWindow):
    def __init__(self):
        super().__init__()
        
        # 1. 优先基础设置与初始化
        self._init_window_spec()
        
        # 2. 依次实例化组件页面
        self.page_eeg_src = EEGSourcePage(self)
        self.page_eeg_conn = EEGConnectivityPage(self)
        self.page_fmri_act = FMRIActivationPage(self)
        self.page_fmri_conn = FMRIConnectivityPage(self)
        
        self.page_log = LogReportPage(self)
        self.page_setting = SettingsPage(self)

        # 3. 挂载到左侧导航树
        self._init_navigation()

    def _init_window_spec(self):
        self.resize(1100, 780)
        self.setWindowTitle("EEG/fMRI 模板脑可视化工具")
        
        # 设置默认亮色主题以符合科学计算普遍交互观感
        setTheme(Theme.LIGHT)
        setThemeColor("#1677ff") # 默认选用医学蓝
        
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