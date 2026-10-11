# ScreenTool - 截屏工具箱 v2.3

一个 Windows 截屏增强工具：**框选截图 + 主色提取 + 离线 OCR + 画笔批注 + 历史截图管理**，
全部处理在本机完成，所有截图默认本地保存，重启不丢数据。

截图后会自动挂到屏幕顶部的「绳子」上，**把相片拖到任意窗口松手即可直接粘贴**。

## 功能总览

| 模块 | 说明 |
|------|------|
| 框选截图 | `Ctrl+Alt+X` 全屏框选，支持多显示器、十字准线、实时尺寸标签、跟随放大镜；`Esc` / 右键取消，`Enter` / 双击截取整屏 |
| 颜色提取 | K-means 聚类提取主色，色块点击即复制 HEX |
| 离线 OCR | PaddleOCR + ONNX Runtime 本地识别，保留排版（换行、缩进），一键复制全文 |
| 画笔批注 | 画笔 / 荧光笔 / 直线 / 箭头 / 矩形 / 椭圆 / 文字 / 马赛克，共 8 种工具；支持撤销重做、缩放、调色与粗细 |
| 历史截图 | 卡片网格浏览；重命名、分类、标签、备注、收藏、搜索、排序、批量选择；一键**复制（随时粘贴出）**、另存为、画笔二次编辑、覆盖保存、删除、导出 |
| 绳子相片墙 | 截图自动挂到屏幕顶部的绳子上（带落下 + 摆动动画）；可左右拖动排序、拖出即粘贴到当前应用；无操作自动收起成一条发光细线，靠近再展开 |
| 毛玻璃特效 | 原生 blur-behind 真实模糊窗口背后的内容，配合渐变染色、圆角与描边光晕；可在设置中调整模式与不透明度 |
| 设置 | 7 个分页：常规 / 截图 / 历史记录 / 快捷键 / 画笔 / 存储 / 关于；偏好即时保存 |

> 设置页现为 **8 个分页**（新增「绳子与特效」）。

## 绳子（相片墙）怎么用

| 操作 | 效果 |
|------|------|
| 截图 | 相片从上方落下挂到绳子最左端，并轻微摆动 |
| 按住相片左右拖动 | 调整在绳子上的顺序 |
| 把相片拖出绳子、松手 | 自动粘贴到光标所在的窗口（下方会提示目标窗口名） |
| 拖到桌面空白处松手 | 视为取消，相片回到绳子上 |
| 右键相片 | 粘贴 / 只复制 / 画笔批注 / 在历史中查看 / 从绳子取下 / 删除记录 |
| 鼠标离开一会儿 | 绳子自动收起，只在屏幕顶部留一条发光细线，靠近自动展开 |
| 托盘菜单 → 显示 / 收起绳子 | 手动展开或收起 |

> 粘贴原理：绳子窗口点击时不抢焦点，松手时把图片写入剪贴板并模拟 `Ctrl+V`，
> 因此粘贴目标是「你原本正在使用的那个窗口」。若要拖进只接受文件拖放的程序，
> 需要 OLE 拖放支持（当前未启用）。

## 快捷键（默认，均可在「设置 → 快捷键」中修改）

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+Alt+X` | 框选截图 |
| `Ctrl+Alt+H` | 打开历史截图 |
| `Ctrl+Alt+Z` | 粘贴最近一张截图到剪贴板 |
| `Esc` / 鼠标右键 | 取消框选 |
| `Enter` / 双击 | 截取整个屏幕 |

## 数据与隐私

| 内容 | 位置 |
|------|------|
| 用户偏好 | `%APPDATA%\ScreenTool\settings.json` |
| 历史索引 | `%APPDATA%\ScreenTool\history\index.json` |
| 原图 | `%APPDATA%\ScreenTool\history\images\<id>.png` |
| 缩略图 | `%APPDATA%\ScreenTool\history\thumbs\<id>.jpg` |

- 默认开启「截图自动保存到本地」；可在 **设置 → 历史记录** 中关闭保存、限制保留条数、或改用自定义存储目录。
- 所有识别与绘制都在本机完成，不向任何服务器上传截图。

## 下载使用

### 方式一：下载 EXE（推荐）

从 [Releases](https://github.com/user-henry/ScreenTool/releases) 下载最新 `ScreenTool.exe`，
与 `models/` 目录放在同一文件夹后双击运行。

> 首次运行会自动下载 PaddleOCR ONNX 模型（约 10MB），之后可完全离线使用。

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

## 测试

```bash
python tests\smoke_test.py       # 数据层：设置、历史 CRUD、分类、搜索、限额、迁移、导入导出
python tests\gui_smoke_test.py   # 界面层：结果面板、历史窗口、画笔、设置、对话框、截图叠加层
```

两套测试均使用临时数据目录，不会影响本机已有记录。

## 技术栈

- Python + tkinter（暗色科技风自绘主题）
- PaddleOCR + ONNX Runtime（离线 OCR）
- Pillow（截图、颜色提取、画笔渲染）
- pystray（系统托盘）、keyboard（全局热键）

## 许可

MIT License
