# ScreenTool - 截屏工具箱

一个 Windows 截屏增强工具：**框选区域截屏 + 识别颜色 + OCR 文字识别**，所有结果一键复制。

## 功能

| 功能 | 说明 |
|------|------|
| 框选截图 | 按下 `Ctrl+Alt+X`，拖拽框选区域，截图自动复制到剪贴板 |
| 颜色提取 | 自动识别区域内主要颜色，显示色块和 HEX 码，点击复制 |
| OCR 文字 | 离线识别区域内文字，保留排版（换行、缩进），支持一键复制全部文字 |

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+Alt+X` | 启动截图 |
| `ESC` | 取消截图 |

## 下载使用

### 方式一：下载 EXE（推荐）

从 [Releases](https://github.com/user-henry/ScreenTool/releases) 页面下载最新 `ScreenTool.exe`，双击运行即可。

> 首次运行时程序会自动下载 PaddleOCR ONNX 模型（约 10MB），请保持网络畅通。后续使用无需联网。

### 方式二：源码运行

```bash
git clone https://github.com/user-henry/ScreenTool.git
cd ScreenTool
pip install -r requirements.txt
python src/main.py
```

## 自行打包

```bash
pip install pyinstaller
pyinstaller --clean --noconfirm ScreenTool.spec
# 输出在 dist/ScreenTool.exe
```

## 技术栈

- Python + tkinter
- PaddleOCR + ONNX Runtime（离线 OCR）
- PIL/Pillow（截图 + 颜色提取）
- pystray（系统托盘）
- keyboard（全局热键）

## 许可

MIT License
