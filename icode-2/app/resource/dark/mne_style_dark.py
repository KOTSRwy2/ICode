# -*- coding: utf-8 -*-
"""
mne_theme.py
MNE 3D 可视化窗口主题样式定义

包含：
- 深色/浅色主题样式表
- 工具栏图标颜色化处理
- 主题应用逻辑
"""

from PyQt5.QtWidgets import QApplication, QToolBar, QToolButton
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt5.QtCore import Qt, QSize, QTimer

MNE_STYLE_DARK = """
QWidget {
    background-color: #1E1E1E;
    color: #E0E0E0;
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 12px;
}
QLabel {
    color: #E0E0E0;
    background: transparent;
}
QGroupBox {
    background-color: #252525;
    color: #F0F0F0;
    border: 1px solid #404040;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #FFFFFF;
}
QSlider::groove:horizontal {
    border: 1px solid #404040;
    height: 6px;
    background: #353535;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #4A90D9;
    border: 1px solid #505050;
    width: 14px;
    margin: -4px 0;
    border-radius: 3px;
}
QSlider::handle:horizontal:hover {
    background: #5A9FE9;
}
QComboBox {
    background-color: #353535;
    color: #F0F0F0;
    border: 1px solid #454545;
    padding: 5px 10px;
    border-radius: 3px;
    min-width: 120px;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #252525;
    color: #F0F0F0;
    border: 1px solid #454545;
    selection-background-color: #4A90D9;
}
QSpinBox, QDoubleSpinBox {
    background-color: #353535;
    color: #F0F0F0;
    border: 1px solid #454545;
    padding: 4px;
    border-radius: 3px;
}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    background-color: #454545;
    border: none;
    width: 16px;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #555555;
}
QPushButton {
    background-color: #404040;
    color: #F0F0F0;
    border: 1px solid #505050;
    padding: 5px 15px;
    border-radius: 4px;
}
QPushButton:hover {
    background-color: #505050;
    border-color: #606060;
}
QPushButton:pressed {
    background-color: #353535;
}
QToolBar {
    background-color: #1E1E1E;
    border: none;
    border-bottom: 1px solid #404040;
    spacing: 8px;
    padding: 6px 10px;
    min-height: 44px;
}
QToolBar QToolButton {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 8px;
    min-width: 36px;
    min-height: 36px;
}
QToolBar QToolButton:hover {
    background-color: #404040;
}
QToolBar QToolButton:pressed {
    background-color: #505050;
}
QToolBar QLabel {
    color: #E0E0E0;
    background: transparent;
    font-size: 13px;
}
QToolBar::separator {
    background-color: #404040;
    width: 2px;
    margin: 6px 8px;
    min-height: 20px;
}
QMenuBar {
    background-color: #1E1E1E;
    color: #E0E0E0;
}
QMenu {
    background-color: #252525;
    color: #E0E0E0;
    border: 1px solid #404040;
}
QMenu::item:selected {
    background-color: #4A90D9;
}
QScrollBar:vertical {
    background-color: #1E1E1E;
    width: 14px;
    border-radius: 7px;
}
QScrollBar::handle:vertical {
    background-color: #505050;
    border-radius: 7px;
    min-height: 30px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background-color: #606060;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QToolTip {
    background-color: #252525;
    color: #F0F0F0;
    border: 1px solid #454545;
    padding: 6px 10px;
    border-radius: 3px;
}
"""

