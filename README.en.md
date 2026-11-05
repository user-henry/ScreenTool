**English** | [简体中文](README.md)

# ScreenTool - Screenshot Toolkit v2.3

A Windows screenshot enhancement tool: **region capture + dominant color extraction + offline OCR + brush annotations + screenshot history**,
with everything processed locally. All screenshots are saved locally by default and survive restarts.

After a capture, the screenshot is automatically hung on the "rope" at the top of the screen — **drag the photo onto any window and release to paste it directly**.

## Feature overview

| Module | Description |
|------|------|
| Region capture | `Ctrl+Alt+X` for full-screen region selection, with multi-monitor support, crosshair guides, a live size label and a follow cursor magnifier; `Esc` / right-click to cancel, `Enter` / double-click to capture the whole screen |
| Color extraction | K-means clustering of dominant colors; click a swatch to copy its HEX value |
| Offline OCR | Local recognition with PaddleOCR + ONNX Runtime, preserving layout (line breaks, indentation), with one-click copy of the full text |
| Brush annotations | Pen / highlighter / line / arrow / rectangle / ellipse / text / mosaic — 8 tools; undo, redo, zoom, color and stroke width |
| Screenshot history | Card-grid browsing; rename, categorize, tag, note, favorite, search, sort and multi-select; one-click **copy (paste anytime)**, save as, re-annotate, overwrite, delete and export |
| Rope photo wall | New captures automatically hang on the rope at the top of the screen (drop + swing animation); drag left/right to reorder, drag out to paste into the current app; auto-collapses into a glowing line when idle and expands on hover |
| Frosted glass | Native blur-behind that truly blurs the content behind the window, with gradient tinting, rounded corners and edge glow; adjustable in Settings |
| Settings | 7 tabs: General / Capture / History / Hotkeys / Brush / Storage / About; preferences are saved immediately |

> The settings page now has **8 tabs** (with the new "Rope & Effects" tab).

## How to use the rope (photo wall)

| Action | Effect |
|------|------|
| Take a screenshot | The photo drops down and hangs at the left end of the rope, swinging slightly |
| Drag a photo left/right | Reorder it on the rope |
| Drag a photo off the rope and release | Paste automatically into the window under the cursor (the target window name is shown below) |
| Release over empty desktop space | Treated as cancel; the photo returns to the rope |
| Right-click a photo | Paste / copy only / annotate / view in history / remove from rope / delete record |
| Move the mouse away for a while | The rope collapses automatically, leaving a glowing line at the top; approaching re-expands it |
| Tray menu → Show / collapse rope | Expand or collapse manually |

> Pasting mechanism: the rope window never steals focus; on release the image is written to the clipboard and `Ctrl+V` is simulated,
> so the paste target is "the window you were already using". Dragging into applications that only accept file drops
> would require OLE drag-and-drop support (not currently enabled).

## Hotkeys (defaults; editable in "Settings → Hotkeys")

| Hotkey | Action |
|--------|------|
| `Ctrl+Alt+X` | Region capture |
| `Ctrl+Alt+H` | Open screenshot history |
| `Ctrl+Alt+Z` | Copy the latest screenshot to the clipboard |
| `Esc` / right-click | Cancel region selection |
| `Enter` / double-click | Capture the entire screen |

## Data and privacy

| Content | Location |
|------|------|
| User preferences | `%APPDATA%\ScreenTool\settings.json` |
| History index | `%APPDATA%\ScreenTool\history\index.json` |
| Original images | `%APPDATA%\ScreenTool\history\images\<id>.png` |
| Thumbnails | `%APPDATA%\ScreenTool\history\thumbs\<id>.jpg` |

- "Save screenshots automatically" is enabled by default; you can turn it off, cap the number of records, or use a custom storage directory under **Settings → History**.
- All recognition and drawing happen locally; screenshots are never uploaded to any server.

## Download and use

### Option 1: download the EXE (recommended)

Download the latest `ScreenTool.exe` from [Releases](https://github.com/user-henry/ScreenTool/releases)
and put it in the same folder as the `models/` directory, then double-click it.

> On first launch it downloads the PaddleOCR ONNX models (about 10 MB); afterwards it works fully offline.

### Option 2: run from source

```bash
git clone https://github.com/user-henry/ScreenTool.git
cd ScreenTool
pip install -r requirements.txt
python src/main.py
```

## Building it yourself

```bash
pip install pyinstaller
pyinstaller --clean --noconfirm ScreenTool.spec
# Output: dist/ScreenTool.exe
```

## Tests

```bash
python tests\smoke_test.py       # Data layer: settings, history CRUD, categories, search, limits, migration, import/export
python tests\gui_smoke_test.py   # UI layer: result panel, history window, brush, settings, dialogs, capture overlay
```

Both test suites use temporary data directories and will not touch existing records on your machine.

## Tech stack

- Python + tkinter (custom dark tech theme)
- PaddleOCR + ONNX Runtime (offline OCR)
- Pillow (capture, color extraction, brush rendering)
- pystray (system tray), keyboard (global hotkeys)

## License

MIT License
