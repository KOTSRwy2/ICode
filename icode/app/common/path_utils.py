# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path


def _source_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def get_resource_root() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass).resolve()
        return Path(sys.executable).resolve().parent
    return _source_root()


def get_runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return _source_root()


def get_project_root() -> Path:
    return get_resource_root()


def get_resource_path(*parts: str) -> Path:
    return get_resource_root().joinpath(*parts)


def get_runtime_path(*parts: str) -> Path:
    return get_runtime_root().joinpath(*parts)
