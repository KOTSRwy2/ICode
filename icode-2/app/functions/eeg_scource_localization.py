# -*- coding: utf-8 -*-
"""
source_localization.py
功能1：模板版 EEG 源定位可视化

"""

import os
from pathlib import Path

import mne
from mne.datasets import fetch_fsaverage
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .PlotlyHTMLInjector import PlotlyHTMLInjector
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from scipy.signal import welch
import matplotlib.ticker as ticker
from ..common.path_utils import get_resource_path, get_runtime_path

from ..resource.dark.mne_style_dark import MNE_STYLE_DARK
from ..resource.light.mne_style_light import MNE_STYLE_LIGHT


def _default_logger(msg: str):
    print(msg)


def _get_project_root():
    """返回当前项目根目录"""
    return get_resource_path()


def _get_assets_dir():
    """返回 assets 文件夹路径，不存在则创建"""
    assets_dir = get_runtime_path("assets")
    assets_dir.mkdir(exist_ok=True)
    return assets_dir


def _get_outputs_dir():
    """返回输出目录 outputs/EEG源定位，不存在则自动创建"""
    outputs_dir = get_runtime_path("outputs", "EEG源定位")
    outputs_dir.mkdir(parents=True, exist_ok=True)
    return outputs_dir


def _prepare_fsaverage(logger):
    """
    准备 fsaverage 模板：
    - 优先使用 assets/fsaverage
    - 若缺失则自动下载到 assets 目录
    """
    bundled_fs_dir = get_resource_path("assets", "fsaverage")
    fs_dir = bundled_fs_dir

    src_path = fs_dir / "bem" / "fsaverage-ico-5-src.fif"
    bem_path = fs_dir / "bem" / "fsaverage-5120-5120-5120-bem-sol.fif"

    if fs_dir.exists() and src_path.exists() and bem_path.exists():
        logger(f"检测到内置 fsaverage 模板：{fs_dir}")
    else:
        assets_dir = _get_assets_dir()
        fs_dir = assets_dir / "fsaverage"
        src_path = fs_dir / "bem" / "fsaverage-ico-5-src.fif"
        bem_path = fs_dir / "bem" / "fsaverage-5120-5120-5120-bem-sol.fif"

        logger("未检测到完整的 fsaverage 模板，正在自动下载到 assets 文件夹...")
        logger(f"下载目录：{assets_dir}")
        fs_dir = fetch_fsaverage(subjects_dir=assets_dir, verbose=True)
        fs_dir = Path(fs_dir)
        logger(f"fsaverage 模板已准备完成：{fs_dir}")

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


def _plot_source_time_course_plotly(stc, output_dir, bdf_stem, band_label, html_injector):
    """绘制源活动时间序列图（Plotly 版本，带动画）"""
    print("正在生成源活动时间序列图（Plotly）...")

    times = stc.times * 1000  # 转换为毫秒
    mean_data = np.mean(np.abs(stc.data), axis=0)

    # ===== 创建帧动画 =====
    frames = []
    for i in range(1, len(times) + 1, 50):
        frames.append(go.Frame(
            data=[
                go.Scatter(
                    x=times[:i],
                    y=mean_data[:i],
                    mode='lines',
                    line=dict(color='#1677ff', width=2),
                    fill='tozeroy',
                    fillcolor='rgba(22, 119, 255, 0.1)'
                )
            ],
            name=str(i)
        ))

    fig = go.Figure(
        data=[
            go.Scatter(
                x=times[:1],
                y=mean_data[:1],
                mode='lines',
                line=dict(color='#1677ff', width=2),
                fill='tozeroy',
                fillcolor='rgba(22, 119, 255, 0.1)',
                name='平均源活动强度'
            )
        ],
        frames=frames
    )

    fig.update_layout(
        updatemenus=[{
            'type': 'buttons',
            'showactive': False,
            'x': 0.5, 'y': 0.5, 'xanchor': 'center',
            'bgcolor': 'rgba(255,255,255,0)',
            'bordercolor': 'rgba(255,255,255,0)',
            'borderwidth': 0,
            'font': {
                'color': 'rgba(255,255,255,0)'
            },
            'buttons': [{
                'label': 'Play',
                'method': 'animate',
                'args': [None, {
                    'frame': {'duration': 150, 'redraw': True},
                    'fromcurrent': True,
                    'transition': {'duration': 150, 'easing': 'linear'},
                    'mode': 'immediate'
                }]
            }, {
                'label': 'Pause',
                'method': 'animate',
                'args': [[None], {
                    'frame': {'duration': 0, 'redraw': False},
                    'mode': 'immediate',
                    'transition': {'duration': 0}
                }]
            }]
        }],
        title=dict(
            text=f'源活动时间序列 ({band_label})',
            font=dict(family="Segoe UI, Arial", size=14, color="#000000"),
            x=0.5
        ),
        paper_bgcolor='#FFFFFF',
        plot_bgcolor='#FFFFFF',
        margin=dict(l=60, r=40, t=60, b=60),
        font=dict(family="Segoe UI, Arial", color="#000000", size=10),
        showlegend=False,
        autosize=True,
        xaxis=dict(
            title='时间 (ms)',
            tickfont=dict(family="Segoe UI, Arial", size=9, color="#000000"),
            gridcolor='rgba(128,128,128,0.2)',
            showticklabels=True,
            ticks='outside',
            showgrid=True
        ),
        yaxis=dict(
            title='平均绝对振幅',
            tickfont=dict(family="Segoe UI, Arial", size=9, color="#000000"),
            gridcolor='rgba(128,128,128,0.2)',
            showticklabels=True,
            ticks='outside',
            showgrid=True
        )
    )

    time_course_path = os.path.join(output_dir, f"{bdf_stem}_source_time_course.html")
    fig.write_html(
        time_course_path,
        include_plotlyjs=True,
        full_html=True,
        config={
            'responsive': True,
            'displayModeBar': True,
            'scrollZoom': True,
            'displaylogo': False,
            'autosizable': True
        }
    )

    html_injector.inject_all(time_course_path, options={
        'fluent_css': True,
        'animation_control': True,
        'debug_info': False,
        'frame_display': False
    })

    print(f"源活动时间序列图已保存：{time_course_path}")
    return time_course_path


