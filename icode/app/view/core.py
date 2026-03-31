# -*- coding: utf-8 -*-
"""
core.py
核心服务模块，提供工程统一的常量、日志管理、以及通用的后台工作线程。
"""

import os
from datetime import datetime
from PyQt5.QtCore import QThread, pyqtSignal, QObject
import traceback

# ======== 常量定义 ========
MODULE_EEG_SOURCE = "EEG源定位"
MODULE_EEG_CONN = "EEG功能连接"
MODULE_FMRI_ACT = "fMRI激活定位"
MODULE_FMRI_CONN = "fMRI功能连接"
MODULE_SYSTEM = "系统"

# ======== 全局日志管理 ========
class LogManager(QObject):
    """
    单例日志管理器，收集各功能模块日志，并用于触发界面的日志刷新
    """
    log_updated = pyqtSignal()

    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(LogManager, cls).__new__(cls, *args, **kwargs)
            cls._instance.__initialized = False
        return cls._instance
        
    def __init__(self):
        if self.__initialized:
            return
        super().__init__()
        self.records = []
        self.__initialized = True

    def add_log(self, text: str, module: str = MODULE_SYSTEM):
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record = {
            "time": time_str,
            "module": module,
            "text": text,
            "line": f"[{time_str}] [{module}] {text}"
        }
        self.records.append(record)
        print(record["line"])
        self.log_updated.emit()

    def get_logs(self, module="全部"):
        if module == "全部":
            return [r["line"] for r in self.records]
        return [r["line"] for r in self.records if r["module"] == module]

    def clear(self):
        self.records.clear()
        self.log_updated.emit()

log_manager = LogManager()

# ======== 异步工作线程 ========
class WorkerThread(QThread):
    """
    通用后台线程，用于执行可能阻塞的主任务（如EEG处理）。
    注入自定义的 logger 将输出导回前端，不阻塞界面并提供给左下角进度条捕获。
    """
    finished_sig = pyqtSignal(bool, object)  # 运行结果：成功与否, 返回对象（路径/结果对象/错误）
    log_sig = pyqtSignal(str)                # 子线程上报细粒度运行日志

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            # 注入 logger
            self.kwargs['logger'] = self.emit_log
            res = self.func(*self.args, **self.kwargs)
            self.finished_sig.emit(True, res)
        except Exception as e:
            err = traceback.format_exc()
            self.log_sig.emit(str(e))
            self.log_sig.emit("异常详细信息:\n" + err)
            self.finished_sig.emit(False, str(e))

    def emit_log(self, msg):
        self.log_sig.emit(str(msg))

class FMRIWorkerThread(QThread):
    """
    针对 fMRI 分析专用线程，将 FMRIProcessor 的执行过程抛入后台。
    """
    finished_sig = pyqtSignal(bool, str)
    log_sig = pyqtSignal(str)

    def __init__(self, processor_class, fmri_path, tr, mode="activation"):
        super().__init__()
        self.processor_class = processor_class
        self.fmri_path = fmri_path
        self.tr = tr
        self.mode = mode # "activation" 或 "connectivity"

    def run(self):
        try:
            processor = self.processor_class(fmri_nifti_path=self.fmri_path, tr=self.tr)
            processor.log_pyqtSignal.connect(self.log_sig.emit)
            fmri_img, mask_img = processor._preprocess_fmri()
            
            if self.mode == "activation":
                html_path = processor._visualize_fmri_activation(fmri_img, mask_img)
            else:
                html_path = processor._compute_fmri_connectivity(fmri_img, mask_img)
                
            self.finished_sig.emit(True, str(html_path) if html_path else "")
        except Exception as e:
            err = traceback.format_exc()
            self.log_sig.emit(str(e))
            self.log_sig.emit("异常详细信息:\n" + err)
            self.finished_sig.emit(False, str(e))