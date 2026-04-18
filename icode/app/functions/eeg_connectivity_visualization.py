# -*- coding: utf-8 -*-
"""
eeg_connectivity_visualization.py
功能2：基于模板的 EEG 功能连接可视化
"""

from __future__ import annotations

import os
from pathlib import Path

import mne
import numpy as np
from mne.datasets import fetch_fsaverage
from ..common.path_utils import get_resource_path, get_runtime_path

import plotly.graph_objects as go
from .PlotlyHTMLInjector import PlotlyHTMLInjector

def _is_vtkjs_404_page(html_path: Path) -> bool:
    """检测导出的 HTML 是否实际上是 VTK.js 的 404 模板页"""
    try:
        head = html_path.read_text(encoding="utf-8", errors="ignore")[:8000]
    except Exception:
        return False

    markers = (
        "<title>404 | VTK.js",
        'href="/vtk-js/assets/',
        'src="/vtk-js/assets/',
    )
    return any(marker in head for marker in markers)


def _default_logger(msg: str) -> None:
    print(msg)


def _get_project_root() -> Path:
    """返回当前项目根目录"""
    return get_resource_path()


def _get_assets_dir() -> Path:
    """返回 assets 文件夹路径，不存在则自动创建"""
    assets_dir = get_runtime_path("assets")
    assets_dir.mkdir(exist_ok=True)
    return assets_dir


def _get_outputs_dir() -> Path:
    """返回输出目录 outputs/EEG功能连接，不存在则自动创建"""
    outputs_dir = get_runtime_path("outputs", "EEG功能连接")
    outputs_dir.mkdir(exist_ok=True)
    return outputs_dir


def _prepare_fsaverage(logger) -> tuple[Path, Path, Path]:
    """准备 ./assets 下的 fsaverage 模板"""
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

        logger("未检测到完整的本地 fsaverage 模板，正在下载到 assets 文件夹...")
        logger(f"下载目录：{assets_dir}")
        fs_dir = Path(fetch_fsaverage(subjects_dir=assets_dir, verbose=True))
        logger(f"fsaverage 模板已准备完成：{fs_dir}")

    src_path = fs_dir / "bem" / "fsaverage-ico-5-src.fif"
    bem_path = fs_dir / "bem" / "fsaverage-5120-5120-5120-bem-sol.fif"

    if not src_path.exists():
        raise FileNotFoundError(f"缺少源空间文件：{src_path}")
    if not bem_path.exists():
        raise FileNotFoundError(f"缺少 BEM 解文件：{bem_path}")

    return fs_dir, src_path, bem_path


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
        raise ValueError(f"不支持的 analysis_band: {analysis_band}")

    return band_map[analysis_band]


def _plot_fc_matrix(con_matrix, label_names, output_dir, bdf_stem, html_injector):
    """绘制功能连接矩阵热图"""
    custom_colorscale = [
            [0.0, '#0000FF'],
            [0.25, '#0080FF'],
            [0.5, '#FFFFFF'],
            [0.75, '#FF8000'],
            [1.0, '#FF0000']
        ]

    fig = go.Figure(
        data=go.Heatmap(
            z=con_matrix,
            colorscale=custom_colorscale,
            zmin=0,
            zmax=np.percentile(con_matrix, 98),
            colorbar=dict(
                title='相关系数',
                tickfont=dict(family="Segoe UI, Arial", size=9, color="#000000"),
                tickformat='.2f',
                len=0.8,
                thickness=20,
                x=1.02,
                xpad=10
            ),
            hovertemplate='脑区 Y: %{y}<br>脑区 X: %{x}<br>相关性: %{z:.3f}<extra></extra>',
            showscale=True
        )
    )

    # 更新布局
    fig.update_layout(
        title=dict(
            text=f'功能连接矩阵 ({bdf_stem})',
            font=dict(family="Segoe UI, Arial", size=14, color="#000000"),
            x=0.5
        ),
        paper_bgcolor='#FFFFFF',
        plot_bgcolor='#FFFFFF',
        margin=dict(l=100, r=100, t=60, b=60),
        font=dict(family="Segoe UI, Arial", color="#000000", size=10),
        autosize=True,
        showlegend=False,
    )

    # 更新坐标轴配置
    fig.update_xaxes(
        title='脑区索引',
        tickfont=dict(family="Segoe UI, Arial", size=8, color="#000000"),
        gridcolor='rgba(128,128,128,0.2)',
        showticklabels=True,
        scaleanchor="y",
        scaleratio=1,
        range=[-0.5, len(label_names) - 0.5],
        ticks='outside',
        showgrid=True,
        constrain="domain"
    )

    fig.update_yaxes(
        title='Brain Region Index',
        tickfont=dict(family="Segoe UI, Arial", size=8, color="#000000"),
        gridcolor='rgba(128,128,128,0.2)',
        showticklabels=True,
        ticks='outside',
        range=[-0.5, len(label_names) - 0.5],
        showgrid=True,
        autorange='reversed'
    )

    # 保存文件
    fc_matrix_path = os.path.join(output_dir, f"{bdf_stem}_fc_matrix.html")
    fig.write_html(
        fc_matrix_path,
        include_plotlyjs=True,
        full_html=True,
        config={
            'responsive': True,
            'displayModeBar': True,
            'scrollZoom': True,
            'displaylogo': False,
            'autosizable': True,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d']
        }
    )

    html_injector.inject_all(fc_matrix_path, options={
        'fluent_css': True,
        'animation_control': False,
        'debug_info': False,
        'frame_display': False
    })

    print(f"功能连接矩阵热图已保存：{fc_matrix_path}")
    return fc_matrix_path


