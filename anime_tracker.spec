# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec para AnimeTracker v1.0.0
# Uso: pyinstaller anime_tracker.spec
#
# Requisitos:
#   pip install pyinstaller
#
# Genera una carpeta dist/AnimeTracker v1.0.0/ con el .exe y todos los
# archivos necesarios. Esa carpeta es la que se usa como Source en Inno Setup.
# Usa onedir (COLLECT) — más estable con PyQt6 que onefile.

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Incluir explícitamente la DLL de Python para PCs sin Python instalado
_extra_binaries = []
for _dll_name in ('python3.dll', f'python{sys.version_info.major}{sys.version_info.minor}.dll'):
    _dll_path = os.path.join(sys.base_exec_prefix, _dll_name)
    if os.path.isfile(_dll_path):
        _extra_binaries.append((_dll_path, '.'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=_extra_binaries,
    datas=[
        ('resources', 'resources'),
        ('icon.ico', '.'),
        ('animes_api.db', '.'),
    ],
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtWidgets',
        'PyQt6.QtGui',
        'sqlite3',
        'requests',
        'PIL',
        'PIL.Image',
        'PIL._imaging',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'PyQt5',
        'PySide2',
        'PySide6',
        'matplotlib',
        'scipy',
        'pandas',
        'numpy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AnimeTracker v1.0.1',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    runtime_tmpdir=None,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='AnimeTracker v1.0.1',
)
