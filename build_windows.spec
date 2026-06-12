# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for building Windows exe

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# 收集 faster-whisper 和 ctranslate2 的数据文件
whisper_datas = collect_data_files('faster_whisper')
ctranslate_datas = collect_data_files('ctranslate2')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=whisper_datas + ctranslate_datas + [
        ('requirements.txt', '.'),
    ],
    hiddenimports=[
        'faster_whisper',
        'ctranslate2',
        'playwright',
        'playwright.async_api',
        'scenedetect',
        'cv2',
        'numpy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='kuaishou-live',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
