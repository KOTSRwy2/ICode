# coding: utf-8
import os
from enum import Enum

from qfluentwidgets import StyleSheetBase, Theme, isDarkTheme, qconfig
from .path_utils import get_resource_path


class StyleSheet(StyleSheetBase, Enum):
    """ Style sheet  """

    MAIN = "main"
    INTERACTIVE_CHART_CARD = "interactive_chart_card"

    def path(self, theme=Theme.AUTO):
        theme = qconfig.theme if theme == Theme.AUTO else theme
        return str(get_resource_path("app", "resource", theme.value.lower(), f"{self.value}.qss"))