def _plot_source_intensity_hist_plotly(stc, output_dir, bdf_stem, html_injector):
    fig2 = Figure(figsize=(8, 4))
    FigureCanvas(fig2)
    ax2 = fig2.add_subplot(111)

    data_flat = stc.data.flatten()

    ax2.hist(data_flat, bins=50, color='#66ccff', alpha=0.8, edgecolor='white')

    p95 = np.percentile(data_flat, 95)

    ax2.axvline(p95, color='#ff4d4f', linestyle='--', linewidth=2, label='95% 阈值')

    x_max = np.percentile(data_flat, 99)
    ax2.set_xlim(0, x_max * 1.5)
    y_max = ax2.get_ylim()[1]

    ax2.text(p95, y_max * 0.95, f'95% 阈值\n({p95:.3f})',
             color='#000000',
             fontsize=9,
             verticalalignment='top',
             horizontalalignment='center', )

    ax2.set_title("激活强度分布统计", fontname='SimHei', fontsize=12)
    ax2.set_xlabel("激活强度", fontname='SimHei', fontsize=10)
    ax2.set_ylabel("体素数量", fontname='SimHei', fontsize=10)

    ax2.xaxis.set_major_locator(ticker.MaxNLocator(5))
    ax2.grid(axis='y', linestyle='--', alpha=0.3)

    ax2.legend(loc='upper right', fontsize=9)

    fig2.tight_layout()
    
    hist_filename = f"{bdf_stem}_source_intensity_hist.png"
    fig2.savefig(output_dir / hist_filename, dpi=300)
    hist_path = os.path.join(output_dir, hist_filename)
    return hist_path


