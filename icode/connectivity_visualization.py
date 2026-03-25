# -*- coding: utf-8 -*-
"""
connectivity_visualization.py
功能2：基于模板的 EEG 功能连接可视化
"""

from __future__ import annotations

import os
from pathlib import Path
import webbrowser

import mne
import numpy as np
from mne.datasets import fetch_fsaverage


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
    return Path(__file__).resolve().parent


def _get_assets_dir() -> Path:
    """返回 assets 文件夹路径，不存在则自动创建"""
    assets_dir = _get_project_root() / "assets"
    assets_dir.mkdir(exist_ok=True)
    return assets_dir


def _get_outputs_dir() -> Path:
    """返回输出目录 outputs/EEG，不存在则自动创建"""
    outputs_dir = _get_project_root() / "outputs" / "EEG"
    outputs_dir.mkdir(exist_ok=True)
    return outputs_dir


def _prepare_fsaverage(logger) -> tuple[Path, Path, Path]:
    """准备 ./assets 下的 fsaverage 模板"""
    assets_dir = _get_assets_dir()
    fs_dir = assets_dir / "fsaverage"

    src_path = fs_dir / "bem" / "fsaverage-ico-5-src.fif"
    bem_path = fs_dir / "bem" / "fsaverage-5120-5120-5120-bem-sol.fif"

    if not fs_dir.exists() or not src_path.exists() or not bem_path.exists():
        logger("未检测到完整的本地 fsaverage 模板，正在下载到 assets 文件夹...")
        logger(f"下载目录：{assets_dir}")
        fs_dir = Path(fetch_fsaverage(subjects_dir=assets_dir, verbose=True))
        logger(f"fsaverage 模板已准备完成：{fs_dir}")
    else:
        logger(f"检测到本地 fsaverage 模板：{fs_dir}")

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


def run_connectivity_visualization(bdf_path, logger=None, duration_sec=10, analysis_band="full"):
    """运行基于模板的 EEG 功能连接可视化，并导出交互式 HTML"""
    if logger is None:
        logger = _default_logger

    logger("========== 功能连接可视化开始 ==========")

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

    # 2) 设置 3D 后端
    logger("正在设置 3D 后端：pyvistaqt")
    mne.viz.set_3d_backend("pyvistaqt")

    # 3) 读取 BDF 文件
    logger("正在读取 BDF 数据（延迟加载）...")
    raw = mne.io.read_raw_bdf(bdf_path, preload=False)

    logger(f"通道总数：{len(raw.ch_names)}")
    logger(f"前几个通道名：{raw.ch_names[:10]}")

    # 4) 按用户选择裁剪分析时长
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

    # 5) 处理非 EEG 通道类型
    logger("正在识别并设置非 EEG 通道类型...")
    ch_type_map = {}
    for ch in raw.ch_names:
        ch_upper = ch.upper()
        if ch_upper == "ECG":
            ch_type_map[ch] = "ecg"
        elif ch_upper in ("EMG1", "EMG2"):
            ch_type_map[ch] = "emg"

    if ch_type_map:
        raw.set_channel_types(ch_type_map)
        logger(f"已设置通道类型：{ch_type_map}")
    else:
        logger("未发现 ECG / EMG1 / EMG2 通道，跳过设置")

    # 6) 设置电极模板并预处理
    logger("正在设置 standard_1020 电极模板...")
    raw.set_montage("standard_1020", on_missing="ignore")

    l_freq, h_freq, band_label = _get_band_range(analysis_band)

    logger(f"正在进行预处理：{band_label} 滤波（{l_freq}-{h_freq} Hz）+ 平均参考")
    raw.filter(l_freq, h_freq, picks="eeg")
    raw.set_eeg_reference("average", projection=True)
    raw.apply_proj()

    # 7) 构建源模型
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

    # 8) 对当前时间段做逆解
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

    # 9) 提取脑区并计算连接矩阵
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

    # 10) 创建 3D 脑场景
    logger("正在创建 3D 脑场景...")
    brain = mne.viz.Brain(
        subject=subject,
        subjects_dir=str(subjects_dir),
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
        v_idx = label.center_of_mass(subject=subject, subjects_dir=str(subjects_dir))
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

    logger("正在添加节点标签...")
    brain.plotter.add_point_labels(
        coords_arr,
        label_names,
        font_size=12,
        text_color="white",
        always_visible=True,
        point_size=0,
        shadow=True,
        render_points_as_spheres=False,
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

    # 11) 导出 HTML
    outputs_dir = _get_outputs_dir()
    bdf_stem = Path(bdf_path).stem
    output_html = outputs_dir / f"{bdf_stem}_connectivity_map.html"

    logger("正在导出交互式 HTML 页面...")

    try:
        brain.plotter.export_html(str(output_html))

        if _is_vtkjs_404_page(output_html):
            raise RuntimeError(
                "导出的 HTML 实际上是 VTK.js 的 404 模板页（浏览器中会显示空白）。"
                "请检查 trame / pyvista 版本以及运行环境。"
            )

        logger(f"HTML 已生成：{output_html}")

        # try:
        #     webbrowser.open(output_html.resolve().as_uri())
        #     logger("已尝试用默认浏览器打开 HTML")
        # except Exception as e:
        #     logger(f"自动打开浏览器失败：{e}")

    finally:
        try:
            brain.close()
        except Exception:
            pass

    logger("功能连接可视化完成。")
    logger("========== 功能连接可视化结束 ==========")

    return str(output_html)