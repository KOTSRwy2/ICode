# -*- coding: utf-8 -*-
"""
source_localization.py
功能1：模板版 EEG 源定位可视化

改造说明：
1. 新增 EEGSourceLocalizationThread，用于后台执行重计算
2. 将“计算”和“显示”拆开：
   - compute_source_localization(): 后台线程执行
   - show_source_localization_window(): 主线程执行
3. 这样可以避免主界面长时间卡死未响应
"""

import os
from pathlib import Path

import mne
from mne.datasets import fetch_fsaverage
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication

from mne_style import (
    MNE_STYLE_DARK,
    MNE_STYLE_LIGHT,
)


def _default_logger(msg: str):
    print(msg)


def _get_project_root():
    """返回当前项目根目录"""
    return Path(__file__).resolve().parent


def _get_assets_dir():
    """返回 assets 文件夹路径，不存在则创建"""
    assets_dir = _get_project_root() / "assets"
    assets_dir.mkdir(exist_ok=True)
    return assets_dir


def _prepare_fsaverage(logger):
    """
    准备 fsaverage 模板：
    - 优先使用 assets/fsaverage
    - 若缺失则自动下载到 assets 目录
    """
    assets_dir = _get_assets_dir()
    fs_dir = assets_dir / "fsaverage"

    src_path = fs_dir / "bem" / "fsaverage-ico-5-src.fif"
    bem_path = fs_dir / "bem" / "fsaverage-5120-5120-5120-bem-sol.fif"

    if not fs_dir.exists() or not src_path.exists() or not bem_path.exists():
        logger("未检测到完整的 fsaverage 模板，正在自动下载到 assets 文件夹...")
        logger(f"下载目录：{assets_dir}")
        fs_dir = fetch_fsaverage(subjects_dir=assets_dir, verbose=True)
        fs_dir = Path(fs_dir)
        logger(f"fsaverage 模板已准备完成：{fs_dir}")
    else:
        logger(f"检测到本地 fsaverage 模板：{fs_dir}")

    src_path = fs_dir / "bem" / "fsaverage-ico-5-src.fif"
    bem_path = fs_dir / "bem" / "fsaverage-5120-5120-5120-bem-sol.fif"

    if not src_path.exists():
        raise FileNotFoundError(f"找不到模板源空间文件：{src_path}")
    if not bem_path.exists():
        raise FileNotFoundError(f"找不到模板 BEM 文件：{bem_path}")

    return fs_dir, src_path, bem_path


def _apply_mne_window_theme(theme: str = "auto"):
    """
    为当前所有 MNE 3D 窗口应用主题样式表
    """
    if theme == "auto":
        from qfluentwidgets import qconfig, Theme
        is_dark = qconfig.get(qconfig.themeMode) == Theme.DARK
        stylesheet = MNE_STYLE_DARK if is_dark else MNE_STYLE_LIGHT
    elif theme == "dark":
        stylesheet = MNE_STYLE_DARK
    else:
        stylesheet = MNE_STYLE_LIGHT

    app = QApplication.instance()
    if app:
        for widget in app.topLevelWidgets():
            window_title = widget.windowTitle()
            if "Source Localization" in window_title or "Brain" in window_title:
                widget.setStyleSheet(stylesheet)


def _get_band_range(analysis_band: str):
    """
    根据用户选择返回滤波范围
    """
    band_map = {
        "full": (1.0, 40.0, "全频道"),
        "alpha": (8.0, 13.0, "α频段"),
        "beta": (13.0, 30.0, "β频段"),
        "gamma": (30.0, 40.0, "γ频段"),
    }

    if analysis_band not in band_map:
        raise ValueError(f"不支持的 analysis_band：{analysis_band}")

    return band_map[analysis_band]


