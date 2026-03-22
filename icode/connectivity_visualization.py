# -*- coding: utf-8 -*-
"""
connectivity_visualization.py
Feature 2: template-based EEG functional connectivity visualization.
"""

from __future__ import annotations

import os
from pathlib import Path
import webbrowser

import mne
import numpy as np
from mne.datasets import fetch_fsaverage


def _is_vtkjs_404_page(html_path: Path) -> bool:
    """Detect whether exported HTML is actually a VTK.js 404 template page."""
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
    return Path(__file__).resolve().parent


def _get_assets_dir() -> Path:
    assets_dir = _get_project_root() / "assets"
    assets_dir.mkdir(exist_ok=True)
    return assets_dir


def _get_outputs_dir() -> Path:
    outputs_dir = _get_project_root() / "outputs"/ "EEG"
    outputs_dir.mkdir(exist_ok=True)
    return outputs_dir


def _prepare_fsaverage(logger) -> tuple[Path, Path, Path]:
    """Prepare fsaverage template under ./assets."""
    assets_dir = _get_assets_dir()
    fs_dir = assets_dir / "fsaverage"

    src_path = fs_dir / "bem" / "fsaverage-ico-5-src.fif"
    bem_path = fs_dir / "bem" / "fsaverage-5120-5120-5120-bem-sol.fif"

    if not fs_dir.exists() or not src_path.exists() or not bem_path.exists():
        logger("Local fsaverage template is incomplete. Downloading to assets ...")
        logger(f"Download directory: {assets_dir}")
        fs_dir = Path(fetch_fsaverage(subjects_dir=assets_dir, verbose=True))
        logger(f"fsaverage ready: {fs_dir}")
    else:
        logger(f"Using local fsaverage: {fs_dir}")

    src_path = fs_dir / "bem" / "fsaverage-ico-5-src.fif"
    bem_path = fs_dir / "bem" / "fsaverage-5120-5120-5120-bem-sol.fif"

    if not src_path.exists():
        raise FileNotFoundError(f"Missing source space file: {src_path}")
    if not bem_path.exists():
        raise FileNotFoundError(f"Missing BEM solution file: {bem_path}")

    return fs_dir, src_path, bem_path


