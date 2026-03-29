# coding:utf-8
from qfluentwidgets import (qconfig, QConfig, OptionsConfigItem, ColorConfigItem, OptionsValidator,
                            EnumSerializer,Theme )


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
qconfig.load('app/config/config.json', cfg)
# ensure qconfig refers to the loaded Config's items so setTheme/setThemeColor affect the correct items
qconfig.themeMode = cfg.themeMode
qconfig.themeColor = cfg.themeColor
