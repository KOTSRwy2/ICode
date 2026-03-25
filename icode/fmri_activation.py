import os
import nibabel as nib
from nilearn import plotting, image, masking
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal
import matplotlib.pyplot as plt
import numpy as np
from nilearn import plotting

plt.rcParams['font.sans-serif'] = ['SimHei']  # 用黑体显示中文
plt.rcParams['axes.unicode_minus'] = False    # 正常显示负号

plt.switch_backend('Agg')


def _get_project_root():
    return os.path.dirname(os.path.abspath(__file__))


def _get_fmri_output_dir():
    output_dir = os.path.join(_get_project_root(), "outputs", "fMRI")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def _get_mni152_template_path():
    return os.path.join(_get_project_root(), "templates", "mni152", "mni_icbm152_t1_tal_nlin_sym_09a.nii")


class FMRIActivationThread(QThread):
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


    def _visualize_fmri_activation(self, fmri_img, mask_img):
        self.log_pyqtSignal.emit("生成fMRI激活可视化HTML...")
        fmri_mean = image.mean_img(fmri_img)
        mni_template_path = _get_mni152_template_path()
        if not os.path.exists(mni_template_path):
            raise FileNotFoundError(f"MNI152模板未找到！请检查路径：{mni_template_path}")
        mni_template = nib.load(mni_template_path)

        base_name = os.path.splitext(os.path.basename(self.fmri_nifti_path))[0]
        if base_name.endswith('.nii'):
            base_name = base_name[:-4]

        html_path = os.path.join(self.output_dir, f"{base_name}_activation.html")

        # ========== 关键：生成自带阈值滑块的 HTML ==========
        view = plotting.view_img(
            fmri_mean, bg_img=mni_template,
            threshold=1.5,
            title="fMRI Activation Map",
            cmap="RdYlBu_r",
            black_bg=True,
        )
        view.save_as_html(html_path)

        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        css_style = """
        <style>
            body, html { background-color: #000000 !important; margin: 0 !important; padding: 20px !important; height: 100% !important; width: 100% !important; box-sizing: border-box !important; }
            h1, h2, h3 { color: #ffffff !important; text-shadow: 2px 2px 4px #000000 !important; font-size: 16px !important; text-align: center !important; white-space: normal !important; width: 100% !important; margin: 10px 0 20px 0 !important; display: block !important; }
            .widget-colorbar { background-color: #000000 !important; margin: 20px auto 0 auto !important; display: block !important; max-width: 80% !important; }
            .renderer-container, .canvas-container, canvas { background-color: #000000 !important; margin: 0 auto !important; display: block !important; max-width: 100% !important; }
            .view-label, .colorbar-label { color: #ffffff !important; font-size: 14px !important; }
            ::-webkit-scrollbar { display: none !important; }
            * { border: none !important; box-shadow: none !important; }
        </style>
        """
        if '<head>' in html_content:
            html_content = html_content.replace('<head>', f'<head>{css_style}')

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        if os.path.exists(html_path):
            # webbrowser.open(f'file://{os.path.abspath(html_path)}')
            self.log_pyqtSignal.emit(f"fMRI激活HTML已生成：{html_path}")

        ########### ===================== 新增功能：自动输出所有图表到 outputs/fMRI =====================
        self.log_pyqtSignal.emit("生成激活统计图表...")

        # 1. 读取激活数据
        data = fmri_mean.get_fdata()
        data = data[data > 0]

        # 2. 阈值-体素数曲线
        plt.figure(figsize=(8, 4))
        thresholds = np.linspace(np.percentile(data, 50), np.percentile(data, 99), 20)
        counts = [np.sum(data > t) for t in thresholds]
        plt.plot(thresholds, counts, 'b-o', linewidth=2)
        plt.xlabel("激活阈值")
        plt.ylabel("激活体素数")
        plt.title("阈值-激活体素数曲线")
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, "threshold_voxel_curve.png"), dpi=300)
        plt.close()

        ######### 3. 激活强度直方图
        plt.figure(figsize=(8, 4))
        plt.hist(data, bins=50, alpha=0.7, color="c", edgecolor="black")
        plt.axvline(np.percentile(data, 95), color="r", linestyle="--", label="95%阈值")
        plt.xlabel("激活强度")
        plt.ylabel("体素数量")
        plt.legend()
        plt.title("激活强度分布直方图")
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, "activation_intensity_hist.png"), dpi=300)
        plt.close()


        ####### 4. 三正交切片图（强制显示最强激活点！）（切的点太怪了感觉不对，如果可以直接在前端交互窗口加个截图功能？）
        threshold = np.percentile(data, 95)
        data_max = np.max(np.abs(fmri_mean.get_fdata()))

        # 第一步：找最强的激活峰值坐标
        from nilearn.masking import compute_epi_mask
        mask = compute_epi_mask(fmri_mean)
        peak_coords = plotting.find_xyz_cut_coords(fmri_mean, mask_img=mask)

        # 第二步：强制切点
        plotting.plot_stat_map(
            fmri_mean,
            bg_img=mni_template,
            threshold=threshold,
            display_mode="ortho",
            title="三正交切片激活图",
            vmax=data_max,
            vmin=-data_max,
            cmap="RdYlBu_r",
            cut_coords=peak_coords,  # 强制切最强点
        )
        plt.savefig(os.path.join(self.output_dir, "ortho_activation.png"), dpi=300, bbox_inches='tight')
        plt.close()

        '''
        # 5. 激活簇表（threshold报错）
        #clusters = reporting.get_clusters_table(fmri_mean, threshold=threshold, cluster_threshold=10)
        #clusters.to_csv(os.path.join(self.output_dir, "activation_clusters.csv"), index=False)
        

        # 6. 脑区激活总结JSON（threshold报错）
        summary = {
            "peak_coords": plotting.find_xyz_cut_coords(fmri_mean).tolist(),
            "peak_intensity": float(np.max(data)),
            "threshold": float(threshold),
            "activated_voxels": int(np.sum(data > threshold))
        }
        with open(os.path.join(self.output_dir, "activation_summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=4, ensure_ascii=False)
        '''

        self.log_pyqtSignal.emit("所有激活图表与统计文件已保存至输出文件夹！")

        return html_path