import os
import re
import numpy as np
import nibabel as nib
from nilearn import plotting, image, masking
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal
import matplotlib.pyplot as plt
from nilearn.connectome import ConnectivityMeasure

plt.switch_backend('Agg')


def _get_project_root():
    return os.path.dirname(os.path.abspath(__file__))


def _get_fmri_output_dir():
    output_dir = os.path.join(_get_project_root(), "outputs", "fMRI")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def _get_aal_template_paths():
    aal_nii = os.path.join(_get_project_root(), "templates", "aal", "aal.nii")
    aal_txt = os.path.join(_get_project_root(), "templates", "aal", "aal.nii.txt")
    return aal_nii, aal_txt


class FMRIConnectivityThread(QThread):
    log_pyqtSignal = pyqtSignal(str)
    finish_pyqtSignal = pyqtSignal()

    def __init__(self, fmri_nifti_path, tr=2.0, mask_path=None):
        super().__init__()
        self.fmri_nifti_path = fmri_nifti_path
        self.tr = tr
        self.mask_path = mask_path
        self.output_dir = _get_fmri_output_dir()

    def run(self):
        try:
            self.log_pyqtSignal.emit("开始处理fMRI数据...")
            fmri_img, mask_img = self._preprocess_fmri()
            self._visualize_fmri_activation(fmri_img, mask_img)
            self._compute_fmri_connectivity(fmri_img, mask_img)
            self.log_pyqtSignal.emit(f"fMRI处理完成！结果已保存至：{self.output_dir}")
            self.finish_pyqtSignal.emit()
        except Exception as e:
            self.log_pyqtSignal.emit(f"fMRI处理出错：{str(e)}")
            QMessageBox.critical(None, "错误", f"fMRI处理失败：{str(e)}")

    def _preprocess_fmri(self):
        self.log_pyqtSignal.emit("读取fMRI NIfTI文件...")
        fmri_img = nib.load(self.fmri_nifti_path)

        if self.mask_path and os.path.exists(self.mask_path):
            mask_img = nib.load(self.mask_path)
            self.log_pyqtSignal.emit(f"使用自定义脑掩码：{self.mask_path}")
        else:
            self.log_pyqtSignal.emit("生成MNI152标准脑掩码...")
            mask_img = masking.compute_brain_mask(fmri_img)

        self.log_pyqtSignal.emit("执行fMRI预处理（掩码+标准化）...")
        fmri_masked = masking.apply_mask(fmri_img, mask_img)
        fmri_masked = (fmri_masked - fmri_masked.mean(axis=0)) / (fmri_masked.std(axis=0) + 1e-8)
        fmri_preprocessed = masking.unmask(fmri_masked, mask_img)
        return fmri_preprocessed, mask_img


    def _compute_fmri_connectivity(self, fmri_img, mask_img):
        self.log_pyqtSignal.emit("计算fMRI功能连接矩阵（AAL脑区）...")

        aal_nii_path, aal_txt_path = _get_aal_template_paths()
        if not os.path.exists(aal_nii_path):
            raise FileNotFoundError(f"AAL模板未找到！请检查路径：{aal_nii_path}")

        self.log_pyqtSignal.emit(f"使用AAL模板：{aal_nii_path}")
        aal_roi = nib.load(aal_nii_path)

        aal_labels = []
        if os.path.exists(aal_txt_path):
            with open(aal_txt_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split()
                        if len(parts) >= 2:
                            try:
                                int(parts[0])
                                aal_labels.append(parts[1])
                            except ValueError:
                                aal_labels.append(line)

        self.log_pyqtSignal.emit("AAL模板重采样至fMRI数据空间...")
        roi_img = image.resample_to_img(aal_roi, fmri_img, interpolation="nearest")

        fmri_data = fmri_img.get_fdata()
        roi_data = roi_img.get_fdata()
        n_timepoints = fmri_data.shape[-1]
        self.log_pyqtSignal.emit(f"fMRI数据：{n_timepoints}个时间点")

        self.log_pyqtSignal.emit("开始提取脑区时间序列...")
        unique_labels = np.unique(roi_data[roi_data > 0])
        n_regions = len(unique_labels)
        self.log_pyqtSignal.emit(f"检测到 {n_regions} 个AAL脑区")

        label_to_idx = {label: idx for idx, label in enumerate(unique_labels)}
        fmri_flat = fmri_data.reshape(-1, n_timepoints)
        roi_flat = roi_data.ravel()

        roi_timeseries = np.zeros((n_regions, n_timepoints))
        valid_region_mask = np.zeros(n_regions, dtype=bool)

        for i, label in enumerate(unique_labels):
            idx = label_to_idx[label]
            mask = (roi_flat == label)
            if np.any(mask):
                region_voxels = fmri_flat[mask]
                if region_voxels.shape[0] > 0:
                    roi_timeseries[idx] = region_voxels.mean(axis=0)
                    valid_region_mask[idx] = True

        if not np.any(valid_region_mask):
            raise ValueError("没有有效脑区时间序列！")

        roi_timeseries = roi_timeseries[valid_region_mask]
        unique_labels = unique_labels[valid_region_mask]

        self.log_pyqtSignal.emit("获取脑区坐标并进行过滤...")
        aal_coords = []
        valid_coord_indices = []

        X_RANGE = (-80, 80)
        Y_RANGE = (-120, 80)
        Z_RANGE = (-40, 80)

        for i, label in enumerate(unique_labels):
            region_voxels = np.where(roi_data == label)
            if len(region_voxels[0]) > 0:
                center_voxel = np.array(
                    [np.mean(region_voxels[0]), np.mean(region_voxels[1]), np.mean(region_voxels[2])])
                center_world = nib.affines.apply_affine(roi_img.affine, center_voxel)
                region_name = aal_labels[i] if i < len(aal_labels) else f"ROI_{int(label)}"

                x, y, z = center_world
                if (X_RANGE[0] <= x <= X_RANGE[1]):
                    if not ((y < -30 and z < -20) or (-100 < y < -30 and -20 < x < 20 and z < 20)):
                        aal_coords.append(center_world)
                        valid_coord_indices.append(i)

        if len(aal_coords) == 0:
            self.log_pyqtSignal.emit("警告：所有坐标都被过滤，使用未过滤的坐标")
            aal_coords = []
            valid_coord_indices = []
            for i, label in enumerate(unique_labels):
                region_voxels = np.where(roi_data == label)
                if len(region_voxels[0]) > 0:
                    center_voxel = np.array(
                        [np.mean(region_voxels[0]), np.mean(region_voxels[1]), np.mean(region_voxels[2])])
                    center_world = nib.affines.apply_affine(roi_img.affine, center_voxel)
                    aal_coords.append(center_world)
                    valid_coord_indices.append(i)
            aal_coords = np.array(aal_coords)
        else:
            aal_coords = np.array(aal_coords)

        if len(valid_coord_indices) < len(unique_labels):
            roi_timeseries = roi_timeseries[valid_coord_indices]
            unique_labels = unique_labels[valid_coord_indices]

        self.log_pyqtSignal.emit(f"最终保留 {len(aal_coords)} 个脑区用于可视化")

        self.log_pyqtSignal.emit("计算功能连接矩阵...")
        conn_matrix = np.corrcoef(roi_timeseries)
        self.log_pyqtSignal.emit(f"生成 {conn_matrix.shape[0]}×{conn_matrix.shape[1]} 功能连接矩阵")

        ######### 2. 绘制连接矩阵热力图（放大画布适配完整脑区，纯黑背景对齐EEG）
        plt.figure(figsize=(15, 12))
        plt.style.use('dark_background')
        plt.imshow(conn_matrix, cmap="coolwarm", vmin=-1, vmax=1)
        plt.colorbar(label="Pearson Correlation")
        plt.title("fMRI Functional Connectivity Matrix (Full AAL ROI)", fontsize=14, color="orangered")
        plt.xlabel("ROI Index", fontsize=12, color="white")
        plt.ylabel("ROI Index", fontsize=12, color="white")
        plt.xticks(color="white")
        plt.yticks(color="white")
        heatmap_path = os.path.join(self.output_dir, "fmri_connectivity_heatmap_full.png")
        plt.savefig(heatmap_path, dpi=300, bbox_inches="tight", facecolor="#000000")
        plt.close()
        self.log_pyqtSignal.emit(f"完整连接矩阵热力图已保存：{heatmap_path}")
        ########
        self.log_pyqtSignal.emit("生成交互式HTML脑网络...")
        base_name = os.path.splitext(os.path.basename(self.fmri_nifti_path))[0]
        if base_name.endswith('.nii'):
            base_name = base_name[:-4]

        html_path = os.path.join(self.output_dir, f"{base_name}_connectivity.html")

        #edge_threshold = "95%" if len(unique_labels) > 50 else "90%"
        edge_threshold = "90%"

        view = plotting.view_connectome(
            conn_matrix, aal_coords, edge_threshold=edge_threshold,
            title="", node_color="yellow", node_size=8, edge_cmap="bwr", colorbar=False
        )
        view.save_as_html(html_path)

        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        title_tag = f"<title>fMRI Connectivity - AAL ({len(unique_labels)} ROIs)</title>"
        html_content = re.sub(r'<title>.*?</title>', title_tag, html_content)
        html_content = html_content.replace('background-color:white', 'background-color:black')
        html_content = html_content.replace('background:white', 'background:black')

        css_style = """
        <style>
            html, body { background-color: #000000 !important; color: #ffffff !important; margin: 0 !important; padding: 0 !important; height: 100% !important; width: 100% !important; display: flex !important; flex-direction: column !important; justify-content: center !important; align-items: center !important; }
            h1, h2, h3 { color: #FFFFFF !important; text-shadow: 1px 1px 2px #000000 !important; font-size: 18px !important; text-align: center !important; margin: 10px 0 !important; font-weight: bold !important; }
            .widget-output, .output_subarea, .jupyter-widgets { background-color: #000000 !important; border: none !important; box-shadow: none !important; width: 95% !important; height: 90vh !important; margin: 0 auto !important; display: flex !important; justify-content: center !important; align-items: center !important; }
            .renderer-container, .canvas-container, canvas, #gl-canvas { background-color: #000000 !important; outline: none !important; width: 100% !important; height: 100% !important; }
            ::-webkit-scrollbar { display: none !important; }
            * { border: none !important; box-shadow: none !important; margin: 0 !important; padding: 0 !important; }
            .modebar {
                gap: 12px !important; /* 按钮之间的间距，可按需调整 */
                padding: 8px 12px !important; /* 模式栏内边距 */
            }
            .modebar-btn {
                margin: 0 4px !important; /* 单个按钮的左右边距 */
        </style>
        """

        if '<head>' in html_content:
            html_content = html_content.replace('<head>', f'<head>{css_style}')

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        if os.path.exists(html_path):
            # webbrowser.open(f'file://{os.path.abspath(html_path)}')
            self.log_pyqtSignal.emit(f"fMRI功能连接HTML已生成并打开：{html_path}")

        return html_path
