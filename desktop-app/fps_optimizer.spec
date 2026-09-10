# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

app_dir = os.path.abspath('app')

datas = [
    (os.path.join(app_dir, 'data'), 'data'),
    (os.path.join(app_dir, 'bin'), 'bin'),
]
datas += collect_data_files('customtkinter')

hiddenimports = [
    'customtkinter',
    'pywinstyles',
    'psutil',
    'wmi',
    'win32api',
    'win32con',
    'win32gui',
    'win32process',
    'pynvml',
    'pandas',
    'numpy',
    'sklearn',
    'sklearn.ensemble',
    'sklearn.preprocessing',
    'joblib',
]
hiddenimports += collect_submodules('customtkinter')

a = Analysis(
    [os.path.join(app_dir, 'main.py')],
    pathex=[app_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='FPS_Optimizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
)
