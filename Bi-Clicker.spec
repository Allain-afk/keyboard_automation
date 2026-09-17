# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['auto_clicker.py'],
    pathex=[],
    binaries=[],
    datas=[('ACLib\\playback.ico', 'ACLib'), ('C:\\PythonProjects\\keyboard_automation\\.venv\\Lib\\site-packages\\customtkinter', 'customtkinter/')],
    hiddenimports=['bi_clicker_ui', 'customtkinter', 'pydirectinput'],
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
    a.binaries,
    a.datas,
    [],
    name='Bi-Clicker',
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
    icon=['ACLib\\playback.ico'],
)
