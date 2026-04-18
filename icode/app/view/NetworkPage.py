

# -*- coding: utf-8 -*-
from datetime import datetime
import os
import socket
import time
import oss2
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QApplication

from qfluentwidgets import (
    ScrollArea, SubtitleLabel, BodyLabel, PushButton, TextEdit,
    InfoBar, InfoBarPosition, IndeterminateProgressBar, LineEdit,
    CaptionLabel, CardWidget, qconfig, Theme
)
from qfluentwidgets import FluentIcon as FIF

from .core import log_manager, MODULE_NETWORK
from ..common.style_sheet import StyleSheet
from ..common.config import cfg


# 后台检测线程
class NetworkCheckThread(QThread):
    """网络检测后台线程，避免界面卡顿"""
    finished_sig = pyqtSignal(bool, str, dict)
    progress_sig = pyqtSignal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.oss_auth = None
        self.oss_bucket = None

    def _test_dns_resolve(self):
        """测试OSS域名DNS解析"""
        self.progress_sig.emit("正在检测OSS域名DNS解析...", 10)
        try:
            domain = cfg.ossEndpoint.value
            ip = socket.gethostbyname(domain)
            return True, f"DNS解析成功，Endpoint: {domain} → IP: {ip}"
        except Exception as e:
            return False, f"DNS解析失败: {str(e)}"

    def _test_oss_connectivity(self):
        """测试阿里云OSS连通性"""
        self.progress_sig.emit("正在初始化OSS客户端...", 30)
        try:
            auth = oss2.Auth(cfg.ossAccessKeyId.value, cfg.ossAccessKeySecret.value)
            bucket = oss2.Bucket(auth, cfg.ossEndpoint.value, cfg.ossBucket.value)
            
            try:
                bucket.get_bucket_info()
            except oss2.exceptions.NoSuchBucket:
                return False, f"OSS Bucket {cfg.ossBucket.value} 不存在"
            except Exception as e:
                return False, f"OSS Bucket访问异常: {str(e)}"
            
            self.oss_auth = auth
            self.oss_bucket = bucket
            return True, f"OSS客户端初始化成功，Bucket: {cfg.ossBucket.value}"
        except Exception as e:
            return False, f"OSS连接失败: {str(e)}"

    def _test_oss_upload_download(self):
        """测试OSS上传/下载链路"""
        self.progress_sig.emit("正在测试OSS上传/下载链路...", 60)
        test_file_name = "network_test.html"
        try:
            test_content = f"Network Test File - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            start_time = time.time()
            result = self.oss_bucket.put_object(test_file_name, test_content)
            upload_time = round((time.time() - start_time) * 1000, 2)

            if result.status != 200:
                return False, f"OSS上传失败，状态码: {result.status}"

            start_time = time.time()
            obj = self.oss_bucket.get_object(test_file_name)
            download_content = obj.read().decode("utf-8")
            download_time = round((time.time() - start_time) * 1000, 2)

            if download_content != test_content:
                self.oss_bucket.delete_object(test_file_name)
                return False, "OSS上传/下载内容不一致，链路异常"

            self.oss_bucket.delete_object(test_file_name)

            return True, (
                f"OSS上传/下载测试成功 | 上传耗时: {upload_time}ms | 下载耗时: {download_time}ms\n"
                f"Bucket: {cfg.ossBucket.value} | Endpoint: {cfg.ossEndpoint.value}"
            )
        except Exception as e:
            if self.oss_bucket:
                try:
                    self.oss_bucket.delete_object(test_file_name)
                except:
                    pass
            return False, f"OSS上传/下载测试异常: {str(e)}"

    def _test_network_latency(self):
        """测试网络延迟"""
        self.progress_sig.emit("正在检测网络延迟...", 85)
        try:
            host = cfg.ossEndpoint.value
            latencies = []
            for _ in range(3):
                start = time.time()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex((host, 443))
                if result == 0:
                    latency = round((time.time() - start) * 1000, 2)
                    latencies.append(latency)
                sock.close()
                time.sleep(0.5)

            if not latencies:
                return False, "网络延迟测试失败，无法连接到OSS节点"
            
            avg_latency = round(sum(latencies) / len(latencies), 2)
            return True, f"网络延迟测试成功 | 平均延迟: {avg_latency}ms | 测试节点: {host}"
        except Exception as e:
            return False, f"网络延迟测试异常: {str(e)}"

    def run(self):
        """执行完整检测流程"""
        report = {
            "project": "脑功能连接网络分析",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "check_items": [],
            "overall_status": "success",
            "oss_config": {
                "bucket": cfg.ossBucket.value,
                "endpoint": cfg.ossEndpoint.value
            }
        }

        dns_ok, dns_msg = self._test_dns_resolve()
        report["check_items"].append({
            "item": "DNS解析检测",
            "status": "success" if dns_ok else "failed",
            "message": dns_msg
        })
        if not dns_ok:
            report["overall_status"] = "failed"

        oss_connect_ok, oss_connect_msg = self._test_oss_connectivity()
        report["check_items"].append({
            "item": "OSS连通性检测",
            "status": "success" if oss_connect_ok else "failed",
            "message": oss_connect_msg
        })
        if not oss_connect_ok:
            report["overall_status"] = "failed"
            final_msg = "OSS连通性检测失败，终止后续测试"
            self.finished_sig.emit(False, final_msg, report)
            return

        upload_ok, upload_msg = self._test_oss_upload_download()
        report["check_items"].append({
            "item": "OSS上传/下载链路测试",
            "status": "success" if upload_ok else "failed",
            "message": upload_msg
        })
        if not upload_ok:
            report["overall_status"] = "failed"

        latency_ok, latency_msg = self._test_network_latency()
        report["check_items"].append({
            "item": "网络延迟检测",
            "status": "success" if latency_ok else "failed",
            "message": latency_msg
        })
        if not latency_ok:
            report["overall_status"] = "failed"

        self.progress_sig.emit("检测完成，正在生成报告...", 100)
        final_msg = f"网络检测完成，整体状态: {'全部通过' if report['overall_status'] == 'success' else '存在异常'}"
        self.finished_sig.emit(True, final_msg, report)


