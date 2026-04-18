# -*- coding: utf-8 -*-
"""
core.py
核心服务模块：提供统一的日志管理、OSS上传逻辑以及各模块专用的异步工作线程。
"""

import os
import oss2
import traceback
from datetime import datetime
from PyQt5.QtCore import QThread, pyqtSignal, QObject

# ======== 常量定义 ========
MODULE_EEG_SOURCE = "EEG源定位"
MODULE_EEG_CONN = "EEG功能连接"
MODULE_FMRI_ACT = "fMRI激活定位"
MODULE_FMRI_CONN = "fMRI功能连接"
MODULE_NETWORK = "网络与云服务"  
MODULE_SYSTEM = "系统"

# ======== 新增：日志节流器（防止刷屏卡死 UI） ========
class LogThrottler:
    def __init__(self, signal, interval_ms=200):
        self.signal = signal
        self.interval = interval_ms
        self.buffer = []
        self.last_time = datetime.now()

    def emit(self, msg):
        # 统一转换为字符串，避免上游 logger 传入 list/dict 导致 join 报错
        self.buffer.append(str(msg))
        now = datetime.now()
        if (now - self.last_time).total_seconds() * 1000 > self.interval:
            self._flush()
            self.last_time = now

    def _flush(self):
        if self.buffer:
            # 仅发射最新一条，避免一次性多行刷到前端造成卡顿
            self.signal.emit(self.buffer[-1])
            self.buffer = []

    def finish(self):
        self._flush()

# ======== 全局日志管理 ========
class LogManager(QObject):
    log_updated = pyqtSignal()
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.__initialized = False
        return cls._instance
        
    def __init__(self):
        if self.__initialized: return
        super().__init__()
        self.records = []
        self.__initialized = True

    def add_log(self, text: str, module: str = MODULE_SYSTEM):
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record = {"time": time_str, "module": module, "text": text}
        self.records.append(record)
        self.log_updated.emit()

    def get_logs(self, module_filter=None):
        if not module_filter or module_filter == "全部模块":
            return [f"[{r['time']}] [{r['module']}] {r['text']}" for r in self.records]
        return [f"[{r['time']}] [{r['module']}] {r['text']}" for r in self.records if r['module'] == module_filter]
    
    def clear(self):
        self.records.clear()
        self.log_updated.emit()

# 实例化全局对象
log_manager = LogManager()

# ======== OSS 路径配置表 ========
UPLOAD_CONFIG = {
    "EEG_SOURCE": {
        "main": "EEG源定位/EEG源定位图",
        "gfp_path": "EEG源定位/全球功率时间曲线图",
        "psd_path": "EEG源定位/源活动功率谱密度图",
        "hist_path": "EEG源定位/激活强度分布直方图",
        "top15_path": "EEG源定位/脑区激活 TOP15 柱状图"
    },
    "EEG_CONN": {
        "main": "EEG功能连接/交互式EEG脑网络三维图",
        "fc_matrix_path": "EEG功能连接/功能连接强度矩阵",
        "fc_hub_path": "EEG功能连接/网络核心枢纽排名图",
        "fc_distance_path": "EEG功能连接/距离-强度相关性散点图",
        "fc_distribution_path": "EEG功能连接/连接强度分布直方图"
    },
    "FMRI_ACT": {
        "main": "fMRI激活定位/fMRI脑区激活定位图",
        "histogram": "fMRI激活定位/激活强度分布直方图",
        "curve": "fMRI激活定位/阈值-激活体素数曲线",
        "summary_json": "fMRI激活定位/fMRI脑区激活总结"
    },
    "FMRI_CONN": {
        "main": "fMRI功能连接/3D交互式功能连接脑网络图",
        "path_full_heatmap": "fMRI功能连接/全脑功能连接矩阵",    
        "path_heatmap": "fMRI功能连接/多时间窗口功能连接热力图", 
        "pie_path": "fMRI功能连接/正负功能连接比例饼图",        
        "path_metrics": "fMRI功能连接/滑动窗口功能连接动态指标图",
        "path_npy": "fMRI功能连接/全窗口连接矩阵npy文件",
        "path_csv": "fMRI功能连接/滑动窗口动态指标csv文件"
    }
}

from ..common.config import cfg

# ======== OSS 基础上传函数 ========
def _oss_internal_put(file_path, folder):
    try:
        access_key_id = cfg.ossAccessKeyId.value
        access_key_secret = cfg.ossAccessKeySecret.value
        endpoint = cfg.ossEndpoint.value
        bucket_name = cfg.ossBucket.value

        if not all([access_key_id, access_key_secret, endpoint, bucket_name]):
            log_manager.add_log("OSS上传失败：配置不完整，请在“网络与云服务”页面配置账号", MODULE_NETWORK)
            return None

        auth = oss2.Auth(access_key_id, access_key_secret)
        bucket = oss2.Bucket(auth, endpoint, bucket_name)
        
        filename = os.path.basename(file_path)
        object_key = f"{folder}/{filename}"

        with open(file_path, 'rb') as f:
            bucket.put_object(object_key, f)
        
        return f"https://{bucket_name}.{endpoint}/{object_key}"
    except Exception as e:
        log_manager.add_log(f"OSS上传错误: {str(e)}", MODULE_NETWORK)
        return None

