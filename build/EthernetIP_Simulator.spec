# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for EthernetIP Virtual PLC Simulator
Optimized for minimal size with aggressive exclusions and UPX compression
"""

block_cipher = None

# Minimal PySide6 modules (exclude unused Qt components)
pyside6_modules = ['PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets']

# Aggressive exclusions - save 30-50 MB
excluded_modules = [
    # Unused stdlib modules
    'tkinter', 'turtle', 'test', 'unittest', 'distutils', 'setuptools',
    'pip', 'wheel', 'ensurepip',
    'email', 'html', 'http.client', 'urllib.request',
    'xml.etree', 'xmlrpc', 'pydoc', 'doctest',
    'multiprocessing', 'concurrent.futures',
    'asyncio', 'asynchat', 'asyncore',
    'curses', 'readline', 'rlcompleter',

    # Unused PySide6 modules (save 50-80 MB)
    'PySide6.QtNetwork',
    'PySide6.QtOpenGL',
    'PySide6.QtOpenGLWidgets',
    'PySide6.QtPrintSupport',
    'PySide6.QtQml',
    'PySide6.QtQuick',
    'PySide6.QtQuickWidgets',
    'PySide6.QtSql',
    'PySide6.QtSvg',
    'PySide6.QtSvgWidgets',
    'PySide6.QtTest',
    'PySide6.QtWebChannel',
    'PySide6.QtWebEngine',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebSockets',
    'PySide6.QtXml',
    'PySide6.Qt3D',
    'PySide6.QtCharts',
    'PySide6.QtDataVisualization',
    'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',

    # Pillow removed (Phase 1 already eliminated this)
    'PIL', 'Pillow',
]

a = Analysis(
    ['build/main_frozen.py'],  # Simplified entry point (run pyinstaller from project root)
    pathex=[],
    binaries=[],
    datas=[('data/tags.db', 'data')],
    hiddenimports=[
        'cpppo.server.enip',
        'cpppo.server.enip.device',
        *pyside6_modules,
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=excluded_modules,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Filter out non-English Qt translations (save 5-10 MB)
a.datas = [x for x in a.datas if not (
    'translations' in x[0].lower() and not x[0].endswith('en.qm')
)]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='EthernetIP_Simulator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,       # Strip debug symbols from binaries
    upx=True,         # UPX compression (30-40% size savings)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,    # No console window (GUI app)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,        # Add .ico file here if you have one
)
