# coding:utf-8
import shutil
from qfluentwidgets import (qconfig, QConfig, OptionsConfigItem, ColorConfigItem, OptionsValidator,
                            EnumSerializer,Theme )
from .path_utils import get_resource_path, get_runtime_path


class Config(QConfig):
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
