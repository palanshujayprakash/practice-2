# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Specification File for Retail POS Desktop App.
Bundles Streamlit, SQLite, ReportLab, openpyxl, Plotly, and pywebview into a standalone Windows executable.
"""
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all Streamlit and Plotly package assets
streamlit_datas = collect_data_files('streamlit')
plotly_datas = collect_data_files('plotly')

added_datas = [
    ('pages', 'pages'),
    ('.streamlit', '.streamlit'),
    ('assets', 'assets'),
    ('db', 'db'),
    ('services', 'services'),
    ('utils', 'utils'),
    ('app.py', '.'),
] + streamlit_datas + plotly_datas

hidden_imports = [
    'streamlit',
    'streamlit.web.cli',
    'streamlit.runtime.scriptrunner.magic_funcs',
    'reportlab',
    'reportlab.lib',
    'reportlab.platypus',
    'reportlab.lib.pagesizes',
    'openpyxl',
    'pandas',
    'plotly',
    'plotly.express',
    'plotly.graph_objects',
    'webview',
    'sqlite3',
    'hashlib',
    'secrets',
    'decimal',
] + collect_submodules('streamlit')

a = Analysis(
    ['launcher.py'],
    pathex=['.'],
    binaries=[],
    datas=added_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy', 'tkinter', 'unittest'],
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
    name='RetailPOS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False, # Windowed desktop app (no black command prompt)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico'
)