def run_connectivity_visualization(bdf_path, logger=None, duration_sec=10):
    """Run template-based EEG connectivity visualization and export interactive HTML."""
    if logger is None:
        logger = _default_logger

    logger("========== Connectivity Visualization Start ==========")

    if not os.path.exists(bdf_path):
        raise FileNotFoundError(f"BDF file does not exist: {bdf_path}")

    logger(f"BDF file: {bdf_path}")

    # 1) Prepare fsaverage
    fs_dir, src_path, bem_path = _prepare_fsaverage(logger)
    subject = "fsaverage"
    subjects_dir = fs_dir.parent
    trans = "fsaverage"

    logger(f"subjects_dir: {subjects_dir}")
    logger(f"src: {src_path}")
    logger(f"bem: {bem_path}")

    # 2) 3D backend
    logger("Setting 3D backend: pyvistaqt")
    mne.viz.set_3d_backend("pyvistaqt")

    # 3) Read BDF
    logger("Reading BDF (lazy load) ...")
    raw = mne.io.read_raw_bdf(bdf_path, preload=False)

    logger(f"Channel count: {len(raw.ch_names)}")
    logger(f"First channels: {raw.ch_names[:10]}")

    # 4) Crop duration
    total_duration = float(raw.times[-1]) if raw.n_times > 1 else 0.0
    if duration_sec is None:
        actual_duration = total_duration
        logger("Duration selected: full length")
    else:
        actual_duration = min(float(duration_sec), total_duration)
        logger(f"Duration selected: first {duration_sec} s")
        if total_duration < float(duration_sec):
            logger(f"Data only has {total_duration:.2f} s; using full length")

    if actual_duration > 0:
        raw.crop(tmin=0.0, tmax=actual_duration)

    logger(f"Actual duration used: {raw.times[-1]:.2f} s")

    logger("Loading selected segment into memory ...")
    raw.load_data()
    logger("Data segment loaded")

    # 5) Non-EEG channel typing
    logger("Typing non-EEG channels if present ...")
    ch_type_map = {}
    for ch in raw.ch_names:
        ch_upper = ch.upper()
        if ch_upper == "ECG":
            ch_type_map[ch] = "ecg"
        elif ch_upper in ("EMG1", "EMG2"):
            ch_type_map[ch] = "emg"

    if ch_type_map:
        raw.set_channel_types(ch_type_map)
        logger(f"Set channel types: {ch_type_map}")
    else:
        logger("No ECG/EMG1/EMG2 channels found; skip typing")

    # 6) Montage + preprocess
    logger("Applying standard_1020 montage ...")
    raw.set_montage("standard_1020", on_missing="ignore")

    logger("Preprocessing: 1-30 Hz filter + average reference")
    raw.filter(1.0, 30.0, picks="eeg")
    raw.set_eeg_reference("average", projection=True)
    raw.apply_proj()

    # 7) Source model
    logger("Loading source space and BEM ...")
    src = mne.read_source_spaces(src_path)
    bem = mne.read_bem_solution(bem_path)

    logger("Building forward solution ...")
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

    logger("Computing covariance ...")
    cov = mne.compute_raw_covariance(raw, picks="eeg", method="empirical")

    logger("Building inverse operator ...")
    inv = mne.minimum_norm.make_inverse_operator(
        raw.info,
        fwd,
        cov,
        loose=0.2,
        depth=0.8,
    )

    # 8) Inverse solution on selected segment
    logger("Applying inverse solution ...")
    stc = mne.minimum_norm.apply_inverse_raw(
        raw,
        inv,
        lambda2=1.0 / 9.0,
        method="dSPM",
        start=0,
        stop=raw.n_times,
        pick_ori=None,
    )

    # 9) Labels and connectivity
    logger("Loading cortical labels (aparc) ...")
    labels = mne.read_labels_from_annot(
        subject=subject,
        parc="aparc",
        subjects_dir=str(subjects_dir),
    )
    logger(f"Label count (raw): {len(labels)}")

    labels = [lab for lab in labels if not lab.name.startswith("unknown")]
    logger(f"Label count (filtered): {len(labels)}")

    logger("Extracting label time courses ...")
    label_ts = mne.extract_label_time_course(
        stc,
        labels,
        src,
        mode="mean_flip",
        allow_empty="ignore",
    )

    logger("Computing connectivity matrix (Pearson correlation) ...")
    connectivity_matrix = np.corrcoef(label_ts)

    # 10) Build 3D scene
    logger("Creating 3D brain scene ...")
    brain = mne.viz.Brain(
        subject=subject,
        subjects_dir=str(subjects_dir),
        surf="inflated",
        hemi="both",
        cortex="low_contrast",
        alpha=0.45,
        background="black",
    )

    logger("Selecting strongest connections ...")
    n_lines = 100
    upper_idx = np.triu_indices(len(labels), k=1)
    all_weights = connectivity_matrix[upper_idx]

    if len(all_weights) > n_lines:
        threshold = np.sort(all_weights)[-n_lines]
    else:
        threshold = 0.5

    logger(f"Connection threshold: {threshold:.4f}")

    logger("Preparing node coordinates and labels ...")
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

    logger("Drawing nodes ...")
    for i, v_idx in enumerate(label_vertices):
        node_size = 0.6 + (degrees[i] / max_deg) * 0.9
        brain.add_foci(
            v_idx,
            coords_as_verts=True,
            scale_factor=node_size,
            color="orangered",
            hemi=labels[i].hemi,
        )

    logger("Adding node labels ...")
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

    logger("Drawing edges ...")
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

    logger(f"Edges drawn: {count}")

    # 11) Export HTML
    outputs_dir = _get_outputs_dir()
    bdf_stem = Path(bdf_path).stem
    output_html = outputs_dir / f"{bdf_stem}_connectivity_map.html"

    logger("Exporting interactive HTML ...")

    try:
        brain.plotter.export_html(str(output_html))

        if _is_vtkjs_404_page(output_html):
            raise RuntimeError(
                "Exported HTML is a VTK.js 404 template (blank page in browser). "
                "Please verify trame/pyvista versions and runtime environment."
            )

        logger(f"HTML generated: {output_html}")

        try:
            webbrowser.open(output_html.resolve().as_uri())
            logger("Attempted to open HTML in default browser")
        except Exception as e:
            logger(f"Auto-open browser failed: {e}")

    finally:
        try:
            brain.close()
        except Exception:
            pass

    logger("Connectivity visualization completed")
    logger("========== Connectivity Visualization End ==========")

    return str(output_html)