def _plot_region_activation_bar_plotly(stc, subjects_dir, output_dir, bdf_stem, html_injector):
    """绘制脑区激活排名图（Plotly 版本，静态）"""
    print("正在生成脑区激活排名图（Plotly）...")

    try:
        # 寻找峰值时刻
        global_power = np.mean(np.abs(stc.data), axis=0)
        peak_idx = np.argmax(global_power)
        win = 5
        start_idx = max(0, peak_idx - win)
        stop_idx = min(stc.data.shape[1], peak_idx + win)

        labels = mne.read_labels_from_annot('fsaverage', parc='aparc', subjects_dir=subjects_dir)
        label_means = []
        label_names = []

        for l in labels:
            try:
                stc_label = stc.in_label(l)
                if stc_label.data.size > 0:
                    val = np.mean(np.abs(stc_label.data[:, start_idx:stop_idx]))
                    label_means.append(val)
                    label_names.append(l.name)
            except:
                continue

        if not label_means:
            print("无有效脑区数据，跳过排名图生成")
            return None

        max_val = max(label_means) if max(label_means) > 0 else 1
        norm_means = [v / max_val for v in label_means]

        idx = np.argsort(norm_means)[-15:]
        top_names = [label_names[i] for i in idx]
        top_values = [norm_means[i] for i in idx]

        fig = go.Figure(
            data=go.Bar(
                x=top_values,
                y=top_names,
                orientation='h',
                marker=dict(
                    color='#ffa940',
                    line=dict(color='#000000', width=0.5)
                ),
                hovertemplate='脑区: %{y}<br>相对强度: %{x:.3f}<extra></extra>'
            )
        )

        fig.update_layout(
            title=dict(
                text='脑区激活排名Top15',
                font=dict(family="Segoe UI, Arial", size=14, color="#000000"),
                x=0.5
            ),
            paper_bgcolor='#FFFFFF',
            plot_bgcolor='#FFFFFF',
            margin=dict(l=150, r=40, t=60, b=40),
            font=dict(family="Segoe UI, Arial", color="#000000", size=10),
            autosize=True,
            showlegend=False,
            xaxis=dict(
                title='相对强度 (0-1)',

                tickfont=dict(family="Segoe UI, Arial", size=9, color="#000000"),
                gridcolor='rgba(128,128,128,0.2)',
                showticklabels=True,
                ticks='outside',
                showgrid=True,
                range=[0, 1.1]
            ),
            yaxis=dict(
                title='脑区名称',
                tickfont=dict(family="Segoe UI, Arial", size=8, color="#000000"),
                gridcolor='rgba(128,128,128,0.2)',
                showticklabels=True,
                ticks='outside',
                showgrid=True
            )
        )

        region_path = os.path.join(output_dir, f"{bdf_stem}_region_activation_bar.html")
        fig.write_html(
            region_path,
            include_plotlyjs=True,
            full_html=True,
            config={
                'responsive': True,
                'displayModeBar': True,
                'scrollZoom': False,
                'displaylogo': False,
                'autosizable': True
            }
        )

        html_injector.inject_all(region_path, options={
            'fluent_css': True,
            'animation_control': False,
            'debug_info': False,
            'frame_display': False
        })

        print(f"脑区激活排名图已保存：{region_path}")
        return region_path

    except Exception as e:
        print(f"脑区排名图生成失败：{str(e)}")
        return None


def _plot_source_psd_plotly(stc, raw, output_dir, bdf_stem, html_injector):
    """绘制源活动相对功率谱图（Plotly 版本，带动画）"""
    print("正在生成源活动相对功率谱图（Plotly）...")

    fs = raw.info['sfreq']
    mean_data = np.mean(np.abs(stc.data), axis=0)
    freqs, psd = welch(mean_data, fs=fs, nperseg=min(len(mean_data), int(fs * 2)))

    psd_db = 10 * np.log10(psd + 1e-25)
    psd_db -= np.max(psd_db)

    # ===== 创建帧动画 =====
    frames = []
    for i in range(1, len(freqs) + 1, 2):
        frames.append(go.Frame(
            data=[
                go.Scatter(
                    x=freqs[:i],
                    y=psd_db[:i],
                    mode='lines',
                    line=dict(color='#73d13d', width=2),
                    fill='tozeroy',
                    fillcolor='rgba(115, 209, 61, 0.1)'
                )
            ],
            name=str(i)
        ))

    fig = go.Figure(
        data=[
            go.Scatter(
                x=freqs[:1],
                y=psd_db[:1],
                mode='lines',
                line=dict(color='#73d13d', width=2),
                fill='tozeroy',
                fillcolor='rgba(115, 209, 61, 0.1)',
                name='相对功率'
            )
        ],
        frames=frames
    )

    fig.update_layout(
        updatemenus=[{
            'type': 'buttons',
            'showactive': False,
            'x': 0.5, 'y': 0.5, 'xanchor': 'center',
            'bgcolor': 'rgba(255,255,255,0)',
            'bordercolor': 'rgba(255,255,255,0)',
            'borderwidth': 0,
            'font': {
                'color': 'rgba(255,255,255,0)'
            },
            'buttons': [{
                'label': 'Play',
                'method': 'animate',
                'args': [None, {
                    'frame': {'duration': 150, 'redraw': True},
                    'fromcurrent': True,
                    'transition': {'duration': 150, 'easing': 'linear'},
                    'mode': 'immediate'
                }]
            }, {
                'label': 'Pause',
                'method': 'animate',
                'args': [[None], {
                    'frame': {'duration': 0, 'redraw': False},
                    'mode': 'immediate',
                    'transition': {'duration': 0}
                }]
            }]
        }],
        title=dict(
            text='源活动相对功率谱 (归一化 dB)',
            font=dict(family="Segoe UI, Arial", size=14, color="#000000"),
            x=0.5
        ),
        paper_bgcolor='#FFFFFF',
        plot_bgcolor='#FFFFFF',
        margin=dict(l=60, r=40, t=60, b=60),
        font=dict(family="Segoe UI, Arial", color="#000000", size=10),
        autosize=True,
        showlegend=False,
        xaxis=dict(
            title='频率 (Hz)',
            tickfont=dict(family="Segoe UI, Arial", size=9, color="#000000"),
            gridcolor='rgba(128,128,128,0.2)',
            showticklabels=True,
            ticks='outside',
            showgrid=True,
            range=[1, 45]
        ),
        yaxis=dict(
            title='相对功率 (dB)',
            tickfont=dict(family="Segoe UI, Arial", size=9, color="#000000"),
            gridcolor='rgba(128,128,128,0.2)',
            showticklabels=True,
            ticks='outside',
            showgrid=True
        )
    )

    psd_path = os.path.join(output_dir, f"{bdf_stem}_source_psd_analysis.html")
    fig.write_html(
        psd_path,
        include_plotlyjs=True,
        full_html=True,
        config={
            'responsive': True,
            'displayModeBar': True,
            'scrollZoom': True,
            'displaylogo': False,
            'autosizable': True
        }
    )

    html_injector.inject_all(psd_path, options={
        'fluent_css': True,
        'animation_control': True,
        'debug_info': False,
        'frame_display': False
    })

    print(f"源活动相对功率谱图已保存：{psd_path}")
    return psd_path


