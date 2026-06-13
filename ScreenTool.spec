# -*- mode: python ; coding: utf-8 -*-
# ScreenTool PyInstaller 打包配置（OneFile 模式）
# 模型文件不嵌入，与 EXE 同目录分发。
from PyInstaller.utils.hooks import collect_all, collect_data_files

datas = []
binaries = []
hiddenimports = [
    'pystray', 'PIL', 'keyboard', 'pyperclip', 'tkinter',
    'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageGrab', 'PIL.ImageTk',
    'numpy', 'ctypes',
    'paddleocr', 'paddlex', 'onnxruntime',
    # OCR 运行时必须依赖：cv2（图像处理）、pyclipper（文本检测后处理）
    'cv2', 'cv2.data', 'pyclipper',
]

# 只收集轻量包的全部子模块
for _pkg in ('pystray', 'PIL', 'onnxruntime'):
    try:
        tmp_ret = collect_all(_pkg)
        datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
    except Exception:
        pass

# paddleocr / paddlex: 仅收集数据文件
for _pkg in ('paddleocr', 'paddlex'):
    try:
        _extra_datas = collect_data_files(_pkg)
        datas += _extra_datas
    except Exception:
        pass

# ── 去重 ──
datas = list(set(datas))
binaries = list(set(binaries))
hiddenimports = list(set(hiddenimports))

a = Analysis(
    ['src\\main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['build\\runtime_hook.py'],
    excludes=[
        'matplotlib', 'scipy', 'tensorflow',
        'torch', 'jupyter', 'IPython', 'notebook',
        'paddle',
        '81d243bd2c585b0f4821',        # 孤立 mypyc 模块，不属于任何包
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, upx=False)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ScreenTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,            # 禁用 UPX：避免二次压缩导致 .pyd 解压失败
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets\\icon.ico',
)
