# -*- mode: python ; coding: utf-8 -*-

import os

block_cipher = None

# We run pyinstaller from the packaging dir, so the project root is ..
project_root = os.path.abspath(os.path.join(os.getcwd(), '..'))
entry_point = os.path.join(project_root, 'run.py')

# Collect additional data files
datas = []
datas.append((os.path.join(project_root, 'ayrannotes', 'assets', '*.png'), 'ayrannotes/assets'))
datas.append((os.path.join(project_root, 'ayrannotes', 'localization', '*.json'), 'ayrannotes/localization'))

a = Analysis(
    [entry_point],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=['PyQt6'],
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
    [],
    exclude_binaries=True,
    name='ayrannotes',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_root, 'ayrannotes', 'assets', 'ayrannotes.png')
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ayrannotes'
)