def compute_source_localization(
    bdf_path,
    logger=None,
    duration_sec=10,
    analysis_band="full",
    plot_theme="auto",
):
    """
    只负责重计算，不负责弹窗。
    可在后台线程中安全执行。

    返回
    ----------
    result : dict
        后续主线程显示窗口所需的数据
    """
    if logger is None:
        logger = _default_logger

    logger("========== 模板源定位开始 ==========")

    if not os.path.exists(bdf_path):
        raise FileNotFoundError(f"BDF 文件不存在：{bdf_path}")

    logger(f"BDF 文件：{bdf_path}")

    # 1. 准备模板
    fs_dir, src_path, bem_path = _prepare_fsaverage(logger)
    subject = "fsaverage"
    subjects_dir = fs_dir.parent
    trans = "fsaverage"

    logger(f"subjects_dir：{subjects_dir}")
    logger(f"src 文件：{src_path}")
    logger(f"bem 文件：{bem_path}")

    # 2. 设置 3D 后端
    logger("正在设置 3D 可视化后端...")
    mne.viz.set_3d_backend("pyvistaqt")

    # 3. 读取 BDF
    # 改成延迟加载：先裁剪，再真正加载数据，比 preload=True 更合理
    logger("正在读取 BDF 数据（延迟加载）...")
    raw = mne.io.read_raw_bdf(bdf_path, preload=False)

    logger(f"通道总数：{len(raw.ch_names)}")
    logger(f"前几个通道名：{raw.ch_names[:10]}")

    # 4. 裁剪用户选择的时间段
    total_duration = float(raw.times[-1]) if raw.n_times > 1 else 0.0

    if duration_sec is None:
        actual_duration = total_duration
        logger("用户选择：处理全部数据。")
    else:
        actual_duration = min(float(duration_sec), total_duration)
        logger(f"用户选择：处理前 {duration_sec} 秒。")
        if total_duration < float(duration_sec):
            logger(f"原始数据总时长只有 {total_duration:.2f} 秒，因此将处理全部数据。")

    if actual_duration > 0:
        raw.crop(tmin=0.0, tmax=actual_duration)

    logger(f"实际参与处理的数据时长：{raw.times[-1]:.2f} 秒")

    logger("正在将所选时间段加载到内存...")
    raw.load_data()
    logger("数据加载完成。")

    # 5. 非 EEG 通道处理
    logger("正在处理非 EEG 通道...")
    ch_type_map = {}
    for ch in raw.ch_names:
        ch_upper = ch.upper()
        if ch_upper == "ECG":
            ch_type_map[ch] = "ecg"
        elif ch_upper in ["EMG1", "EMG2"]:
            ch_type_map[ch] = "emg"

    if ch_type_map:
        raw.set_channel_types(ch_type_map)
        logger(f"已设置非 EEG 通道类型：{ch_type_map}")
    else:
        logger("未发现 ECG / EMG1 / EMG2，跳过非 EEG 通道设置。")

    # 6. 设置标准电极模板
    logger("正在设置 standard_1020 电极模板...")
    raw.set_montage("standard_1020", on_missing="ignore")

    # 7. 预处理
    l_freq, h_freq, band_label = _get_band_range(analysis_band)
    logger(f"正在进行预处理：平均参考 + {band_label} 滤波（{l_freq}-{h_freq} Hz）...")
    raw.set_eeg_reference(projection=True)
    raw.filter(l_freq, h_freq, picks="eeg")

    # 8. 加载模板模型
    logger("正在加载模板源空间和 BEM...")
    src = mne.read_source_spaces(src_path)
    bem = mne.read_bem_solution(bem_path)

    # 9. 构建正向解
    logger("正在构建 forward solution...")
    fwd = mne.make_forward_solution(
        raw.info,
        trans=trans,
        src=src,
        bem=bem,
        eeg=True,
        meg=False,
        mindist=5.0,
        n_jobs=1,
    )

    # 10. 计算协方差
    logger("正在计算 EEG 协方差...")
    cov = mne.compute_raw_covariance(raw, picks="eeg", method="auto")

    # 11. 构建逆算子
    logger("正在构建 inverse operator...")
    inverse_operator = mne.minimum_norm.make_inverse_operator(
        raw.info,
        fwd,
        cov,
        loose=0.2,
        depth=0.8,
    )

    # 12. 逆向求解
    logger("正在进行逆向求解（当前所选时间段）...")
    stc = mne.minimum_norm.apply_inverse_raw(
        raw,
        inverse_operator,
        lambda2=1.0 / 9.0,
        method="dSPM",
        start=0,
        stop=raw.n_times,
        pick_ori=None,
    )

    if len(stc.times) == 0:
        raise ValueError("stc.times 为空，无法设置 initial_time。")

    initial_time = float(stc.times[len(stc.times) // 2])

    logger("源定位计算完成，准备返回主线程显示 3D 窗口。")
    logger("========== 模板源定位计算结束 ==========")

    return {
        "stc": stc,
        "subject": subject,
        "subjects_dir": str(subjects_dir),
        "initial_time": initial_time,
        "band_label": band_label,
        "plot_theme": plot_theme,
    }


def show_source_localization_window(result, logger=None):
    """
    只负责在主线程中弹出 3D 窗口
    """
    if logger is None:
        logger = _default_logger

    stc = result["stc"]
    subject = result["subject"]
    subjects_dir = result["subjects_dir"]
    initial_time = result["initial_time"]
    band_label = result["band_label"]
    plot_theme = result["plot_theme"]

    logger("正在弹出 3D 源定位窗口...")

    if plot_theme == "dark":
        bg_color = "#161618"
        fg_color = "white"
    elif plot_theme == "light":
        bg_color = "#F5F7FA"
        fg_color = "black"
    else:
        bg_color = "black"
        fg_color = None

    brain = stc.plot(
        subject=subject,
        subjects_dir=subjects_dir,
        initial_time=initial_time,
        hemi="both",
        views="lateral",
        size=(1000, 700),
        title=f"Template Source Localization - {band_label}",
        time_viewer=True,
        background=bg_color,
        foreground=fg_color,
        brain_kwargs={
            "theme": "dark",
            "silhouette": False,
            "interaction": "trackball",
        },
    )

    _apply_mne_window_theme(plot_theme)

    logger("模板源定位完成。")
    logger("========== 模板源定位结束 ==========")

    return brain


def run_source_localization(
    bdf_path,
    logger=None,
    duration_sec=10,
    analysis_band="full",
    plot_theme="auto",
):
    """
    兼容旧调用方式：
    同步执行计算 + 弹窗
    """
    result = compute_source_localization(
        bdf_path=bdf_path,
        logger=logger,
        duration_sec=duration_sec,
        analysis_band=analysis_band,
        plot_theme=plot_theme,
    )
    show_source_localization_window(result, logger=logger)
    return result["stc"]


class EEGSourceLocalizationThread(QThread):
    """
    EEG 源定位后台线程：
    - 线程里只做重计算
    - 算完通过 result_pyqtSignal 把结果发回主线程
    """
    log_pyqtSignal = pyqtSignal(str)
    result_pyqtSignal = pyqtSignal(object)
    finish_pyqtSignal = pyqtSignal()
    error_pyqtSignal = pyqtSignal(str)

    def __init__(self, bdf_path, duration_sec=10, analysis_band="full", plot_theme="auto"):
        super().__init__()
        self.bdf_path = bdf_path
        self.duration_sec = duration_sec
        self.analysis_band = analysis_band
        self.plot_theme = plot_theme

    def _log(self, msg: str):
        self.log_pyqtSignal.emit(msg)

    def run(self):
        try:
            result = compute_source_localization(
                bdf_path=self.bdf_path,
                logger=self._log,
                duration_sec=self.duration_sec,
                analysis_band=self.analysis_band,
                plot_theme=self.plot_theme,
            )
            self.result_pyqtSignal.emit(result)
            self.finish_pyqtSignal.emit()
        except Exception as e:
            self.error_pyqtSignal.emit(str(e))
            self.log_pyqtSignal.emit(f"EEG源定位处理失败：{str(e)}")