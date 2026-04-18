import os
import re
import numpy as np
import nibabel as nib
from nilearn import plotting, image, masking
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal
import matplotlib.pyplot as plt
from .PlotlyHTMLInjector import PlotlyHTMLInjector
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import pandas as pd
from ..common.path_utils import get_resource_path, get_runtime_path

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

plt.switch_backend('Agg')


def _get_project_root():
    return get_resource_path()


def _get_fmri_output_dir():
    output_dir = str(get_runtime_path("outputs", "fMRI功能连接"))
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def _get_aal_template_paths():
    aal_nii = str(get_resource_path("templates", "aal", "aal.nii"))
    aal_txt = str(get_resource_path("templates", "aal", "aal.nii.txt"))
    return aal_nii, aal_txt


class FMRIConnectivityThread(QThread):
    log_pyqtSignal = pyqtSignal(str)
    finish_pyqtSignal = pyqtSignal()

    def __init__(self, fmri_nifti_path, tr=2.0, mask_path=None,
                 window_strategy="time_based",
                 window_param=30,
                 step_strategy="fixed",
                 step_param=10):
        super().__init__()
        self.fmri_nifti_path = fmri_nifti_path
        self.tr = tr
        self.mask_path = mask_path
        self.output_dir = _get_fmri_output_dir()

        self.drop_first_timepoints = 10

        # 自适应窗口/步长参数
        self.window_strategy = window_strategy
        self.window_param = window_param
        self.step_strategy = step_strategy
        self.step_param = step_param

        # 实际生效的窗口/步长
        self.window_size = None
        self.step_size = None

        self.html_injector = PlotlyHTMLInjector(self.output_dir)

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

    # AI辅助生成：豆包4.0, 2026-4-06
    def _preprocess_fmri(self):
        self.log_pyqtSignal.emit("读取fMRI NIfTI文件...")
        fmri_img = nib.load(self.fmri_nifti_path)

        # Reorient 空间对齐
        self.log_pyqtSignal.emit("执行Reorient空间对齐（RAS+方向）...")

        self.log_pyqtSignal.emit(f"剔除前{self.drop_first_timepoints}个时间点...")
        fmri_data = fmri_img.get_fdata()
        original_timepoints = fmri_data.shape[-1]

        # 校验时间点数量
        if original_timepoints <= self.drop_first_timepoints:
            raise ValueError(f"时间点数量不足！原始{original_timepoints}个，需剔除{self.drop_first_timepoints}个")

        # 剔除前N个时间点
        fmri_data = fmri_data[..., self.drop_first_timepoints:]
        remaining_timepoints = fmri_data.shape[-1]
        self.log_pyqtSignal.emit(f"时间点处理完成：原始{original_timepoints}个 → 剩余{remaining_timepoints}个")

        # 重新构建Nibabel对象
        fmri_img = nib.Nifti1Image(fmri_data, fmri_img.affine, fmri_img.header)
        # 更新header中的时间维度信息
        fmri_img.header['dim'][4] = remaining_timepoints
        fmri_img.header['pixdim'][4] = self.tr

        # 掩码处理
        if self.mask_path and os.path.exists(self.mask_path):
            mask_img = nib.load(self.mask_path)

            self.log_pyqtSignal.emit(f"使用自定义脑掩码（已Reorient）：{self.mask_path}")
        else:
            self.log_pyqtSignal.emit("生成MNI152标准脑掩码（适配DPARSF）...")
            mask_img = masking.compute_brain_mask(
                fmri_img,
                mask_type='whole-brain',
                connected=True,
                opening=False
            )

        self.log_pyqtSignal.emit("执行fMRI预处理（掩码+标准化，适配DPARSF）...")
        fmri_masked = masking.apply_mask(fmri_img, mask_img)
        fmri_masked = (fmri_masked - fmri_masked.mean(axis=0)) / (fmri_masked.std(axis=0) + 1e-8)
        fmri_preprocessed = masking.unmask(fmri_masked, mask_img)

        return fmri_preprocessed, mask_img

    def _adapt_sliding_window_params(self, n_timepoints):
        """
        自适应计算滑动窗口参数
        :param n_timepoints: 数据集总时间点数
        """
        self.log_pyqtSignal.emit(f"自适应计算滑动窗口参数（总时间点：{n_timepoints}，TR：{self.tr}s）")

        # 1. 计算窗口大小
        if self.window_strategy == "time_based":
            # 按时间长度（秒）计算窗口（如60秒）
            target_seconds = self.window_param
            self.window_size = max(2, int(np.round(target_seconds / self.tr)))  # 至少2个时间点
            self.log_pyqtSignal.emit(f"时间策略：目标{target_seconds}秒 → 窗口大小{self.window_size}个时间点")

        elif self.window_strategy == "proportion_based":
            # 按数据比例计算窗口（如0.2表示总长度的20%）
            proportion = np.clip(self.window_param, 0.05, 0.5)  # 限制5%-50%
            self.window_size = max(2, int(np.round(n_timepoints * proportion)))
            self.log_pyqtSignal.emit(f"比例策略：总长度{proportion * 100:.1f}% → 窗口大小{self.window_size}个时间点")

        elif self.window_strategy == "fixed":
            # 固定窗口大小（兜底）
            self.window_size = max(2, min(self.window_param, n_timepoints))
            self.log_pyqtSignal.emit(f"固定策略：窗口大小{self.window_size}个时间点（原始{self.window_param}）")

        # 窗口不能超过总时间点
        self.window_size = min(self.window_size, n_timepoints)

        # 2. 计算步长
        if self.step_strategy == "auto":
            # 自动步长：窗口大小的1/3
            self.step_size = max(1, int(np.round(self.window_size / 3)))
            self.log_pyqtSignal.emit(f"自动步长：窗口1/3 → 步长{self.step_size}个时间点")

        elif self.step_strategy == "fixed":
            # 固定步长
            self.step_size = max(1, min(self.step_param, self.window_size))
            self.log_pyqtSignal.emit(f"固定步长：步长{self.step_size}个时间点（原始{self.step_param}）")

        # 3. 边界校验
        if self.window_size > n_timepoints:
            self.window_size = n_timepoints
            self.step_size = 1
            self.log_pyqtSignal.emit(f"警告：总时间点不足，调整为窗口{self.window_size}，步长{self.step_size}")

        self.log_pyqtSignal.emit(
            f"最终滑动窗口参数：窗口={self.window_size}({self.window_size * self.tr:.1f}s)，步长={self.step_size}({self.step_size * self.tr:.1f}s)")

    def _get_sliding_window_indices(self, n_timepoints):
        """
        生成自适应的滑动窗口索引（处理边界）
        :param n_timepoints: 总时间点数
        :return: 窗口索引列表 [(start_idx, end_idx), ...]
        """
        windows = []
        start_idx = 0

        while start_idx + self.window_size <= n_timepoints:
            end_idx = start_idx + self.window_size
            windows.append((start_idx, end_idx))
            start_idx += self.step_size


        if start_idx < n_timepoints and len(windows) > 0:
            last_start = max(0, n_timepoints - self.window_size)
            if last_start != windows[-1][0]:  # 避免重复
                windows.append((last_start, n_timepoints))
                self.log_pyqtSignal.emit(f"补充最后一个窗口：[{last_start}, {n_timepoints})")


        return windows

    def _plot_pos_neg_connectivity_pie(self, conn_matrix, output_dir,base_name='fmri'):
        """绘制正负连接比例饼图"""
        self.log_pyqtSignal.emit("计算正负连接比例并绘制饼图...")

        mask = np.eye(conn_matrix.shape[0], dtype=bool)
        conn_vals = conn_matrix[~mask]

        pos_count = np.sum(conn_vals > 0)
        neg_count = np.sum(conn_vals < 0)
        zero_count = np.sum(conn_vals == 0)
        total = len(conn_vals)

        pos_ratio = pos_count / total * 100
        neg_ratio = neg_count / total * 100
        zero_ratio = zero_count / total * 100

        labels = []
        sizes = []
        colors = []
        explode = []

        if pos_ratio > 0:
            labels.append("正连接")
            sizes.append(pos_count)
            colors.append('#E74C3C')
        if neg_ratio > 0:
            labels.append("负连接")
            sizes.append(neg_count)
            colors.append('#3498DB')
        if zero_ratio > 0:
            labels.append("Zero")
            sizes.append(zero_count)
            colors.append('#BDC3C7')

            # 创建图形
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=sizes,
            marker=dict(
                colors=colors,
                line=dict(color='#FFFFFF', width=2)
            ),
            hole=0,
            textinfo='percent',
            textfont=dict(family="Arial, Helvetica, sans-serif", size=14, color="white"),
            hoverinfo='label+value+percent',
            rotation=90,
            pull=[0.05 if l == "Positive" else 0 for l in labels]
        )])

        fig.update_layout(
            title=dict(
                text=f'<b>正/负连接比例饼图</b><br><span style="font-size:12px; color:#95A5A6;">{base_name.upper()} 分析</span>',
                font=dict(family="Arial, Helvetica, sans-serif", size=18, color="#2C3E50"),
                x=0.5,
                y=0.95
            ),
            paper_bgcolor='white',
            plot_bgcolor='white',
            margin=dict(l=20, r=20, t=80, b=40),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.1,
                xanchor="center",
                x=0.5,
                font=dict(family="Arial", size=12, color="#2C3E50")
            ),
            autosize=True
        )

        sub_dir_pie = os.path.join(output_dir, "正负功能连接比例饼图")
        os.makedirs(sub_dir_pie, exist_ok=True)
        pie_path = os.path.join(sub_dir_pie, f"{base_name}_pos_neg_pie.html")
        fig.write_html(pie_path, include_plotlyjs=True, full_html=True,
                       config={'responsive': True, 'displayModeBar': True,
                               'scrollZoom': False, 'displaylogo': False})

        self.html_injector.inject_all(pie_path, options={
            'fluent_css': True,
            'animation_control': False,
            'debug_info': False,
            'frame_display': False
        })

        pos_neg_stats = {
            "positive_count": int(pos_count),
            "negative_count": int(neg_count),
            "zero_count": int(zero_count),
            "positive_ratio": float(pos_ratio),
            "negative_ratio": float(neg_ratio),
            "zero_ratio": float(zero_ratio)
        }
        self.log_pyqtSignal.emit(f"正负连接比例饼图已保存：{pie_path}")
        self.log_pyqtSignal.emit(f"正连接比例：{pos_ratio:.1f}% | 负连接比例：{neg_ratio:.1f}%")
        return pie_path, pos_neg_stats

    def _plot_sliding_window_connectivity(self, roi_timeseries, output_dir, tr=2.0,base_name="fmri"):
        """
        绘制滑动窗口功能连接可视化（适配不同数据集）
        :param roi_timeseries: 脑区时间序列 (n_regions, n_timepoints)
        :param output_dir: 输出目录
        :param tr: 重复时间（秒）
        :param base_name: 输出文件前缀（数据集名称）
        :return: 滑动窗口可视化路径、统计数据路径
        """
        self.log_pyqtSignal.emit("开始绘制滑动窗口功能连接可视化...")

        n_regions, n_timepoints = roi_timeseries.shape

        self._adapt_sliding_window_params(n_timepoints)

        windows = self._get_sliding_window_indices(n_timepoints)
        n_windows = len(windows)

        if n_windows <= 0:
            self.log_pyqtSignal.emit(f"警告：无法生成有效滑动窗口（总时间点：{n_timepoints}，窗口：{self.window_size}）")
            return None, None, None, None

        self.log_pyqtSignal.emit(
            f"滑动窗口参数：窗口大小={self.window_size}个时间点({self.window_size * tr:.1f}s)，步长={self.step_size}个时间点({self.step_size * tr:.1f}s)，总窗口数={n_windows}")

        window_metrics = []

        window_conn_matrices = []

        for window_idx, (start_idx, end_idx) in enumerate(windows):
            window_ts = roi_timeseries[:, start_idx:end_idx]

            # 检查窗口内脑区波动
            window_std = window_ts.std(axis=1)
            valid_window_mask = window_std > 1e-100

            if np.sum(valid_window_mask) < 2:
                mean_conn_strength = 0.0
                pos_ratio = 0.0
                neg_ratio = 0.0
                conn_std = 0.0
                window_conn = np.zeros((n_regions, n_regions))
            else:
                # 只用有效脑区算相关
                wt_valid = window_ts[valid_window_mask]
                corr = np.corrcoef(wt_valid)

                # 填回原尺寸
                window_conn = np.zeros((n_regions, n_regions))
                valid_idx = np.where(valid_window_mask)[0]
                window_conn[np.ix_(valid_idx, valid_idx)] = corr

                # 计算指标
                mask = np.triu(np.ones_like(window_conn, dtype=bool), k=1)
                vals = window_conn[mask]
                mean_conn_strength = np.mean(np.abs(vals))
                pos_ratio = np.sum(vals > 0) / len(vals) * 100
                neg_ratio = np.sum(vals < 0) / len(vals) * 100
                conn_std = np.std(vals)

            # 保存矩阵
            np.fill_diagonal(window_conn, 1.0)  # 加这行
            window_conn_matrices.append(window_conn)

            # 时间
            start_time = start_idx * tr
            end_time = end_idx * tr

            window_metrics.append({
                "window_idx": window_idx,
                "start_time_s": start_time,
                "end_time_s": end_time,
                "mean_conn_strength": mean_conn_strength,
                "pos_ratio": pos_ratio,
                "neg_ratio": neg_ratio,
                "conn_std": conn_std
            })
        self.log_pyqtSignal.emit("生成滑动窗口指标曲线...")

        window_indices = [m["window_idx"] for m in window_metrics]
        start_times = [m["start_time_s"] for m in window_metrics]
        mean_strengths = [m["mean_conn_strength"] for m in window_metrics]
        pos_ratios = [m["pos_ratio"] for m in window_metrics]
        neg_ratios = [m["neg_ratio"] for m in window_metrics]
        conn_stds = [m["conn_std"] for m in window_metrics]

        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                '平均连接强度图',
                '正负连接比例图',
                '连接异质性图',
                '窗口覆盖示意图'
            ),
            specs=[
                [{"secondary_y": False}, {"secondary_y": True}],
                [{"secondary_y": False}, {"secondary_y": False}]
            ],
            vertical_spacing=0.4,
            horizontal_spacing=0.14
        )
        mean_strengths_clean = np.nan_to_num(mean_strengths, nan=0.0, posinf=0.0, neginf=0.0)

        fig.add_trace(go.Scatter(x=start_times, y=mean_strengths_clean, mode='lines',legend='legend', showlegend=True,
                                 name='平均连接强度', line=dict(color='#1677ff', width=3)), row=1, col=1,)
        # Trace 1
        fig.add_trace(go.Scatter(x=start_times, y=pos_ratios, mode='lines',legend='legend2', showlegend=True,
                                 name='正连接', line=dict(color='#E74C3C', width=2)), row=1, col=2)
        # Trace 2
        fig.add_trace(go.Scatter(x=start_times, y=neg_ratios, mode='lines',legend='legend2', showlegend=True,
                                 name='负连接', line=dict(color='#3498DB', width=2)), row=1, col=2)
        # Trace 3
        conn_stds_clean = np.nan_to_num(conn_stds, nan=0.0, posinf=0.0, neginf=0.0)
        fig.add_trace(go.Scatter(x=start_times, y=conn_stds_clean, mode='lines',legend='legend3', showlegend=True,
                                 name='异质性', line=dict(color='#fe8019', width=2)), row=2, col=1)

        # Trace 4: 时间轴
        fig.add_trace(go.Scatter(x=[0, n_timepoints * tr], y=[0, 0], mode='lines',
                                 line=dict(color='#808080', width=2), showlegend=False, hoverinfo='skip'), row=2, col=2)

        cyan_legend_shown = False
        red_legend_shown = False
        window_trace_start_idx = 5

        for i, (start_idx, end_idx) in enumerate(windows):
            start = start_idx * tr
            end = end_idx * tr
            color = '#4ECDC4' if i % 2 == 0 else '#FF6B6B'

            # 按颜色分类显示图例
            if color == '#4ECDC4' and not cyan_legend_shown:
                show_legend = True
                cyan_legend_shown = True
                legend_name = '窗口类别A'
            elif color == '#FF6B6B' and not red_legend_shown:
                show_legend = True
                red_legend_shown = True
                legend_name = '窗口类别B'
            else:
                show_legend = False
                legend_name = ''

            fig.add_trace(
                go.Scatter(
                    x=[start, end, end, start, start],
                    y=[-0.1, -0.1, 0.1, 0.1, -0.1],
                    fill='toself',
                    fillcolor=color,
                    line=dict(color=color, width=0),
                    opacity=0.5,
                    name=legend_name,
                    showlegend=show_legend,
                    legend='legend4',
                    hoverinfo='x',
                    legendgroup=f'g4_{color}'
                ),
                row=2, col=2
            )
        # 记录最后一个用于更新的 Trace 索引（即进度圆点）
        dot_trace_idx = 5 + len(windows)
        fig.add_trace(
            go.Scatter(x=[start_times[0]], y=[0], mode='markers',
                       marker=dict(size=10, color='white', symbol='diamond'),
                       name='当前位置', showlegend=False),
            row=2, col=2
        )

        # 创建帧动画
        frames = []
        for i in range(1, len(start_times) + 1):
            frames.append(go.Frame(
                data=[
                    go.Scatter(x=start_times[:i], y=mean_strengths_clean[:i],legend='legend'),  # Trace 0
                    go.Scatter(x=start_times[:i], y=pos_ratios[:i],legend='legend2'),  # Trace 1
                    go.Scatter(x=start_times[:i], y=neg_ratios[:i],legend='legend2'),  # Trace 2
                    go.Scatter(x=start_times[:i], y=conn_stds_clean[:i],legend='legend3'),  # Trace 3
                    go.Scatter(x=[start_times[i - 1]], y=[0])
                ],
                traces=[0, 1, 2, 3, dot_trace_idx],
                name=str(i)
            ))
        fig.frames = frames
        # 更新布局
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
            paper_bgcolor='#FFFFFF',
            plot_bgcolor='#FFFFFF',
            margin=dict(l=20, r=20, t=60, b=20),
            font=dict(family="Segoe UI, Microsoft YaHei", color="#808080"),
            showlegend=True,
            legend=dict(
                x=0.95, y=0.90, xanchor='left', yanchor='top',
                bgcolor='rgba(0,0,0,0)', font=dict(size=10, color="#808080"),
                orientation='v', traceorder='normal', itemsizing='constant'
            ),
            autosize=True
        )
        common_style = dict(
            bgcolor='rgba(255,255,255,0.6)',
            font=dict(size=10, color="#333333"),
            bordercolor='rgba(200,200,200,0.5)',
            borderwidth=1,
            orientation='v'
        )

        fig.update_layout(
            # 子图 1 图例
            legend=dict(
                x=0.35, y=1.1, xanchor='left', yanchor='top',
                **common_style
            ),
            # 子图 2 图例
            legend2=dict(
                x=0.94, y=1.15, xanchor='right', yanchor='top',
                **common_style
            ),
            # 子图 3 图例
            legend3=dict(
                x=0.35, y=0.45, xanchor='left', yanchor='top',
                **common_style
            ),
            # 子图 4 图例
            legend4=dict(
                x=0.94, y=0.50, xanchor='right', yanchor='top',
                **common_style
            )
        )

        fig.update_layout(showlegend=True)

        # 更新各子图的坐标轴配置
        fig.update_xaxes(
            title='时间 (秒)',
            showticklabels=True,
            ticks='outside',
            gridcolor='rgba(50,50,50,1)',
            tickfont=dict(family="Segoe UI, Microsoft YaHei", color="#808080"),
            row=1, col=1
        )
        fig.update_yaxes(
            title='平均绝对相关系数',
            showticklabels=True,
            ticks='outside',
            gridcolor='rgba(50,50,50,1)',
            tickfont=dict(family="Segoe UI, Microsoft YaHei", color="#808080"),
            row=1, col=1
        )

        fig.update_xaxes(
            title='时间 (秒)',
            showticklabels=True,
            ticks='outside',
            gridcolor='rgba(50,50,50,1)',
            tickfont=dict(family="Segoe UI, Microsoft YaHei", color="#808080"),
            row=1, col=2
        )
        fig.update_yaxes(
            title='比例 (%)',
            showticklabels=True,
            ticks='outside',
            gridcolor='rgba(50,50,50,1)',
            tickfont=dict(family="Segoe UI, Microsoft YaHei", color="#808080"),
            range=[0, 100],
            row=1, col=2,
            secondary_y=False
        )

        fig.update_xaxes(
            title='时间 (秒)',
            showticklabels=True,
            ticks='outside',
            gridcolor='rgba(50,50,50,1)',
            tickfont=dict(family="Segoe UI, Microsoft YaHei", color="#808080"),
            row=2, col=1
        )
        fig.update_yaxes(
            title='连接值标准差',
            showticklabels=True,
            ticks='outside',
            gridcolor='rgba(50,50,50,1)',
            tickfont=dict(family="Segoe UI, Microsoft YaHei", color="#808080"),
            row=2, col=1
        )

        fig.update_xaxes(
            title='时间 (秒)',
            showticklabels=True,
            ticks='outside',
            gridcolor='rgba(50,50,50,1)',
            tickfont=dict(family="Segoe UI, Microsoft YaHei", color="#808080"),
            row=2, col=2
        )
        fig.update_yaxes(
            showticklabels=True,
            ticks='outside',
            range=[-0.3, 0.3],
            row=2, col=2
        )

        sub_dir_metrics = os.path.join(output_dir, "滑动窗口功能连接动态指标图")
        os.makedirs(sub_dir_metrics, exist_ok=True)
        path_metrics = os.path.join(sub_dir_metrics, f"{base_name}_sliding_window_metrics.html")
        fig.write_html(path_metrics, include_plotlyjs=True, full_html=True,
                               config={'responsive': True, 'displayModeBar': True,
                                       'scrollZoom': True, 'displaylogo': False, 'autosizable': True})

        self.html_injector.inject_all(path_metrics, options={
            'fluent_css': True,
            'animation_control': True,
            'debug_info': False,
            'frame_display': False
        })

        # 3. 绘制典型窗口的连接矩阵热力图
        self.log_pyqtSignal.emit("生成连接矩阵热力图...")

        n_show = min(5, n_windows)
        key_window_indices = np.linspace(0, n_windows - 1, n_show, dtype=int)
        key_window_indices = sorted(list(set(key_window_indices)))  # 去重

        fig_heatmap = make_subplots(
            rows=1,
            cols=len(key_window_indices),
            subplot_titles=[
                f"窗口 {win_idx}\n{window_metrics[win_idx]['start_time_s']:.0f}-{window_metrics[win_idx]['end_time_s']:.0f}s"
                for win_idx in key_window_indices
            ],
            horizontal_spacing=0.03,
            vertical_spacing=0.01
        )

        custom_colorscale = [
            [0.0, '#0000FF'],
            [0.25, '#0080FF'],
            [0.5, '#FFFFFF'],
            [0.75, '#FF8000'],
            [1.0, '#FF0000']
        ]

        # 添加每个子图的热力图
        for idx, win_idx in enumerate(key_window_indices):
            conn = window_conn_matrices[win_idx][:83, :83]

            fig_heatmap.add_trace(
                go.Heatmap(
                    z=conn,
                    colorscale=custom_colorscale,
                    zmin=-1,
                    zmax=1,
                    showscale=(idx == len(key_window_indices) - 1),
                    colorbar=dict(
                        title='皮尔逊相关系数',
                        tickfont=dict(family="Segoe UI, Microsoft YaHei", size=10, color="#000000"),
                        len=0.8,
                        thickness=20
                    ) if idx == len(key_window_indices) - 1 else None,
                    hovertemplate='脑区 Y: %{y}<br>脑区 X: %{x}<br>相关系数: %{z:.3f}<extra></extra>',
                    connectgaps=False
                ),
                row=1,
                col=idx + 1
            )

        fig_heatmap.update_layout(
            title=dict(
                text='滑动窗口连接矩阵热力图',
                font=dict(family="Segoe UI, Microsoft YaHei", size=16, color="rgba(60,60,60,1)"),
                x=0.5
            ),
            paper_bgcolor='#ffffff',
            plot_bgcolor='#ffffff',
            margin=dict(l=60, r=60, t=60, b=60),
            font=dict(family="Segoe UI, Microsoft YaHei", color="rgba(60,60,60,1)"),
            height=500,
            width=500 * len(key_window_indices)
        )

        # 更新各子图的坐标轴配置
        for idx in range(1, len(key_window_indices) + 1):
            fig_heatmap.update_xaxes(
                title='脑区索引',
                gridcolor='rgba(60,60,60,1)',
                tickfont=dict(family="Segoe UI, Microsoft YaHei", size=8, color="#000000"),
                scaleanchor="y" if idx == 1 else None,
                scaleratio=1,
                row=1,
                col=idx,
                showticklabels=True,
                ticks='outside',
            )
            fig_heatmap.update_yaxes(
                title='脑区索引',
                gridcolor='rgba(60,60,60,1)',
                tickfont=dict(family="Segoe UI, Microsoft YaHei", size=8, color="#000000"),
                row=1,
                col=idx,
                showticklabels=True,
                ticks='outside',
            )

        sub_dir_heatmap = os.path.join(output_dir, "多时间窗口功能连接热力图")
        os.makedirs(sub_dir_heatmap, exist_ok=True)
        path_heatmap = os.path.join(sub_dir_heatmap, f"{base_name}_connectivity_heatmap.html")
        fig_heatmap.write_html(path_heatmap, include_plotlyjs=True, full_html=True,
                               config={'responsive': True, 'displayModeBar': True,
                                       'scrollZoom': True, 'displaylogo': False, 'autosizable': True})

        self.html_injector.inject_all(path_heatmap, options={
            'fluent_css': True,
            'animation_control': False,
            'debug_info': False,
            'frame_display': False
        })

        # 4. 保存窗口指标到CSV
        sub_dir_csv = os.path.join(output_dir, "滑动窗口动态指标csv文件的文件夹")
        os.makedirs(sub_dir_csv, exist_ok=True)
        metrics_df = pd.DataFrame(window_metrics)
        metrics_csv_path = os.path.join(sub_dir_csv, f"{base_name}_sliding_window_metrics.csv")
        metrics_df.to_csv(metrics_csv_path, index=False, encoding='utf-8-sig')

        # 5. 保存所有窗口的连接矩阵
        sub_dir_npy = os.path.join(output_dir, "全窗口连接矩阵npy文件")
        os.makedirs(sub_dir_npy, exist_ok=True)
        npy_path = os.path.join(sub_dir_npy, f"{base_name}_sliding_window_conn_matrices.npy")
        np.save(npy_path, np.array(window_conn_matrices))

        self.log_pyqtSignal.emit(f"滑动窗口指标图已保存：{path_metrics}")
        self.log_pyqtSignal.emit(f"典型窗口连接矩阵图已保存：{path_heatmap}")
        self.log_pyqtSignal.emit(f"滑动窗口指标数据已保存：{metrics_csv_path}")

        return path_metrics, path_heatmap, metrics_csv_path, npy_path



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

        # AI辅助生成：豆包4.0, 2026-3-30
        roi_timeseries = roi_timeseries[valid_region_mask]
        unique_labels = unique_labels[valid_region_mask]
        n_valid_regions = len(unique_labels)
        self.log_pyqtSignal.emit(f"有效脑区数量（用于计算）：{n_valid_regions}")

        self.log_pyqtSignal.emit("生成脑区坐标...")

        aal_coords_full = []  # 计算用
        aal_coords_3d = []  # 3D图用
        valid_indices_3d = []

        X_RANGE = (-80, 80)
        Y_RANGE = (-120, 80)
        Z_RANGE = (-40, 80)

        for i, label in enumerate(unique_labels):
            region_voxels = np.where(roi_data == label)
            if len(region_voxels[0]) > 0:
                center_voxel = np.array(
                    [np.mean(region_voxels[0]), np.mean(region_voxels[1]), np.mean(region_voxels[2])])
                center_world = nib.affines.apply_affine(roi_img.affine, center_voxel)
                aal_coords_full.append(center_world)

                x, y, z = center_world
                if (X_RANGE[0] <= x <= X_RANGE[1]):
                    if not ((y < -30 and z < -20) or (-100 < y < -30 and -20 < x < 20 and z < 20)):
                        aal_coords_3d.append(center_world)
                        valid_indices_3d.append(i)

        aal_coords_full = np.array(aal_coords_full)
        aal_coords_3d = np.array(aal_coords_3d) if len(aal_coords_3d) > 0 else aal_coords_full

        self.log_pyqtSignal.emit(f"3D脑图将使用过滤后的 {len(aal_coords_3d)} 个脑区")

        roi_std = np.std(roi_timeseries, axis=1)
        valid_roi_mask = roi_std > 1e-10
        self.log_pyqtSignal.emit(f"有效脑区：{np.sum(valid_roi_mask)}/{len(roi_timeseries)}")

        if np.sum(valid_roi_mask) < 2:
            raise ValueError("有效脑区不足2个，无法计算相关矩阵")

        # 只对有效脑区计算相关
        valid_ts = roi_timeseries[valid_roi_mask]
        valid_corr = np.corrcoef(valid_ts)
        np.fill_diagonal(valid_corr, 1.0)

        # 回填到完整矩阵，无效位置填0
        conn_matrix = np.zeros((len(roi_timeseries), len(roi_timeseries)))
        conn_matrix[np.ix_(valid_roi_mask, valid_roi_mask)] = valid_corr

        # 最后把所有 NaN 换成 0
        conn_matrix = np.nan_to_num(conn_matrix, nan=0.0)
        np.fill_diagonal(conn_matrix, 1.0)
        self.log_pyqtSignal.emit(f"生成功能连接矩阵")

        # 提取输入文件的base_name，所有输出文件统一使用该前缀
        base_name = os.path.splitext(os.path.basename(self.fmri_nifti_path))[0]
        if base_name.endswith('.nii'):
            base_name = base_name[:-4]

        results_paths = {}

        custom_colorscale = [
            [0.0, '#0000FF'],
            [0.25, '#0080FF'],
            [0.5, '#FFFFFF'],
            [0.75, '#FF8000'],
            [1.0, '#FF0000']
        ]

        fig = go.Figure(
            data=go.Heatmap(
                z=conn_matrix[:84,:84],
                colorscale=custom_colorscale,
                zmin=-1,
                zmax=1,
                colorbar=dict(
                    title='皮尔逊相关系数',
                    tickfont=dict(family="Segoe UI, Microsoft YaHei", size=10, color="#000000"),
                    tickvals=np.linspace(-1, 1, 9).tolist(),  # 刻度值：-1, -0.75, ..., 1
                    tickformat='.2f',
                    len=0.8,
                    thickness=20,
                    x=1.02,
                    xpad=10
                ),
                hovertemplate='脑区 Y: %{y}<br>脑区 X: %{x}<br>相关系数：%{z:.3f}<extra></extra>'
            )
        )

        # 更新布局
        fig.update_layout(
            title=dict(
                text='fMRI 功能连接矩阵',
                font=dict(family="Segoe UI, Microsoft YaHei", size=14, color="#000000"),
                x=0.5
            ),
            paper_bgcolor='#FFFFFF',
            plot_bgcolor='#FFFFFF',
            margin=dict(l=100, r=100, t=80, b=60),
            font=dict(family="Segoe UI, Microsoft YaHei", color="#000000", size=12),
            autosize=True,
            showlegend=False,
        )

        # 更新坐标轴配置
        fig.update_xaxes(
            title='脑区索引',
            tickfont=dict(family="Segoe UI, Microsoft YaHei", size=10, color="#000000"),
            gridcolor='rgba(128,128,128,0.5)',
            showticklabels=True,
            scaleanchor="y",
            scaleratio=1,
            ticks='outside',
            dtick=10,
            constrain="domain"
        )

        fig.update_yaxes(
            title='脑区索引',
            tickfont=dict(family="Segoe UI, Microsoft YaHei", size=10, color="#000000"),
            gridcolor='rgba(128,128,128,0.2)',
            showticklabels=True,
            ticks='outside',
            constrain="domain",
            autorange = 'reversed',
            dtick = 10
        )

        # 保存全脑功能连接矩阵
        sub_dir_full_heatmap = os.path.join(self.output_dir, "全脑功能连接矩阵")
        os.makedirs(sub_dir_full_heatmap, exist_ok=True)
        path_full_heatmap = os.path.join(sub_dir_full_heatmap, f"{base_name}_connectivity_heatmap_full.html")
        fig.write_html(
            path_full_heatmap,
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

        self.html_injector.inject_all(path_full_heatmap, options={
            'fluent_css': True,
            'animation_control': False,
            'debug_info': False,
            'frame_display': False
        })

        self.log_pyqtSignal.emit(f"完整连接矩阵热力图已保存：{path_full_heatmap}")

        pie_path, pos_neg_stats = self._plot_pos_neg_connectivity_pie(conn_matrix, self.output_dir, base_name=base_name)
        results_paths['pie_path'] = pie_path
        results_paths['path_full_heatmap'] = path_full_heatmap

        path_metrics, path_heatmap, path_csv, path_npy = self._plot_sliding_window_connectivity(roi_timeseries, self.output_dir, self.tr, base_name=base_name)
        results_paths['path_metrics'] = path_metrics
        results_paths['path_heatmap'] = path_heatmap
        results_paths['path_csv'] = path_csv
        results_paths['path_npy'] = path_npy

        # AI辅助生成：豆包4.0, 2026-3-15
        self.log_pyqtSignal.emit("生成交互式HTML脑网络...")

        sub_dir_main = os.path.join(self.output_dir, "3D交互式功能连接脑网络图")
        os.makedirs(sub_dir_main, exist_ok=True)
        html_path = os.path.join(sub_dir_main, f"{base_name}_connectivity.html")

        edge_threshold = "90%"

        conn_matrix_for_3d = conn_matrix[valid_indices_3d, :][:, valid_indices_3d]
        coords_for_3d = np.array(aal_coords_3d)

        view = plotting.view_connectome(
            conn_matrix_for_3d,
            coords_for_3d,
            edge_threshold=edge_threshold,
            title="", node_color="yellow", node_size=8, edge_cmap="bwr", colorbar=False
        )

        view.save_as_html(html_path)

        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        title_tag = f"<title>fMRI Connectivity - AAL ({len(unique_labels)} ROIs)</title>"
        html_content = re.sub(r'<title>.*?</title>', title_tag, html_content)
        html_content = html_content.replace('background-color:white', 'background-color:black')
        html_content = html_content.replace('background:white', 'background:black')

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
            self.log_pyqtSignal.emit(f"fMRI功能连接HTML已生成并打开：{html_path}")

        results_paths['main'] = html_path

        return results_paths