def compute_source_localization(
        bdf_path,
        logger=None,
        duration_sec=10,
        analysis_band="full",
        plot_theme="auto",
):
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
    logger(raw.ch_names)
    ch_type_map = {}
    channels_to_drop = []

    for ch in raw.ch_names:
        ch_upper = ch.upper()
        if ch_upper == "ECG":
            ch_type_map[ch] = "ecg"
        elif ch_upper in ["EMG1", "EMG2"]:
            ch_type_map[ch] = "emg"
        elif ch_upper == "STATUS":
            # 将 Status 设为 stim 通道。如果确定不再需要，也可以加入 channels_to_drop
            ch_type_map[ch] = "stim"

    if ch_type_map:
        raw.set_channel_types(ch_type_map)
        logger(f"已设置非 EEG 通道类型：{ch_type_map}")
    else:
        logger("未发现 ECG / EMG1 / EMG2，跳过相关设置。")

    if channels_to_drop:
        raw.drop_channels(channels_to_drop)

    # 6. 设置标准电极模板
    logger("正在设置电极模板...")
    all_chan_names = [ch.upper() for ch in raw.ch_names]

    if "A1" in all_chan_names and "B1" in all_chan_names:
        # 核心修复：定义 BioSemi 64 (A/B) 到 10-20 系统的标准映射字典
        biosemi_mapping = {
            'A1': 'Fp1', 'A2': 'AF7', 'A3': 'AF3', 'A4': 'F1', 'A5': 'F3', 'A6': 'F5', 'A7': 'F7', 'A8': 'FT7',
            'A9': 'FC5', 'A10': 'FC3', 'A11': 'FC1', 'A12': 'C1', 'A13': 'C3', 'A14': 'C5', 'A15': 'T7', 'A16': 'TP7',
            'A17': 'CP5', 'A18': 'CP3', 'A19': 'CP1', 'A20': 'P1', 'A21': 'P3', 'A22': 'P5', 'A23': 'P7', 'A24': 'P9',
            'A25': 'PO7', 'A26': 'PO3', 'A27': 'O1', 'A28': 'Iz', 'A29': 'Oz', 'A30': 'POz', 'A31': 'Pz', 'A32': 'CPz',
            'B1': 'Fpz', 'B2': 'Fp2', 'B3': 'AF8', 'B4': 'AF4', 'B5': 'AFz', 'B6': 'Fz', 'B7': 'F2', 'B8': 'F4',
            'B9': 'F6', 'B10': 'F8', 'B11': 'FT8', 'B12': 'FC6', 'B13': 'FC4', 'B14': 'FC2', 'B15': 'FCz', 'B16': 'Cz',
            'B17': 'C2', 'B18': 'C4', 'B19': 'C6', 'B20': 'T8', 'B21': 'TP8', 'B22': 'CP6', 'B23': 'CP4', 'B24': 'CP2',
            'B25': 'P2', 'B26': 'P4', 'B27': 'P6', 'B28': 'P8', 'B29': 'P10', 'B30': 'PO8', 'B31': 'PO4', 'B32': 'O2'
        }

        # 将原始通道名称重命名为标准名称
        raw.rename_channels(biosemi_mapping)

        # 应用 Montage，建议将 ignore 改为 warn，这样如果以后再缺电极位置，终端会给你亮黄字警告而不是静默跳过
        raw.set_montage("biosemi64", on_missing="warn")
        logger("已重命名 A/B 通道并应用 biosemi64 模板。")
    else:
        raw.set_montage("standard_1020", on_missing="warn")
        logger("已应用 standard_1020 模板。")

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

    # === 新增：局部隔离的统计图导出逻辑 ===
    time_course_path = ""
    hist_path = ""
    region_path = ""
    psd_path = ""
    try:
        logger("正在生成 EEG 源定位统计分析图（时间/分布/区域/频谱）...")
        eeg_output_dir = _get_outputs_dir()
        html_injector = PlotlyHTMLInjector(str(eeg_output_dir))
        bdf_stem = Path(bdf_path).stem
        # 数据准备
        times = stc.times * 1000
        mean_data = np.mean(np.abs(stc.data), axis=0)

        # 1. 时间序列图 (全球功率时间曲线图)
        sub_dir_gfp = eeg_output_dir / "全球功率时间曲线图"
        sub_dir_gfp.mkdir(parents=True, exist_ok=True)
        time_course_path = _plot_source_time_course_plotly(
            stc, sub_dir_gfp, bdf_stem, band_label, html_injector
        )

        # 2. 强度直方图 (激活强度分布直方图)
        sub_dir_hist = eeg_output_dir / "激活强度分布直方图"
        sub_dir_hist.mkdir(parents=True, exist_ok=True)
        hist_path = _plot_source_intensity_hist_plotly(
            stc, sub_dir_hist, bdf_stem, html_injector
        )

        # 3. 脑区激活排名 (脑区激活 TOP15 柱状图)
        sub_dir_top15 = eeg_output_dir / "脑区激活 TOP15 柱状图"
        sub_dir_top15.mkdir(parents=True, exist_ok=True)
        region_path = _plot_region_activation_bar_plotly(
            stc, str(subjects_dir), sub_dir_top15, bdf_stem, html_injector
        )

        # 4. 频谱 PSD (源活动功率谱密度图)
        sub_dir_psd = eeg_output_dir / "源活动功率谱密度图"
        sub_dir_psd.mkdir(parents=True, exist_ok=True)
        psd_path = _plot_source_psd_plotly(
            stc, raw, sub_dir_psd, bdf_stem, html_injector
        )

        # 5. 3D 源定位图 (main)
        sub_dir_main = eeg_output_dir / "EEG源定位图"
        sub_dir_main.mkdir(parents=True, exist_ok=True)
        main_path = str(sub_dir_main / f"{bdf_stem}_source_map.html")

        logger(f"所有统计分析图已分类保存至：{eeg_output_dir}")
    except Exception as e:
        logger(f"统计图生成或目录创建失败: {str(e)}")

    logger("源定位计算完成，准备返回主线程显示 3D 窗口。")
    logger("========== 模板源定位计算结束 ==========")

    return {
        "stc": stc,
        "subject": subject,
        "subjects_dir": str(subjects_dir),
        "initial_time": initial_time,
        "band_label": band_label,
        "plot_theme": plot_theme,
        "main": main_path,
        "gfp_path": time_course_path,
        "hist_path": hist_path,
        "top15_path": region_path,
        "psd_path": psd_path
    }


def show_source_localization_window(result, html_output_path: str = None, logger=None):
    """
    只负责在主线程中弹出 3D 窗口，可选保存为 HTML 文件。
    """
    if logger is None:
        logger = _default_logger

    if html_output_path is None:
        html_output_path = result.get("main")

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

    if html_output_path:
        try:
            os.makedirs(os.path.dirname(html_output_path), exist_ok=True)
            logger(f"正在将源定位 3D 窗口导出为 HTML：{html_output_path}")
            brain.plotter.export_html(html_output_path)
            logger(f"源定位 3D HTML 已保存：{html_output_path}")
        except Exception as exc:
            logger(f"保存源定位 HTML 失败：{exc}")

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