# ========== MNE 窗口浅色主题样式表 ==========
MNE_STYLE_LIGHT = """
QWidget {
    background-color: #F5F5F5;
    color: #1E1E1E;
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 12px;
}
QLabel {
    color: #1E1E1E;
    background: transparent;
}
QGroupBox {
    background-color: #FFFFFF;
    color: #1E1E1E;
    border: 1px solid #D0D0D0;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #1E1E1E;
}
QSlider::groove:horizontal {
    border: 1px solid #D0D0D0;
    height: 6px;
    background: #E5E5E5;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #1677FF;
    border: 1px solid #C0C0C0;
    width: 14px;
    margin: -4px 0;
    border-radius: 3px;
}
QSlider::handle:horizontal:hover {
    background: #2687FF;
}
QComboBox {
    background-color: #FFFFFF;
    color: #1E1E1E;
    border: 1px solid #D0D0D0;
    padding: 5px 10px;
    border-radius: 3px;
    min-width: 120px;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    color: #1E1E1E;
    border: 1px solid #D0D0D0;
    selection-background-color: #1677FF;
}
QSpinBox, QDoubleSpinBox {
    background-color: #FFFFFF;
    color: #1E1E1E;
    border: 1px solid #D0D0D0;
    padding: 4px;
    border-radius: 3px;
}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    background-color: #F0F0F0;
    border: none;
    width: 16px;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #E0E0E0;
}
QPushButton {
    background-color: #F0F0F0;
    color: #1E1E1E;
    border: 1px solid #D0D0D0;
    padding: 5px 15px;
    border-radius: 4px;
}
QPushButton:hover {
    background-color: #E0E0E0;
    border-color: #C0C0C0;
}
QPushButton:pressed {
    background-color: #D0D0D0;
}
QToolBar {
    background-color: #F5F5F5;
    border: none;
    border-bottom: 1px solid #D0D0D0;
    spacing: 8px;
    padding: 6px 10px;
    min-height: 44px;
}
QToolBar QToolButton {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 8px;
    min-width: 36px;
    min-height: 36px;
}
QToolBar QToolButton:hover {
    background-color: #E0E0E0;
}
QToolBar QToolButton:pressed {
    background-color: #D0D0D0;
}
QToolBar QLabel {
    color: #1E1E1E;
    background: transparent;
    font-size: 13px;
}
QToolBar::separator {
    background-color: #D0D0D0;
    width: 2px;
    margin: 6px 8px;
    min-height: 20px;
}
QMenuBar {
    background-color: #F5F5F5;
    color: #1E1E1E;
}
QMenu {
    background-color: #FFFFFF;
    color: #1E1E1E;
    border: 1px solid #D0D0D0;
}
QMenu::item:selected {
    background-color: #1677FF;
}
QScrollBar:vertical {
    background-color: #F5F5F5;
    width: 14px;
    border-radius: 7px;
}
QScrollBar::handle:vertical {
    background-color: #C0C0C0;
    border-radius: 7px;
    min-height: 30px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background-color: #B0B0B0;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QToolTip {
    background-color: #FFFFFF;
    color: #1E1E1E;
    border: 1px solid #D0D0D0;
    padding: 6px 10px;
    border-radius: 3px;
}
"""


def _fix_toolbar_icons(widget, theme: str):
    """
    修复 MNE 3D 窗口工具栏图标显示问题

    参数
    ----------
    widget : QMainWindow
        MNE 3D 窗口对象
    theme : str
        "dark" | "light"
    """
    for toolbar in widget.findChildren(QToolBar):
        toolbar.setFixedHeight(44)
        toolbar.setIconSize(QSize(24, 24))

        for tool_btn in toolbar.findChildren(QToolButton):
            tool_btn.setIconSize(QSize(24, 24))
            tool_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)

            # 深色主题下将图标改为白色
            if theme == "dark":
                original_icon = tool_btn.icon()
                if not original_icon.isNull():
                    pixmap = original_icon.pixmap(24, 24)
                    if not pixmap.isNull():
                        white_pixmap = QPixmap(24, 24)
                        white_pixmap.fill(Qt.transparent)

                        painter = QPainter(white_pixmap)
                        painter.setRenderHint(QPainter.Antialiasing)
                        painter.setCompositionMode(QPainter.CompositionMode_Source)
                        painter.drawPixmap(0, 0, pixmap)
                        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
                        painter.fillRect(white_pixmap.rect(), QColor(255, 255, 255))
                        painter.end()

                        tool_btn.setIcon(QIcon(white_pixmap))


def _apply_theme_delayed(app, stylesheet: str, theme: str):
    """延迟应用主题，确保窗口已完全初始化"""
    for widget in app.topLevelWidgets():
        window_title = widget.windowTitle()
        if "Source Localization" in window_title or "Brain" in window_title:
            widget.setStyleSheet(stylesheet)
            _fix_toolbar_icons(widget, theme)


def apply_mne_window_theme(theme: str = "auto"):
    # 确定使用哪个样式表
    if theme == "auto":
        from qfluentwidgets import qconfig, Theme
        is_dark = qconfig.get(qconfig.themeMode) == Theme.DARK
        stylesheet = MNE_STYLE_DARK if is_dark else MNE_STYLE_LIGHT
        effective_theme = "dark" if is_dark else "light"
    elif theme == "dark":
        stylesheet = MNE_STYLE_DARK
        effective_theme = "dark"
    else:
        stylesheet = MNE_STYLE_LIGHT
        effective_theme = "light"

    # 应用到所有顶层窗口
    app = QApplication.instance()
    if app:
        QTimer.singleShot(100, lambda: _apply_theme_delayed(app, stylesheet, effective_theme))