def _plot_fc_node_degree(con_matrix, label_names, output_dir, bdf_stem, html_injector):
    """绘制节点度（中心枢纽）排名图"""
    # 计算每个节点的加权度（所有连接强度之和）
    node_degrees = np.sum(np.abs(con_matrix), axis=0)

    # 取前 15 个最重要的核心节点
    num_top = min(15, len(label_names))
    idx = np.argsort(node_degrees)[-num_top:]

    top_names = [label_names[i] for i in idx]
    top_values = node_degrees[idx]

    fig = go.Figure(
        data=go.Bar(
            x=top_values,
            y=top_names,
            orientation='h',
            marker=dict(
                color='#13c2c2',
                line=dict(color='#000000', width=0.5)
            ),
            hovertemplate='脑区: %{y}<br>加权度: %{x:.3f}<extra></extra>'
        )
    )

    fig.update_layout(
        title=dict(
            text=f'网络核心枢纽Top{num_top}',
            font=dict(family="Segoe UI, Arial", size=14, color="#000000"),
            x=0.5
        ),
        paper_bgcolor='#FFFFFF',
        plot_bgcolor='#FFFFFF',
        margin=dict(l=150, r=60, t=60, b=40),  # 左侧留空间给脑区名称
        font=dict(family="Segoe UI, Arial", color="#000000", size=10),
        autosize=True,
        showlegend=False
    )

    fig.update_xaxes(
        title='加权节点度',
        tickfont=dict(family="Segoe UI, Arial", size=9, color="#000000"),
        gridcolor='rgba(128,128,128,0.2)',
        showticklabels=True,
        ticks='outside',
        showgrid=True
    )

    fig.update_yaxes(
        title='脑区名称',
        tickfont=dict(family="Segoe UI, Arial", size=8, color="#000000"),
        gridcolor='rgba(128,128,128,0.2)',
        showticklabels=True,
        ticks='outside',
        showgrid=True
    )

    fc_hubs_path = os.path.join(output_dir, f"{bdf_stem}_fc_hubs.html")
    fig.write_html(
        fc_hubs_path,
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

    html_injector.inject_all(fc_hubs_path, options={
        'fluent_css': True,
        'animation_control': False,
        'debug_info': False,
        'frame_display': False
    })

    print(f"节点度排名图已保存：{fc_hubs_path}")
    return fc_hubs_path

def _plot_fc_distribution(con_matrix, output_dir, bdf_stem,html_injector):
    """绘制连接强度分布直方图"""
    # 提取矩阵上三角部分（排除对角线自身相关）
    upper_idx = np.triu_indices(len(con_matrix), k=1)
    weights = con_matrix[upper_idx]

    fig = go.Figure(
        data=go.Histogram(
            x=weights,
            nbinsx=50,
            marker=dict(
                color='#69c0ff',
                line=dict(color='#FFFFFF', width=0.5)
            ),
            opacity=0.7,
            hovertemplate='相关性: %{x:.3f}<br>密度: %{y}<extra></extra>'
        )
    )

    fig.update_layout(
        title=dict(
            text=f'连接强度分布 ({bdf_stem})',
            font=dict(family="Segoe UI, Arial", size=14, color="#000000"),
            x=0.5
        ),
        paper_bgcolor='#FFFFFF',
        plot_bgcolor='#FFFFFF',
        margin=dict(l=60, r=40, t=60, b=60),
        font=dict(family="Segoe UI, Arial", color="#000000", size=10),
        autosize=True,
        showlegend=False
    )

    fig.update_xaxes(
        title='相关系数',
        tickfont=dict(family="Segoe UI, Arial", size=9, color="#000000"),
        gridcolor='rgba(128,128,128,0.2)',
        showticklabels=True,
        ticks='outside',
        showgrid=True
    )

    fig.update_yaxes(
        title='分布密度',
        tickfont=dict(family="Segoe UI, Arial", size=9, color="#000000"),
        gridcolor='rgba(128,128,128,0.2)',
        showticklabels=True,
        ticks='outside',
        showgrid=True
    )

    fc_distribution_path = os.path.join(output_dir, f"{bdf_stem}_fc_distribution.html")
    fig.write_html(
        fc_distribution_path,
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

    html_injector.inject_all(fc_distribution_path, options={
        'fluent_css': True,
        'animation_control': False,
        'debug_info': False,
        'frame_display': False
    })

    print(f"连接强度分布图已保存：{fc_distribution_path}")
    return fc_distribution_path


def _plot_fc_distance_relation(con_matrix, labels, subject, subjects_dir, output_dir, bdf_stem,html_injector):
    """绘制连接距离与强度的相关性散点图"""
    import numpy as np
    from scipy.spatial.distance import pdist

    # 计算每个脑区中心的坐标
    coords = []
    for label in labels:
        v_idx = label.center_of_mass(subject=subject, subjects_dir=subjects_dir)
        # 获取对应半球的坐标数据
        pos = mne.read_surface(Path(subjects_dir) / subject / 'surf' / f"{label.hemi}.white")[0][v_idx]
        coords.append(pos)
    coords = np.array(coords)

    # 计算两两脑区间的欧几里得距离
    dist_vector = pdist(coords)

    # 提取对应的连接强度
    upper_idx = np.triu_indices(len(con_matrix), k=1)
    weight_vector = con_matrix[upper_idx]

    # 绘图
    fig = go.Figure(
        data=go.Scatter(
            x=dist_vector,
            y=weight_vector,
            mode='markers',
            marker=dict(
                size=6,
                color='#ff7875',
                opacity=0.3,
                line=dict(color='#000000', width=0.5)
            ),
            hovertemplate='物理距离: %{x:.2f} mm<br>相关性: %{y:.3f}<extra></extra>',
            name='数据点'
        )
    )

    # 添加趋势线
    if len(dist_vector) > 1:
        z = np.polyfit(dist_vector, weight_vector, 1)
        p = np.poly1d(z)
        trend_x = np.linspace(dist_vector.min(), dist_vector.max(), 100)
        trend_y = p(trend_x)

        fig.add_trace(
            go.Scatter(
                x=trend_x,
                y=trend_y,
                mode='lines',
                line=dict(color='#FF0000', width=2, dash='dash'),
                name='趋势线',
                hovertemplate='物理距离: %{x:.2f} mm<br>趋势线: %{y:.3f}<extra></extra>'
            )
        )

    fig.update_layout(
        title=dict(
            text='距离-强度相关性散点图',
            font=dict(family="Segoe UI, Arial", size=14, color="#000000"),
            x=0.5
        ),
        paper_bgcolor='#FFFFFF',
        plot_bgcolor='#FFFFFF',
        margin=dict(l=60, r=40, t=60, b=60),
        font=dict(family="Segoe UI, Arial", color="#000000", size=10),
        autosize=True,
        showlegend=True,
        legend=dict(
            x=0.98,
            y=0.98,
            xanchor='right',
            yanchor='top',
            bgcolor='rgba(255,255,255,0.8)',
            font=dict(size=9, color="#000000")
        )
    )

    fig.update_xaxes(
        title='物理距离 (mm)',
        tickfont=dict(family="Segoe UI, Arial", size=9, color="#000000"),
        gridcolor='rgba(128,128,128,0.2)',
        showticklabels=True,
        ticks='outside',
        showgrid=True
    )

    fig.update_yaxes(
        title='连接强度 (相关系数)',
        tickfont=dict(family="Segoe UI, Arial", size=9, color="#000000"),
        gridcolor='rgba(128,128,128,0.2)',
        showticklabels=True,
        ticks='outside',
        showgrid=True
    )

    fc_distance_path = os.path.join(output_dir, f"{bdf_stem}_fc_distance_corr.html")
    fig.write_html(
        fc_distance_path,
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

    html_injector.inject_all(fc_distance_path, options={
        'fluent_css': True,
        'animation_control': False,
        'debug_info': False,
        'frame_display': False
    })

    print(f"距离 - 强度相关性图已保存：{fc_distance_path}")
    return fc_distance_path

def compute_connectivity_data(bdf_path, logger=None, duration_sec=10, analysis_band="full"):
    """后台线程执行：只做 EEG 功能连接计算，不创建 3D 场景"""
    if logger is None:
        logger = _default_logger

    logger("========== 功能连接计算开始 ==========")

    if not os.path.exists(bdf_path):
        raise FileNotFoundError(f"BDF 文件不存在：{bdf_path}")

    logger(f"BDF 文件：{bdf_path}")

    # 1) 准备 fsaverage 模板
    fs_dir, src_path, bem_path = _prepare_fsaverage(logger)
    subject = "fsaverage"
    subjects_dir = fs_dir.parent
    trans = "fsaverage"

    logger(f"subjects_dir：{subjects_dir}")
    logger(f"src 文件：{src_path}")
    logger(f"bem 文件：{bem_path}")

    # 2) 读取 BDF 文件
    logger("正在读取 BDF 数据（延迟加载）...")
    raw = mne.io.read_raw_bdf(bdf_path, preload=False)

    logger(f"通道总数：{len(raw.ch_names)}")
    logger(f"前几个通道名：{raw.ch_names[:10]}")

    # 3) 按用户选择裁剪分析时长
    total_duration = float(raw.times[-1]) if raw.n_times > 1 else 0.0
    if duration_sec is None:
        actual_duration = total_duration
        logger("用户选择：处理全部时长")
    else:
        actual_duration = min(float(duration_sec), total_duration)
        logger(f"用户选择：处理前 {duration_sec} 秒")
        if total_duration < float(duration_sec):
            logger(f"原始数据总时长只有 {total_duration:.2f} 秒，因此将处理全部数据")

    if actual_duration > 0:
        raw.crop(tmin=0.0, tmax=actual_duration)

    logger(f"实际参与处理的数据时长：{raw.times[-1]:.2f} 秒")

    logger("正在将所选时间段加载到内存...")
    raw.load_data()
    logger("数据加载完成")

    # 4) 处理非 EEG 通道类型
    logger("正在识别并设置非 EEG 通道类型...")
    ch_type_map = {}
    for ch in raw.ch_names:
        ch_upper = ch.upper()
        if ch_upper == "ECG":
            ch_type_map[ch] = "ecg"
        elif ch_upper in ("EMG1", "EMG2"):
            ch_type_map[ch] = "emg"
        elif ch_upper == "STATUS":
            ch_type_map[ch] = "stim"

    if ch_type_map:
        raw.set_channel_types(ch_type_map)
        logger(f"已设置通道类型：{ch_type_map}")
    else:
        logger("未发现 ECG / EMG1 / EMG2 / STATUS 通道，跳过设置")

    # 5) 设置电极模板并预处理
    logger("正在设置电极模板...")
    all_chan_names = [ch.upper() for ch in raw.ch_names]

    if "A1" in all_chan_names and "B1" in all_chan_names:
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
        raw.rename_channels(biosemi_mapping)
        raw.set_montage("biosemi64", on_missing="warn")
        logger("已重命名 A/B 通道并应用 biosemi64 模板")
    else:
        raw.set_montage("standard_1020", on_missing="warn")
        logger("已应用 standard_1020 模板")

    l_freq, h_freq, band_label = _get_band_range(analysis_band)

    logger(f"正在进行预处理：{band_label} 滤波（{l_freq}-{h_freq} Hz）+ 平均参考")
    raw.filter(l_freq, h_freq, picks="eeg")
    raw.set_eeg_reference("average", projection=True)
    raw.apply_proj()

    # 6) 构建源模型
    logger("正在加载源空间和 BEM 模型...")
    src = mne.read_source_spaces(src_path)
    bem = mne.read_bem_solution(bem_path)

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

    logger("正在计算协方差矩阵...")
    cov = mne.compute_raw_covariance(raw, picks="eeg", method="empirical")

    logger("正在构建 inverse operator...")
    inv = mne.minimum_norm.make_inverse_operator(
        raw.info,
        fwd,
        cov,
        loose=0.2,
        depth=0.8,
    )

    # 7) 对当前时间段做逆解
    logger("正在进行逆向求解...")
    stc = mne.minimum_norm.apply_inverse_raw(
        raw,
        inv,
        lambda2=1.0 / 9.0,
        method="dSPM",
        start=0,
        stop=raw.n_times,
        pick_ori=None,
    )

    # 8) 提取脑区并计算连接矩阵
    logger("正在加载皮层脑区标签（aparc）...")
    labels = mne.read_labels_from_annot(
        subject=subject,
        parc="aparc",
        subjects_dir=str(subjects_dir),
    )
    logger(f"原始脑区标签数量：{len(labels)}")

    labels = [lab for lab in labels if not lab.name.startswith("unknown")]
    logger(f"过滤 unknown 后的脑区标签数量：{len(labels)}")

    logger("正在提取脑区时间序列...")
    label_ts = mne.extract_label_time_course(
        stc,
        labels,
        src,
        mode="mean_flip",
        allow_empty="ignore",
    )

    logger("正在计算功能连接矩阵（皮尔逊相关）...")
    connectivity_matrix = np.corrcoef(label_ts)
    connectivity_matrix = np.nan_to_num(connectivity_matrix, nan=0.0, posinf=0.0, neginf=0.0)

    outputs_dir = _get_outputs_dir()
    bdf_stem = Path(bdf_path).stem
    output_html = outputs_dir / f"{bdf_stem}_connectivity_map.html"

    logger("后台计算完成，等待主线程生成 3D 场景并导出 HTML...")
    logger("========== 功能连接计算结束 ==========")

    outputs_dir = _get_outputs_dir()
    bdf_stem = Path(bdf_path).stem
    label_names = [lab.name for lab in labels]

    html_injector = PlotlyHTMLInjector(str(outputs_dir))
    fc_matrix_path = ""
    fc_hubs_path = ""
    fc_distribution_path = ""
    fc_distance_path = ""

    try:
        logger("正在生成功能连接多维度统计分析图...")
        # 1. 功能连接强度矩阵
        sub_dir_matrix = outputs_dir / "功能连接强度矩阵"
        sub_dir_matrix.mkdir(parents=True, exist_ok=True)
        fc_matrix_path = _plot_fc_matrix(connectivity_matrix, label_names, sub_dir_matrix, bdf_stem, html_injector)

        # 2. 网络核心枢纽排名图
        sub_dir_hub = outputs_dir / "网络核心枢纽排名图"
        sub_dir_hub.mkdir(parents=True, exist_ok=True)
        fc_hub_path = _plot_fc_node_degree(connectivity_matrix, label_names, sub_dir_hub, bdf_stem, html_injector)

        # 3. 连接强度分布直方图
        sub_dir_dist = outputs_dir / "连接强度分布直方图"
        sub_dir_dist.mkdir(parents=True, exist_ok=True)
        fc_distribution_path = _plot_fc_distribution(connectivity_matrix, sub_dir_dist, bdf_stem, html_injector)

        # 4. 距离-强度相关性散点图
        sub_dir_distance = outputs_dir / "距离-强度相关性散点图"
        sub_dir_distance.mkdir(parents=True, exist_ok=True)
        fc_distance_path = _plot_fc_distance_relation(
            connectivity_matrix, labels, subject, subjects_dir, sub_dir_distance, bdf_stem, html_injector
        )

        logger(f"所有 FC 统计图已分类保存至：{outputs_dir}")
    except Exception as e:
        logger(f"部分统计图生成或目录创建失败: {str(e)}")
        import traceback
        logger(traceback.format_exc())

    # 5. 3D 脑网络图 (main)
    sub_dir_main = outputs_dir / "交互式EEG脑网络三维图"
    sub_dir_main.mkdir(parents=True, exist_ok=True)
    output_html = sub_dir_main / f"{bdf_stem}_connectivity_map.html"

    logger("后台计算完成，等待主线程生成 3D 场景并导出 HTML...")
    logger("========== 功能连接计算结束 ==========")

    return {
        "subject": subject,
        "subjects_dir": str(subjects_dir),
        "labels": labels,
        "label_names": label_names,
        "connectivity_matrix": connectivity_matrix,
        "main_path": str(output_html),
        "band_label": band_label,
        "fc_matrix_path": fc_matrix_path,
        "fc_hub_path": fc_hub_path,
        "fc_distribution_path": fc_distribution_path,
        "fc_distance_path": fc_distance_path,
    }


def render_connectivity_html(result, logger=None):
    """主线程执行：创建 3D 脑场景并导出 HTML"""
    if logger is None:
        logger = _default_logger

    subject = result["subject"]
    subjects_dir = result["subjects_dir"]
    labels = result["labels"]
    connectivity_matrix = result["connectivity_matrix"]
    output_html = Path(result["main_path"])
    
    results_path = {
        'main': str(output_html),
        'fc_matrix_path': result["fc_matrix_path"],
        'fc_hub_path': result["fc_hub_path"],
        'fc_distribution_path': result["fc_distribution_path"],
        'fc_distance_path': result["fc_distance_path"]
    }

    logger("========== 主线程渲染开始 ==========")

    logger("正在设置 3D 后端：pyvistaqt")
    mne.viz.set_3d_backend("pyvistaqt")

    logger("正在创建 3D 脑场景...")
    brain = mne.viz.Brain(
        subject=subject,
        subjects_dir=subjects_dir,
        surf="inflated",
        hemi="both",
        cortex="low_contrast",
        alpha=0.45,
        background="black",
    )

    logger("正在筛选最强连接...")
    n_lines = 100
    upper_idx = np.triu_indices(len(labels), k=1)
    all_weights = connectivity_matrix[upper_idx]

    if len(all_weights) > n_lines:
        threshold = np.sort(all_weights)[-n_lines]
    else:
        threshold = 0.5

    logger(f"连接阈值：{threshold:.4f}")

    logger("正在准备节点坐标和标签名称...")
    degrees = np.sum(connectivity_matrix >= threshold, axis=1) - 1
    max_deg = np.max(degrees) if np.max(degrees) > 0 else 1

    label_vertices = []
    label_coords = []
    label_names = []

    for label in labels:
        v_idx = label.center_of_mass(subject=subject, subjects_dir=subjects_dir)
        label_vertices.append(v_idx)
        pos = brain.geo[label.hemi].coords[v_idx]
        label_coords.append(pos)
        label_names.append(label.name)

    coords_arr = np.array(label_coords)

    logger("正在绘制节点...")
    for i, v_idx in enumerate(label_vertices):
        node_size = 0.6 + (degrees[i] / max_deg) * 0.9
        brain.add_foci(
            v_idx,
            coords_as_verts=True,
            scale_factor=node_size,
            color="orangered",
            hemi=labels[i].hemi,
        )

    logger("正在绘制连接边...")
    count = 0
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            weight = connectivity_matrix[i, j]
            if weight >= threshold:
                p1 = brain.geo[labels[i].hemi].coords[label_vertices[i]]
                p2 = brain.geo[labels[j].hemi].coords[label_vertices[j]]

                mix = (weight - threshold) / (1.0 - threshold + 1e-5)
                line_color = (mix, 0.9, 1.0 - mix)

                brain.plotter.add_lines(
                    np.array([p1, p2]),
                    color=line_color,
                    width=max(weight * 6, 1.0),
                )
                count += 1

    logger(f"已绘制连接边数量：{count}")
    logger("正在导出交互式 HTML 页面...")

    try:
        brain.plotter.export_html(str(output_html))

        if _is_vtkjs_404_page(output_html):
            raise RuntimeError(
                "导出的 HTML 实际上是 VTK.js 的 404 模板页（浏览器中会显示空白）。"
                "请检查 trame / pyvista 版本以及运行环境。"
            )

        logger(f"HTML 已生成：{output_html}")

    finally:
        try:
            brain.close()
        except Exception:
            pass

    logger("功能连接可视化完成。")
    logger("========== 主线程渲染结束 ==========")

    return results_path


def run_connectivity_visualization(bdf_path, logger=None, duration_sec=10, analysis_band="full"):
    """
    兼容旧调用方式：
    先计算，再渲染导出
    """
    result = compute_connectivity_data(
        bdf_path=bdf_path,
        logger=logger,
        duration_sec=duration_sec,
        analysis_band=analysis_band,
    )
    return render_connectivity_html(result, logger=logger)