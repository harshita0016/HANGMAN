# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['HANG-THE-MAN.py'],
    pathex=[],
    binaries=[],
    datas=[('hangman html', 'hangman html'), ('static', 'static'), ('templates', 'templates'), ('hanged.png', '.'), ('stage0.png', '.'), ('stage1.png', '.'), ('stage2.png', '.'), ('stage4.png', '.'), ('stage5.png', '.'), ('stage7.png', '.')],
    hiddenimports=[],
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
    name='HANG-THE-MAN',
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
)
