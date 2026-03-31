from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,QFileDialog
)

from qfluentwidgets import (
    ScrollArea, SubtitleLabel, BodyLabel,ComboBox,PushButton,TextEdit,InfoBar,InfoBarPosition
)
from qfluentwidgets import FluentIcon as FIF

from .core import log_manager, MODULE_EEG_SOURCE, MODULE_EEG_CONN, MODULE_FMRI_ACT, MODULE_FMRI_CONN, MODULE_SYSTEM
from ..common.style_sheet import StyleSheet

class LogReportPage(ScrollArea):
    """独立的系统中心日志监控面板"""
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("Log_Report")
        self.setWidgetResizable(True)
        self.setFrameShape(self.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)


        self.view = QWidget(self)
        self.view.setObjectName("LogReportPageView")

        self.main_layout = QVBoxLayout(self.view)
        self.main_layout.setContentsMargins(36, 36, 36, 36)

        self.title_label = SubtitleLabel("系统运行日志", self.view)
        self.main_layout.addWidget(self.title_label)
        self.main_layout.addSpacing(16)

        # 过滤器与操作区
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(BodyLabel("日志模块源:", self.view))

        self.combo_filter = ComboBox(self.view)
        self.combo_filter.addItems(["全部", MODULE_EEG_SOURCE, MODULE_EEG_CONN, MODULE_FMRI_ACT, MODULE_FMRI_CONN, MODULE_SYSTEM])
        self.combo_filter.currentIndexChanged.connect(self._update_log_display)
        filter_layout.addWidget(self.combo_filter)

        self.btn_export = PushButton("导出日志报表", self.view, FIF.DOWNLOAD)
        self.btn_export.clicked.connect(self._export_log)
        filter_layout.addWidget(self.btn_export)

        self.btn_clear = PushButton("清理屏幕", self.view, FIF.DELETE)
        self.btn_clear.clicked.connect(self._clear_log)
        filter_layout.addWidget(self.btn_clear)

        filter_layout.addStretch(1)
        self.main_layout.addLayout(filter_layout)

        # 多行只读本文显示区
        self.text_editor = TextEdit(self.view)
        self.text_editor.setReadOnly(True)
        self.text_editor.setPlaceholderText("暂无日志报告...")
        self.main_layout.addWidget(self.text_editor, stretch=1)

        self.setWidget(self.view)

        # 绑定核心派发器刷新UI
        log_manager.log_updated.connect(self._update_log_display)
        StyleSheet.MAIN.apply(self)

    def _update_log_display(self):
        mod = self.combo_filter.currentText()
        lines = log_manager.get_logs(mod)
        self.text_editor.setPlainText("\n".join(lines))
        self.text_editor.verticalScrollBar().setValue(self.text_editor.verticalScrollBar().maximum())

    def _clear_log(self):
        log_manager.clear()

    def _export_log(self):
        mod = self.combo_filter.currentText()
        lines = log_manager.get_logs(mod)
        if not lines:
            InfoBar.warning("导出提示", "当前过滤器下没有可导出的日志。", parent=self.window(), position=InfoBarPosition.BOTTOM_RIGHT)
            return

        path, _ = QFileDialog.getSaveFileName(self, "导出运行记录", f"system_logs_{mod}.txt", "Text Files (*.txt)")
        if path:
            with open(path, "w", encoding='utf-8') as f:
                f.write("\n".join(lines))
            InfoBar.success("导出完成", f"日志报告已落地到指定记录:\n{path}", parent=self.window(), position=InfoBarPosition.BOTTOM_RIGHT)
