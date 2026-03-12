# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# ── Shared hidden imports ──────────────────────────────────────────────
HIDDEN = [
    'MetaTrader5',
    'matplotlib', 'matplotlib.backends.backend_tkagg',
    'mplfinance',
    'customtkinter', 'customtkinter.windows',
    'pandas', 'numpy',
    'config', 'main', 'gpu_runner', 'gpu_engine',
    'fibonacci', 'indicators', 'live_trading',
    'mt5_handler', 'risk_management', 'trend_analysis',
    'f_analysis', 'backtest',
    'queue', 'threading', 'subprocess', 'json', 'logging', 'dotenv',
]

EXCLUDES = ['torch', 'torchvision']

# ── GUI EXE (Aladin.exe) ──────────────────────────────────────────────
gui = Analysis(
    ['gui_app.py'],
    pathex=['.'],
    binaries=[],
    datas=[('config.json', '.')],
    hiddenimports=HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    cipher=block_cipher,
    noarchive=False,
)

gui_pyz = PYZ(gui.pure, gui.zipped_data, cipher=block_cipher)

gui_exe = EXE(
    gui_pyz,
    gui.scripts,
    [],
    exclude_binaries=True,
    name='Aladin',
    debug=False,
    strip=False,
    upx=True,
    console=False,   # No black console window for the GUI
)

# ── Bot backend EXE (AladinBot.exe) ───────────────────────────────────
bot = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[('config.json', '.')],
    hiddenimports=HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    cipher=block_cipher,
    noarchive=False,
)

bot_pyz = PYZ(bot.pure, bot.zipped_data, cipher=block_cipher)

bot_exe = EXE(
    bot_pyz,
    bot.scripts,
    [],
    exclude_binaries=True,
    name='AladinBot',
    debug=False,
    strip=False,
    upx=True,
    console=True,    # Keep console visible for log output piping
)

# ── Collect BOTH into one output folder ───────────────────────────────
coll = COLLECT(
    gui_exe,
    gui.binaries,
    gui.zipfiles,
    gui.datas,
    bot_exe,
    bot.binaries,
    bot.zipfiles,
    bot.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Aladin',
)
