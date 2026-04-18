# -*- coding: utf-8 -*-
from datetime import datetime
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidgetItem, QHeaderView, QFileDialog, QApplication

from qfluentwidgets import TableWidget, EditableComboBox, StrongBodyLabel, PushButton, Theme
from qfluentwidgets import FluentIcon as FIF

from .core import (
    log_manager, MODULE_SYSTEM, MODULE_EEG_SOURCE, 
    MODULE_EEG_CONN, MODULE_FMRI_ACT, MODULE_FMRI_CONN, MODULE_NETWORK
)
from ..common.style_sheet import StyleSheet


class LogReportPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("LogReportPageView")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(36, 36, 36, 36)
        self.layout.setSpacing(24)
        self._init_style()
        
        # 标题
        self.title = StrongBodyLabel("系统日志", self)
        self.title.setStyleSheet("font-size: 20px; margin-bottom: 10px;")
        
        # 工具栏
        self.tool_layout = QHBoxLayout()
        self.module_filter = EditableComboBox(self)
        self.module_filter.addItems(["全部模块", MODULE_EEG_SOURCE, MODULE_EEG_CONN, MODULE_FMRI_ACT, MODULE_FMRI_CONN, MODULE_NETWORK, MODULE_SYSTEM])
        self.module_filter.currentIndexChanged.connect(self._update_table)
        
        self.btn_refresh = PushButton("手动刷新", self, FIF.SYNC)
        self.btn_refresh.clicked.connect(self._update_table)
        
        # 导出日志按钮
        self.btn_export = PushButton("导出日志", self, FIF.SAVE)
        self.btn_export.clicked.connect(self._export_logs)
        
        # 清空日志按钮
        self.btn_clear = PushButton("清空日志", self, FIF.DELETE)
        self.btn_clear.clicked.connect(self._clear_logs)

        self.tool_layout.addWidget(self.module_filter)
        self.tool_layout.addStretch(1)
        self.tool_layout.addWidget(self.btn_refresh)
        self.tool_layout.addWidget(self.btn_export)
        self.tool_layout.addWidget(self.btn_clear)
        
        # 表格
        self.table = TableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["时间", "模块", "内容"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        
        self.layout.addWidget(self.title)
        self.layout.addLayout(self.tool_layout)
        self.layout.addWidget(self.table)
        
        # 定时器刷新
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_table)
        self.timer.start(2000)
        
        self._update_table()

    def _update_table(self):
        self.table.setRowCount(0)
        filter_text = self.module_filter.text()
        records = getattr(log_manager, 'records', [])
        
        for record in reversed(records):
            mod = record.get("module", "")
            if filter_text != "全部模块" and filter_text != mod:
                continue
            
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(record.get("time", "")))
            self.table.setItem(row, 1, QTableWidgetItem(mod))
            self.table.setItem(row, 2, QTableWidgetItem(record.get("text", "")))

    # 导出日志
    def _export_logs(self):
        records = getattr(log_manager, 'records', [])
        if not records:
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "保存日志", f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "日志文件 (*.txt);;所有文件 (*.*)"
        )
        if not filename:
            return

        filter_text = self.module_filter.text()
        with open(filename, "w", encoding="utf-8") as f:
            f.write("时间\t模块\t内容\n")
            f.write("-"*80 + "\n")
            
            for record in reversed(records):
                mod = record.get("module", "")
                if filter_text != "全部模块" and filter_text != mod:
                    continue
                
                time_str = record.get("time", "")
                text = record.get("text", "")
                f.write(f"{time_str}\t{mod}\t{text}\n")

    # 清空日志
    def _clear_logs(self):
        if hasattr(log_manager, 'records'):
            log_manager.records.clear()
        self._update_table()

    def _init_style(self):
        StyleSheet.MAIN.apply(self)

    def _on_theme_changed(self, theme: Theme):
        """主题切换刷新样式 (由 main.py 调用)"""
        StyleSheet.MAIN.apply(self)
        self.update()
        self.repaint()
        QApplication.processEvents()