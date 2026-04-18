# -*- mode: python ; coding: utf-8 -*-
#Qwen3.5-Plus使用情况说明：2026年 4月2日 19：00-19：30 参考AI提供的解决方案，最终使用了spec配置文件，根据项目所用资源进行配置
import os
from PyInstaller.utils.hooks import collect_all

icon_path = os.path.abspath(os.path.join('app', 'resource', 'images', 'logo.ico'))


def collect_local_data(src_dir, dest_dir):
    """Collect all files under src_dir into the given destination folder."""
    collected = []
    abs_src = os.path.abspath(src_dir)
    if not os.path.isdir(abs_src):
        return collected

    for root, _, files in os.walk(abs_src):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            rel_root = os.path.relpath(root, abs_src)
            target_dir = os.path.normpath(os.path.join(dest_dir, rel_root))
            collected.append((file_path, target_dir))
    return collected

datas = []
binaries = []
hiddenimports = []
tmp_ret = collect_all('qfluentwidgets')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('nilearn')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('mne')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# Project assets required at runtime.
datas += collect_local_data('app/config', 'app/config')
datas += collect_local_data('app/resource', 'app/resource')
datas += collect_local_data('templates', 'templates')
datas += collect_local_data('assets/fsaverage', 'assets/fsaverage')


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    icon=icon_path,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='main',
)
