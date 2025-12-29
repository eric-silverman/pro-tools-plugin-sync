# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
hiddenimports += collect_submodules('pt_plugin_sync')


a = Analysis(
    ['src/pt_plugin_sync/menubar_app.py'],
    pathex=['src'],
    binaries=[],
    datas=[('src/pt_plugin_sync', 'pt_plugin_sync')],
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
    name='Pro Tools Plugin Sync',
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
    icon=['src/pt_plugin_sync/resources/app_icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Pro Tools Plugin Sync',
)
app = BUNDLE(
    coll,
    name='Pro Tools Plugin Sync.app',
    icon='src/pt_plugin_sync/resources/app_icon.icns',
    bundle_identifier=None,
)
