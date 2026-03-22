# -*- coding: utf-8 -*-
"""
source_localization.py
功能1：模板版 EEG 源定位可视化

逻辑：
1. 输入 BDF 文件
2. 优先使用项目目录下 assets/fsaverage 模板
3. 如果模板不存在或不完整，则自动下载
4. 做模板脑源定位并弹出 3D 窗口
"""

import os
from pathlib import Path

import mne
from mne.datasets import fetch_fsaverage


def _default_logger(msg: str):
    print(msg)


def _get_project_root():
    """返回当前项目根目录（也就是 EEGicode 文件夹）"""
    return Path(__file__).resolve().parent


def _get_assets_dir():
    """返回 assets 文件夹路径，不存在就创建"""
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

    # 如果本地模板不完整，则自动下载
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


def run_source_localization(bdf_path, logger=None, duration_sec=10):
    """
    运行模板版源定位可视化

    参数
    ----------
    bdf_path : str
        用户选择的 .bdf 文件路径
    logger : callable | None
        日志函数，例如 main.py 里的 self.log

    返回
    ----------
    stc : mne.SourceEstimate
        源估计结果对象
    """
    if logger is None:
        logger = _default_logger

    logger("========== 模板源定位开始 ==========")

    # -------------------------
    # 1. 基础检查
    # -------------------------
    if not os.path.exists(bdf_path):
        raise FileNotFoundError(f"BDF 文件不存在：{bdf_path}")

    logger(f"BDF 文件：{bdf_path}")

    # -------------------------
    # 2. 准备 fsaverage 模板
    # -------------------------
    fs_dir, src_path, bem_path = _prepare_fsaverage(logger)
    subject = "fsaverage"
    subjects_dir = fs_dir.parent
    trans = "fsaverage"

    logger(f"subjects_dir：{subjects_dir}")
    logger(f"src 文件：{src_path}")
    logger(f"bem 文件：{bem_path}")

    # -------------------------
    # 3. 设置 3D 后端
    # -------------------------
    logger("正在设置 3D 可视化后端...")
    mne.viz.set_3d_backend("pyvistaqt")

    # -------------------------
    # 4. 读取 BDF
    # -------------------------
    logger("正在读取 BDF 数据...")
    raw = mne.io.read_raw_bdf(bdf_path, preload=True)

    logger(f"通道总数：{len(raw.ch_names)}")
    logger(f"前几个通道名：{raw.ch_names[:10]}")

    # -------------------------
    # 4.1 裁剪用户选择的时间段
    # -------------------------
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

    # -------------------------
    # 5. 非 EEG 通道处理
    # -------------------------
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

    # -------------------------
    # 6. 设置标准电极模板
    # -------------------------
    logger("正在设置 standard_1020 电极模板...")
    raw.set_montage("standard_1020", on_missing="ignore")

    # -------------------------
    # 7. 预处理
    # -------------------------
    logger("正在进行预处理：平均参考 + 1-40 Hz 滤波...")
    raw.set_eeg_reference(projection=True)
    raw.filter(1.0, 40.0, picks="eeg")

    # -------------------------
    # 8. 加载模板模型
    # -------------------------
    logger("正在加载模板源空间和 BEM...")
    src = mne.read_source_spaces(src_path)
    bem = mne.read_bem_solution(bem_path)

    # -------------------------
    # 9. 构建正向解
    # -------------------------
    logger("正在构建 forward solution...")
    fwd = mne.make_forward_solution(
        raw.info,
        trans=trans,
        src=src,
        bem=bem,
        eeg=True,
        meg=False,
        mindist=5.0,
        n_jobs=1
    )

    # -------------------------
    # 10. 计算协方差
    # -------------------------
    logger("正在计算 EEG 协方差...")
    cov = mne.compute_raw_covariance(raw, picks="eeg", method="auto")

    # -------------------------
    # 11. 构建逆算子
    # -------------------------
    logger("正在构建 inverse operator...")
    inverse_operator = mne.minimum_norm.make_inverse_operator(
        raw.info,
        fwd,
        cov,
        loose=0.2,
        depth=0.8
    )

    # -------------------------
    # 12. 逆向求解（取 0~5 秒）
    # -------------------------
    logger("正在进行逆向求解（当前所选时间段）...")
    start = 0
    stop = raw.n_times

    stc = mne.minimum_norm.apply_inverse_raw(
        raw,
        inverse_operator,
        lambda2=1.0 / 9.0,
        method="dSPM",
        start=start,
        stop=stop,
        pick_ori=None
    )

    # 取当前时间段中间时刻作为初始显示时间
    if len(stc.times) == 0:
        raise ValueError("stc.times 为空，无法设置 initial_time。")

    initial_time = float(stc.times[len(stc.times) // 2])

    # -------------------------
    # 13. 弹出 3D 可视化窗口
    # -------------------------
    logger("正在弹出 3D 源定位窗口...")
    stc.plot(
        subject=subject,
        subjects_dir=str(subjects_dir),
        initial_time=initial_time,
        hemi="both",
        views="lateral",
        size=(1000, 700),
        title="Template Source Localization",
        time_viewer=True
    )

    logger("模板源定位完成。")
    logger("========== 模板源定位结束 ==========")

    return stc