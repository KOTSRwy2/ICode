import os
import nibabel as nib
from nilearn import image, masking
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal
import matplotlib.pyplot as plt
import numpy as np
from nilearn import plotting
import plotly.graph_objects as go
import json
from .PlotlyHTMLInjector import PlotlyHTMLInjector
from pathlib import Path
from ..common.path_utils import get_resource_path, get_runtime_path

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

plt.switch_backend('Agg')


def _get_project_root():
    return get_resource_path()


def _get_fmri_output_dir():
    output_dir = str(get_runtime_path("outputs", "fMRI激活定位"))
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def _get_mni152_template_path():
    return str(get_resource_path("templates", "mni152", "mni_icbm152_t1_tal_nlin_sym_09a.nii"))


class FMRIActivationThread(QThread):
    log_pyqtSignal = pyqtSignal(str)
    finish_pyqtSignal = pyqtSignal(bool,dict)

    def __init__(self, fmri_nifti_path, tr=2.0, mask_path=None):
        super().__init__()
        self.fmri_nifti_path = fmri_nifti_path
        self.tr = tr
        self.mask_path = mask_path
        self.output_dir = _get_fmri_output_dir()

        self.html_injector = PlotlyHTMLInjector(self.output_dir)

    def run(self):
        try:
            self.log_pyqtSignal.emit("开始处理fMRI数据...")
            fmri_img, mask_img = self._preprocess_fmri()
            result_paths = self._visualize_fmri_activation(fmri_img, mask_img)
            self._compute_fmri_connectivity(fmri_img, mask_img)
            self.log_pyqtSignal.emit(f"fMRI处理完成！结果已保存至：{self.output_dir}")
            self.finish_pyqtSignal.emit(True,result_paths)
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

        sub_dir_main = os.path.join(self.output_dir, "fMRI脑区激活定位图")
        os.makedirs(sub_dir_main, exist_ok=True)
        html_path = os.path.join(sub_dir_main, f"{base_name}_activation.html")

        threshold = np.percentile(np.abs(fmri_mean.get_fdata()[fmri_mean.get_fdata() != 0]), 90)
        view = plotting.view_img(
            fmri_mean, bg_img=mni_template,
            threshold=threshold,
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
            self.log_pyqtSignal.emit(f"fMRI激活HTML已生成：{html_path}")

        self.log_pyqtSignal.emit("生成激活统计图表...")

        # 1. 读取激活数据
        results_paths = {}
        results_paths['main'] = html_path

        data = fmri_mean.get_fdata()
        data = data[data > 0]
        threshold_90 = np.percentile(data, 90)

        # 2. 阈值-体素数曲线
        self.log_pyqtSignal.emit("生成阈值 - 体素数曲线...")
        thresholds = np.linspace(np.percentile(data, 50), np.percentile(data, 90), 20)
        counts = [np.sum(data > t) for t in thresholds]

        # 创建帧动画
        frames = []
        for i in range(1, len(thresholds) + 1):
            frames.append(go.Frame(
                data=[go.Scatter(
                    x=thresholds[:i],
                    y=counts[:i],
                    mode='lines+markers',
                    name='体素数',
                    line=dict(color='#1677ff', width=3),
                    marker=dict(size=8, symbol='circle')
                )],
                name=str(i)
            ))

        fig1 = go.Figure(
            data=[go.Scatter(
                x=thresholds[:1],
                y=counts[:1],
                mode='lines+markers',
                name='体素数',
                line=dict(color='#1677ff', width=3),
                marker=dict(size=8, symbol='circle')
            )],
            frames=frames,
        )

        fig1.update_layout(
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
            paper_bgcolor='#FFFFFF',
            plot_bgcolor='#FFFFFF',
            margin=dict(l=40, r=40, t=20, b=0),
            xaxis=dict(title='激活阈值', gridcolor='rgba(128,128,128,0.2)'),
            yaxis=dict(title='激活体素数', gridcolor='rgba(128,128,128,0.2)'),
            font=dict(family="Segoe UI, Microsoft YaHei", color="#808080")
        )
        sub_dir_curve = os.path.join(self.output_dir, "阈值-激活体素数曲线")
        os.makedirs(sub_dir_curve, exist_ok=True)
        path1 = os.path.join(sub_dir_curve, f"{base_name}_curve.html")
        fig1.write_html(path1, include_plotlyjs=True, full_html=True)

        self.html_injector.inject_all(path1, options={
            'fluent_css': True,
            'animation_control': True,
            'debug_info': False,
            'frame_display': False
        })

        results_paths['curve'] = path1

        #3. 激活强度直方图
        self.log_pyqtSignal.emit("生成激活强度分布直方图...")
        fig2 = go.Figure()
        fig2.add_trace(go.Histogram(
            x=data.flatten(), nbinsx=50,
            marker_color='rgba(0, 255, 255, 0.6)',
            marker_line_color='black', marker_line_width=1, name="体素数量"
        ))
        # 添加 90% 阈值辅助线
        fig2.add_vline(x=threshold_90, line_width=2, line_dash="dash", line_color="red",
                       annotation_text="90% 阈值", annotation_position="top right")
        fig2.update_layout(
            paper_bgcolor='#FFFFFF',
            plot_bgcolor='#FFFFFF',
            margin=dict(l=40, r=40, t=20, b=40),
            xaxis=dict(title='激活强度', gridcolor='rgba(128,128,128,0.2)'),
            yaxis=dict(title='体素数量', gridcolor='rgba(128,128,128,0.2)'),
            font=dict(family="Segoe UI, Microsoft YaHei", color="#808080")
        )
        sub_dir_hist = os.path.join(self.output_dir, "激活强度分布直方图")
        os.makedirs(sub_dir_hist, exist_ok=True)
        path2 = os.path.join(sub_dir_hist, f"{base_name}_hist.html")
        fig2.write_html(path2, include_plotlyjs=True, full_html=True)

        self.html_injector.inject_all(path2, options={
            'fluent_css': True,
            'animation_control': False,
            'debug_info': False,
            'frame_display': False
        })

        results_paths['histogram'] = path2

        # 6. 脑区激活总结JSON
        self.log_pyqtSignal.emit("生成脑区激活总结...")
        peak_coords = plotting.find_xyz_cut_coords(fmri_mean)
        # 统一转换为列表
        if isinstance(peak_coords, np.ndarray):
            peak_coords = peak_coords.tolist()

        summary = {
            "peak_coords": peak_coords,
            "peak_intensity": float(np.max(data)),
            "threshold": float(threshold),
            "activated_voxels": int(np.sum(data > threshold))
        }
        # 核心修改：添加base_name前缀，和其他文件命名统一
        sub_dir_json = os.path.join(self.output_dir, "fMRI脑区激活总结")
        os.makedirs(sub_dir_json, exist_ok=True)
        summary_json_path = os.path.join(sub_dir_json, f"{base_name}_activation_summary.json")
        with open(summary_json_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=4, ensure_ascii=False)

        results_paths['summary_json'] = summary_json_path
        self.log_pyqtSignal.emit("所有交互式图表已生成！")
        return results_paths

    # 补充缺失的_compute_fmri_connectivity方法（避免运行报错）
    def _compute_fmri_connectivity(self, fmri_img, mask_img):
        self.log_pyqtSignal.emit("跳过功能连接计算（暂未实现完整逻辑）...")
        pass