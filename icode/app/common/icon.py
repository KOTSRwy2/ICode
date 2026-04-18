# -*- coding: utf-8 -*-
from enum import Enum

from qfluentwidgets import FluentIconBase, Theme, getIconColor
from .path_utils import get_resource_path

class Icon(FluentIconBase, Enum):
    """支持深浅主题切换的自定义导航图标"""

    EEG_SOURCE_LOCALIZATION = "EEG_Source_Localization"
    EEG_CONNECTIVITY = "EEG_Conectivity"
    FMRI_ACTIVATION = "fMRI_Activation"
    FMRI_CONNECTIVITY = "fMRI_Conectivity"

    def path(self, theme=Theme.AUTO):
        if theme == Theme.AUTO:
            # qfluentwidgets 在 AUTO 时基于当前主题返回 black/white 图标色，需转换为主题名
            color = getIconColor(theme).lower()
            theme = Theme.DARK if color == "white" else Theme.LIGHT

        folder = "dark" if theme == Theme.DARK else "light"
        suffix = "Dark" if theme == Theme.DARK else "Light"
        return str(get_resource_path("app", "resource", "icons", folder, f"{self.value}_{suffix}.svg"))