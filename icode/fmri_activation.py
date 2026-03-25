import os
import nibabel as nib
from nilearn import plotting, image, masking
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal
import matplotlib.pyplot as plt
import numpy as np
from nilearn import plotting
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

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
        self.plotly_figures = {}  # 用于存储生成的plotly图表

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

        ########### ===================== 新增功能：生成 Plotly 图表 =====================
        self.log_pyqtSignal.emit("生成激活统计的 Plotly 图表...")
        self.plotly_figures = create_plotly_activation_figures(fmri_mean, mni_template)
        self.log_pyqtSignal.emit("所有 Plotly 图表已在内存中生成！")

        self.log_pyqtSignal.emit("所有激活图表与统计文件已保存至输出文件夹！")

        return html_path


def create_plotly_activation_figures(fmri_mean, mni_template):
    """
    使用 Plotly 创建 fMRI 激活分析的三个核心交互式图表。

    参数:
    - fmri_mean: nilearn 的 Nifti-like 图像对象，代表平均激活图。
    - mni_template: nilearn 的 Nifti-like 图像对象，作为背景的 MNI 模板。

    返回:
    - 一个字典，包含三个 plotly figure 对象:
        {
            "threshold_voxel_curve": fig_curve,
            "activation_intensity_hist": fig_hist,
            "ortho_activation": fig_ortho
        }
    """
    figures = {}
    data = fmri_mean.get_fdata()
    # 仅考虑正激活值进行分析
    positive_data = data[data > 0]

    # 1. 阈值-体素数曲线 (Plotly版本)
    thresholds = np.linspace(np.percentile(positive_data, 50), np.percentile(positive_data, 99), 20)
    counts = [np.sum(positive_data > t) for t in thresholds]

    fig_curve = go.Figure(data=go.Scatter(
        x=thresholds,
        y=counts,
        mode='lines+markers',
        marker=dict(color='#1f77b4', symbol='circle'),
        line=dict(color='#1f77b4', width=2)
    ))
    fig_curve.update_layout(
        title="阈值-激活体素数曲线",
        xaxis_title="激活阈值",
        yaxis_title="激活体素数",
        margin=dict(l=40, r=40, t=40, b=40),
        template="plotly_white" # 使用简洁的白色主题
    )
    figures["threshold_voxel_curve"] = fig_curve

    # 2. 激活强度直方图 (Plotly版本)
    percentile_95 = np.percentile(positive_data, 95)
    fig_hist = go.Figure()
    fig_hist.add_trace(go.Histogram(
        x=positive_data,
        nbinsx=50,
        marker_color='#00bcd4',
        opacity=0.75
    ))
    fig_hist.add_shape(
        type="line",
        x0=percentile_95, y0=0, x1=percentile_95, y1=1,
        yref="paper", # 参考y轴比例
        line=dict(color="red", width=2, dash="dash")
    )
    fig_hist.add_annotation(
        x=percentile_95, y=0.95, yref="paper",
        text="95%阈值",
        showarrow=True,
        arrowhead=1,
        ax=40, ay=-40
    )
    fig_hist.update_layout(
        title="激活强度分布直方图",
        xaxis_title="激活强度",
        yaxis_title="体素数量",
        margin=dict(l=40, r=40, t=40, b=40),
        template="plotly_white"
    )
    figures["activation_intensity_hist"] = fig_hist

    # 3. 三正交切片激活图 (Plotly版本) - 修正版
    # 完全复用 nilearn 的数据处理逻辑，仅用 plotly 展示
    mask = masking.compute_epi_mask(fmri_mean)
    peak_coords = plotting.find_xyz_cut_coords(fmri_mean, mask_img=mask)
    
    # 复用原始逻辑中的阈值和范围计算
    threshold = np.percentile(positive_data, 95)
    data_max = np.max(np.abs(fmri_mean.get_fdata()))

    # 创建 1x3 的 plotly 子图布局
    fig_ortho = make_subplots(
        rows=1, cols=3,
        subplot_titles=("矢状面 (Sagittal)", "冠状面 (Coronal)", "轴状面 (Axial)"),
        horizontal_spacing=0.02,
    )

    # 定义切片平面和对应的 subplot 列
    # 注意: nilearn 的 display_mode 'x' 对应矢状面, 'y' 对应冠状面, 'z' 对应轴状面
    views = [('x', 1), ('y', 2), ('z', 3)]

    for display_mode, col in views:
        # 为 nilearn 创建一个临时的 matplotlib Axes 对象来捕获绘图数据
        fig_temp, ax_temp = plt.subplots()
        
        # 调用 nilearn 的核心绘图函数，但只绘制到一个临时的、不可见的 axes 上
        # 这确保了所有的数据处理（切片、阈值、颜色映射）都由 nilearn 完成
        plotting.plot_stat_map(
            fmri_mean,
            bg_img=mni_template,
            display_mode=display_mode,
            cut_coords=peak_coords,
            axes=ax_temp,
            threshold=threshold,
            vmax=data_max,
            cmap='RdYlBu_r'
        )

        # 从临时的 axes 中提取 nilearn 生成的图像数据
        # ax_temp.images[0] 是背景脑图
        bg_data = ax_temp.images[0].get_array().data
        # ax_temp.images[1] 是激活覆盖图 (这是一个 MaskedArray)
        stat_data_masked = ax_temp.images[1].get_array()
        
        # 将 matplotlib 的图像数据添加到 Plotly 子图中
        # 1. 添加背景图 (灰度)
        fig_ortho.add_trace(go.Heatmap(
            z=np.flipud(bg_data), # 上下翻转以匹配 nilearn 的方向
            colorscale='gray',
            showscale=False,
            hoverinfo='none'
        ), row=1, col=col)
        
        # 2. 添加激活覆盖图
        # 将 MaskedArray 中被掩盖的部分转换为 NaN，以便 plotly 的 heatmap 将其渲染为透明
        stat_data = stat_data_masked.filled(np.nan)

        # 获取 nilearn 计算出的颜色范围
        norm = ax_temp.images[1].get_norm()
        vmin, vmax = norm.vmin, norm.vmax

        fig_ortho.add_trace(go.Heatmap(
            z=np.flipud(stat_data), # 上下翻转以匹配 nilearn 的方向
            colorscale='RdYlBu_r',
            showscale=False,
            hoverinfo='z',
            zmin=vmin,
            zmax=vmax,
            zmid=0 # 对发散型色谱很重要
        ), row=1, col=col)

        plt.close(fig_temp) # 关闭临时图，防止显示和内存泄漏

    fig_ortho.update_layout(
        title_text=f"三正交切片激活图 (最强激活点: {np.round(peak_coords, 1)})",
        height=350,
        margin=dict(l=20, r=20, t=60, b=20),
    )
    # 隐藏所有子图的坐标轴和颜色条
    for i in range(1, 4):
        fig_ortho.update_xaxes(showticklabels=False, showgrid=False, zeroline=False, row=1, col=i)
        fig_ortho.update_yaxes(showticklabels=False, showgrid=False, zeroline=False, row=1, col=i)

    figures["ortho_activation"] = fig_ortho

    return figures