# 网络服务页面
class NetworkPage(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("Network_Integration")
        self.setWidgetResizable(True)
        self.setFrameShape(self.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.view = QWidget(self)
        self.view.setObjectName("view")
        self.viewport().setObjectName("FunctionPageViewport")

        self.main_layout = QVBoxLayout(self.view)
        self.main_layout.setContentsMargins(36, 36, 36, 36)
        self.main_layout.setSpacing(24)

        self._init_ui()
        self.setWidget(self.view)
        StyleSheet.MAIN.apply(self)

        self.check_thread = NetworkCheckThread()
        self.check_thread.progress_sig.connect(self._on_progress_update)
        self.check_thread.finished_sig.connect(self._on_check_finished)

    def _init_ui(self):
        title_label = SubtitleLabel("网络与云服务", self.view)
        description = BodyLabel(
            "在本页面中您可以配置私有的阿里云 OSS 账号，系统将使用您配置的账号进行分析结果的云端同步与分享。",
            self.view
        )
        description.setWordWrap(True)
        self.main_layout.addWidget(title_label)
        self.main_layout.addWidget(description)

        # OSS 配置区域  AI辅助生成：Qwen3.5-Plus, 2026-03-20 ai辅助生成网络服务配置界面，包含输入框和保存按钮
        oss_group_label = SubtitleLabel("OSS 账户配置", self.view)
        oss_group_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 10px;")
        self.main_layout.addWidget(oss_group_label)

        config_card = CardWidget(self.view)
        config_layout = QVBoxLayout(config_card)
        config_layout.setContentsMargins(20, 20, 20, 20)
        config_layout.setSpacing(12)

        def create_input(label_text, placeholder, current_val):
            l = QVBoxLayout()
            cap = CaptionLabel(label_text, config_card)
            edit = LineEdit(config_card)
            edit.setPlaceholderText(placeholder)
            edit.setText(current_val)
            l.addWidget(cap)
            l.addWidget(edit)
            return l, edit

        self.l_ak, self.edit_ak = create_input("AccessKey ID", "输入您的 AccessKey ID", cfg.ossAccessKeyId.value)
        self.l_sk, self.edit_sk = create_input("AccessKey Secret", "输入您的 AccessKey Secret", cfg.ossAccessKeySecret.value)
        self.l_ep, self.edit_ep = create_input("Endpoint", "如: oss-cn-guangzhou.aliyuncs.com", cfg.ossEndpoint.value)
        self.l_bn, self.edit_bn = create_input("Bucket Name", "如: my-brain-data", cfg.ossBucket.value)

        config_layout.addLayout(self.l_ak)
        config_layout.addLayout(self.l_sk)
        config_layout.addLayout(self.l_ep)
        config_layout.addLayout(self.l_bn)

        self.btn_save = PushButton("保存并同步配置", config_card, FIF.SAVE)
        self.btn_save.clicked.connect(self._on_save_config)
        config_layout.addWidget(self.btn_save, alignment=Qt.AlignLeft)

        self.main_layout.addWidget(config_card)

        # 检测区域
        check_title = SubtitleLabel("网络连通性检测", self.view)
        check_title.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 20px;")
        self.main_layout.addWidget(check_title)

        button_layout = QHBoxLayout()
        self.btn_generate_report = PushButton("开始网络连通性检测", self.view, FIF.DOCUMENT)
        self.btn_generate_report.clicked.connect(self._on_start_check)
        
        self.progress_bar = IndeterminateProgressBar(self.view)
        self.progress_bar.setVisible(False)

        button_layout.addWidget(self.btn_generate_report)
        button_layout.addWidget(self.progress_bar)
        button_layout.addStretch(1)
        self.main_layout.addLayout(button_layout)

        self.status_editor = TextEdit(self.view)
        self.status_editor.setReadOnly(True)
        self.status_editor.setPlaceholderText("网络服务状态与检测报告将在此显示...")
        self.main_layout.addWidget(self.status_editor, stretch=1)

    def _on_save_config(self):
        """保存 OSS 配置到本地文件"""
        ak = self.edit_ak.text().strip()
        sk = self.edit_sk.text().strip()
        ep = self.edit_ep.text().strip()
        bn = self.edit_bn.text().strip()

        if not all([ak, sk, ep, bn]):
            InfoBar.warning(
                "配置不完整",
                "请填写所有必填项后再保存",
                parent=self.window(),
                position=InfoBarPosition.TOP_RIGHT
            )
            return

        # 更新全局配置
        qconfig.set(cfg.ossAccessKeyId, ak)
        qconfig.set(cfg.ossAccessKeySecret, sk)
        qconfig.set(cfg.ossEndpoint, ep)
        qconfig.set(cfg.ossBucket, bn)

        InfoBar.success(
            "保存成功",
            "OSS 配置已同步到云端服务，您可以开始进行连通性检测",
            parent=self.window(),
            position=InfoBarPosition.TOP_RIGHT
        )
        self._log_to_manager(f"OSS 配置更新: Bucket={bn}, Endpoint={ep}")

    def _log_to_manager(self, text: str):
        """同步日志到全局日志管理器"""
        log_manager.add_log(text, MODULE_NETWORK)
        self.status_editor.append(text)

    def _on_start_check(self):
        """开始检测"""
        self.status_editor.clear()
        self.btn_generate_report.setEnabled(False)
        self.progress_bar.setVisible(True)
        self._log_to_manager("=== 开始网络连通性检测 ===")
        self.check_thread.start()

    def _on_progress_update(self, msg: str, progress: int):
        """更新检测进度"""
        self._log_to_manager(msg)

    def _on_check_finished(self, ok: bool, msg: str, report: dict):
        """检测完成，生成报告"""
        self.progress_bar.setVisible(False)
        self.btn_generate_report.setEnabled(True)

        if ok and report["overall_status"] == "success":
            InfoBar.success(
                "检测完成", 
                "所有网络检测项全部通过，边缘-云端链路正常", 
                parent=self.window(), 
                position=InfoBarPosition.TOP_RIGHT
            )
        else:
            InfoBar.warning(
                "检测完成", 
                "部分检测项存在异常，请查看详细报告", 
                parent=self.window(), 
                position=InfoBarPosition.TOP_RIGHT
            )

        report_text = self._format_report(report)
        self.status_editor.setPlainText(report_text)
        self._log_to_manager(msg)
        self._log_to_manager("=== 检测结束 ===")

    def _format_report(self, report: dict) -> str:
        """格式化检测报告为易读文本"""
        base_info = (
            f"网络连通性检测报告\n"
            f"项目名称：{report['project']}\n"
            f"检测时间：{report['timestamp']}\n"
            f"云端配置：Bucket[{report['oss_config']['bucket']}] | Endpoint[{report['oss_config']['endpoint']}]\n"
            f"整体状态：{'全部通过' if report['overall_status'] == 'success' else '存在异常'}\n"
            f"\n=== 详细检测项 ===\n"
        )

        items_info = ""
        for item in report["check_items"]:
            status_icon = "成功" if item["status"] == "success" else "失败"
            items_info += f"{status_icon} {item['item']}：{item['message']}\n\n"

        json_report = (
            f"\n=== 结构化JSON报告 ===\n"
            f"{str(report)}\n"
        )

        return base_info + items_info + json_report

    def _on_theme_changed(self, theme: Theme):
        """当主题变化时，重新应用样式表"""
        StyleSheet.MAIN.apply(self)
        self.update()
        self.repaint()
        QApplication.processEvents()