# ======== 通用工作线程 ========
class WorkerThread(QThread):
    finished_sig = pyqtSignal(bool, object)
    log_sig = pyqtSignal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            self.kwargs['logger'] = lambda m: self.log_sig.emit(str(m))
            res = self.func(*self.args, **self.kwargs)
            self.finished_sig.emit(True, res)
        except Exception as e:
            self.finished_sig.emit(False, str(e) + "\n" + traceback.format_exc())

# ======== EEG 专用线程（已修复：使用日志节流器） ========
class EEGWorkerThread(QThread):
    finished_sig = pyqtSignal(bool, object)
    log_sig = pyqtSignal(str)

    def __init__(self, compute_func, render_func, bdf_path, band, duration, mode="CONN"):
        super().__init__()
        self.compute_func = compute_func
        self.render_func = render_func
        self.bdf_path = bdf_path
        self.band = band
        self.duration = duration
        self.mode = mode

    def run(self):
        try:
            # 使用日志节流器：每 200ms 最多发射一次日志
            throttler = LogThrottler(self.log_sig, interval_ms=200)
            
            throttler.emit(f"开始执行 {self.mode} 计算...")
            raw_data = self.compute_func(self.bdf_path, analysis_band=self.band, duration_sec=self.duration, logger=lambda m: throttler.emit(m))
            
            throttler.emit("渲染结果图表...")
            result_data = self.render_func(raw_data, logger=lambda m: throttler.emit(m))
            
            # 校验result_data完整性
            required_keys = UPLOAD_CONFIG["EEG_SOURCE"].keys() if self.mode == "SOURCE" else UPLOAD_CONFIG["EEG_CONN"].keys()
            missing_keys = [k for k in required_keys if k not in result_data]
            if missing_keys:
                throttler.emit("部分结果文件缺失，已跳过对应上传。")
            
            config_key = "EEG_SOURCE" if self.mode == "SOURCE" else "EEG_CONN"
            path_map = UPLOAD_CONFIG[config_key]
            
            throttler.emit("同步结果到云端文件夹...")
            oss_urls = {}
            success_count = 0
            skip_count = 0
            fail_count = 0
            for key, folder in path_map.items():
                local_file = result_data.get(key)
                if local_file and isinstance(local_file, str) and os.path.exists(local_file):
                    url = _oss_internal_put(local_file, folder)
                    if url: 
                        oss_urls[key] = url
                        success_count += 1
                    else:
                        fail_count += 1
                else:
                    skip_count += 1
            
            result_data["share_url"] = oss_urls.get("main")
            result_data["oss_urls"] = oss_urls
            if self.mode == "SOURCE" and skip_count > 0:
                throttler.emit(
                    f"云端同步首轮完成：成功 {success_count}，失败 {fail_count}，待补传 {skip_count}。"
                    "（3D主图导出后会自动补传）"
                )
            else:
                throttler.emit(f"云端同步完成：成功 {success_count}，失败 {fail_count}，跳过 {skip_count}")
            
            throttler.finish()
            self.finished_sig.emit(True, result_data)
        except Exception as e:
            self.log_sig.emit(f"错误: {str(e)}")
            self.finished_sig.emit(False, traceback.format_exc())

# ======== fMRI 专用线程 ========
class FMRIWorkerThread(QThread):
    finished_sig = pyqtSignal(bool, object)
    log_sig = pyqtSignal(str)

    def __init__(self, processor_class, fmri_path, tr, mode="activation"):
        super().__init__()
        self.processor_class = processor_class
        self.fmri_path = fmri_path
        self.tr = tr
        self.mode = mode

    def run(self):
        try:
            processor = self.processor_class(fmri_nifti_path=self.fmri_path, tr=self.tr)
            
            if hasattr(processor, 'log_pyqtSignal'):
                processor.log_pyqtSignal.connect(self.log_sig.emit)
            elif hasattr(processor, 'log_sig'):
                processor.log_sig.connect(self.log_sig.emit)
                
            fmri_img, mask_img = processor._preprocess_fmri()
            
            result_paths = {}
            if self.mode == "activation":
               result_paths = processor._visualize_fmri_activation(fmri_img, mask_img)
               config_key = "FMRI_ACT"
            else:
               result_paths = processor._compute_fmri_connectivity(fmri_img, mask_img)
               config_key = "FMRI_CONN"

            if not isinstance(result_paths, dict):
                result_paths = {"main": result_paths}

            required_keys = UPLOAD_CONFIG[config_key].keys()
            missing_keys = [k for k in required_keys if k not in result_paths]
            if missing_keys:
                self.log_sig.emit(f"警告：result_paths缺失以下key: {missing_keys}")

            path_map = UPLOAD_CONFIG[config_key]
            oss_urls = {}
            for key, folder in path_map.items():
                local_file = result_paths.get(key)
                if local_file and isinstance(local_file, str) and os.path.exists(local_file):
                    url = _oss_internal_put(local_file, folder)
                    if url: 
                        oss_urls[key] = url
                        self.log_sig.emit(f"成功上传 {key} 到OSS")
                    else:
                        self.log_sig.emit(f"警告：{key} 上传OSS失败")
                else:
                    self.log_sig.emit(f"警告：{key} 本地文件不存在，跳过上传")

            final_result = {
                "share_url": oss_urls.get("main"),
                "oss_urls": oss_urls
            }
            final_result.update(result_paths) 

            self.finished_sig.emit(True, final_result)
            
        except Exception as e:
            self.log_sig.emit(f"发生异常: {str(e)}")
            self.finished_sig.emit(False, str(e) + "\n" + traceback.format_exc())