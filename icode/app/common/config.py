# coding:utf-8
import shutil
from qfluentwidgets import (qconfig, QConfig, ConfigItem, OptionsConfigItem, ColorConfigItem, OptionsValidator,
                            EnumSerializer, Theme)
from .path_utils import get_resource_path, get_runtime_path

#Qwen3.5-Plus使用情况说明：3月19日 10：15-11：00 用来梳理Pyqt-fluent-widgets 框架的主题管理逻辑，作为参考辅助理解，代码是通过参考官方示例项目进行编写。
class Config(QConfig):
    # OSS 配置
    ossAccessKeyId = ConfigItem("OSS", "AccessKeyId", "")
    ossAccessKeySecret = ConfigItem("OSS", "AccessKeySecret", "")
    ossEndpoint = ConfigItem("OSS", "Endpoint", "oss-cn-guangzhou.aliyuncs.com")
    ossBucket = ConfigItem("OSS", "Bucket", "html10i")

    themeMode = OptionsConfigItem(
        "MainWindow", "ThemeMode", Theme.AUTO,
        OptionsValidator(Theme),
        EnumSerializer(Theme)
    )

    # 主题颜色配置
    themeColor = ColorConfigItem(
        "MainWindow", "ThemeColor", "#009fa5"
    )

cfg = Config()
cfg.themeMode.value = Theme.AUTO
runtime_cfg = get_runtime_path("app", "config", "config.json")
default_cfg = get_resource_path("app", "config", "config.json")

runtime_cfg.parent.mkdir(parents=True, exist_ok=True)
if not runtime_cfg.exists() and default_cfg.exists():
    shutil.copy2(default_cfg, runtime_cfg)

qconfig.load(str(runtime_cfg), cfg)
qconfig.themeMode = cfg.themeMode
qconfig.themeColor = cfg.themeColor
