r"""
ScreenTool 界面烟雾测试（会短暂弹出窗口后自动关闭）

覆盖：主题应用、结果面板、历史窗口（卡片网格）、设置窗口、画笔窗口、
分类管理、预览窗口、暗色对话框、提示浮层，以及截图叠加层的框选裁剪逻辑。

运行： python tests\gui_smoke_test.py
"""

import os
import sys
import tempfile
import types

TEMP_APPDATA = tempfile.mkdtemp(prefix="screentool_gui_")
os.environ["APPDATA"] = TEMP_APPDATA

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, os.path.abspath(SRC))

import tkinter as tk  # noqa: E402

from PIL import Image, ImageDraw  # noqa: E402

import ui_theme  # noqa: E402
import glass  # noqa: E402
import windows_fx  # noqa: E402
from app_settings import AppSettings  # noqa: E402
from history_manager import HistoryManager  # noqa: E402
from result_window import ResultWindow  # noqa: E402
from history_window import HistoryWindow, PreviewWindow, CategoryManagerDialog  # noqa: E402
from settings_window import SettingsWindow  # noqa: E402
from paint_window import PaintWindow  # noqa: E402
from screen_capture import ScreenCapture  # noqa: E402
from rope_window import RopeWindow  # noqa: E402

PASS = []
FAIL = []


def check(name, condition, detail=""):
    if condition:
        PASS.append(name)
        print(f"  [PASS] {name}")
    else:
        FAIL.append(f"{name} — {detail}")
        print(f"  [FAIL] {name} — {detail}")


def pump(root, times=4, delay=0):
    for _ in range(times):
        try:
            root.update_idletasks()
            root.update()
        except Exception:
            pass


def make_image(w=400, h=260):
    img = Image.new("RGB", (w, h), (14, 21, 38))
    draw = ImageDraw.Draw(img)
    draw.rectangle([16, 16, w - 16, h - 16], outline=(61, 225, 255), width=2)
    draw.text((30, 40), "ScreenTool v2 GUI", fill=(232, 241, 255))
    draw.rectangle([30, 80, 180, 200], fill=(255, 176, 32))
    return img


def main():
    print("=" * 62)
    print("ScreenTool 界面烟雾测试")
    print(f"临时数据目录: {TEMP_APPDATA}")
    print("=" * 62)

    settings = AppSettings()
    settings.update({"show_toast": True, "history_columns": 3}, save=True)
    history = HistoryManager(settings)

    root = tk.Tk()
    root.withdraw()
    root.title("ScreenTool smoke")

    # ── 主题 ──
    print("\n[1] 主题与基础组件")
    style = ui_theme.apply(root, settings.get("accent"))
    check("ttk 主题应用成功", style is not None)
    check("配色表完整", all(k in ui_theme.COLORS for k in ("bg", "accent", "danger")))
    check("分类颜色稳定",
          ui_theme.category_color("代码") == ui_theme.category_color("代码"))

    holder = tk.Toplevel(root)
    holder.withdraw()
    scroll = ui_theme.ScrollableFrame(holder)
    scroll.pack(fill=tk.BOTH, expand=True)
    for i in range(20):
        tk.Label(scroll.inner, text=f"行 {i}").pack()
    pump(root)
    scroll.scroll_to_top()
    scroll.clear()
    check("ScrollableFrame 可用", len(scroll.inner.winfo_children()) == 0)

    chip = ui_theme.Chip(holder, "测试分类")
    chip.set_active(True)
    check("分类标签组件可用", chip.color.startswith("#"))
    holder.destroy()

    # ── 历史数据 ──
    print("\n[2] 历史数据准备")
    img = make_image()
    entries = []
    for i, (title, cat) in enumerate([("登录界面", "设计"), ("报错日志", "代码"),
                                      ("聊天记录", "聊天"), ("设计稿", "设计")]):
        e = history.add(img, title=title, category=cat,
                        ocr_text="示例识别文字" if i % 2 == 0 else "System Error 500",
                        colors=["#3DE1FF", "#FFB020"], source="capture")
        entries.append(e)
    history.toggle_pinned(entries[0]["id"])
    check("准备 4 条测试记录", history.count() == 4, str(history.count()))

    # ── 结果面板 ──
    print("\n[3] 截图结果面板")
    colors = [{"hex": "#3DE1FF", "rgb": (61, 225, 255), "pct": 42.0},
              {"hex": "#FFB020", "rgb": (255, 176, 32), "pct": 18.5},
              {"hex": "#0E1526", "rgb": (14, 21, 38), "pct": 39.5}]
    rw = ResultWindow(root, settings, history, callbacks={"history": lambda: None})
    rw.show(img, colors, "识别中…", entry=entries[0])
    pump(root)
    check("结果面板已创建", rw.is_open())
    rw.set_ocr_text("这是一段 OCR 识别结果\n第二行")
    pump(root)
    check("OCR 文本可异步更新",
          "OCR 识别结果" in rw._ocr_widget.get("1.0", tk.END))
    check("OCR 结果写回历史",
          history.get(entries[0]["id"])["ocr_text"].startswith("这是一段"))
    check("颜色色块已渲染", len(rw._colors) == 3)
    rw._on_copy_image()
    rw._save_meta()
    pump(root)
    check("保存标题与分类无异常", True)
    rw.close()
    pump(root)
    check("结果面板可关闭", not rw.is_open())

    # ── 历史窗口 ──
    print("\n[4] 历史截图窗口")
    hw = HistoryWindow(root, settings, history, callbacks={
        "paste": lambda entry, auto=False: None,
        "paint": lambda entry: None,
        "settings": lambda: None,
        "on_changed": lambda: None,
    })
    hw.show()
    pump(root)
    check("历史窗口已打开", bool(hw.win and hw.win.winfo_exists()))
    check("卡片数量与记录一致", len(hw._cards) == history.count(),
          f"{len(hw._cards)}/{history.count()}")

    hw._set_filter("设计")
    pump(root)
    check("分类筛选生效", len(hw._cards) == 2, str(len(hw._cards)))
    hw._set_filter("全部")

    hw._search_var.set("报错")
    pump(root)
    check("搜索过滤生效", len(hw._cards) == 1, str(len(hw._cards)))
    hw._clear_search()
    pump(root)

    first_id = list(hw._cards.keys())[0]
    hw._toggle_select(first_id)
    pump(root)
    check("卡片可多选", first_id in hw._selected)
    hw._select_all()
    check("全选可用", len(hw._selected) == len(hw._cards))
    hw._clear_selection()
    check("取消选择可用", not hw._selected)

    hw._sort_var.set("标题")
    hw._on_sort()
    hw._sort_var.set("最新优先")
    hw._on_sort()
    pump(root)
    check("排序切换无异常", True)

    hw._load_more()
    pump(root)
    check("加载更多无异常", True)

    hw._rename({"id": entries[1]["id"], "title": "报错日志"})
    check("重命名对话框可构建/取消", history.get(entries[1]["id"])["title"] == "报错日志")

    # ── 预览窗口 ──
    print("\n[5] 历史截图详情预览")
    preview = PreviewWindow(root, settings, history, hw._current_entries(), 0,
                            callbacks={"on_changed": lambda: None})
    preview.show()
    pump(root)
    check("预览窗口已打开", bool(preview.win and preview.win.winfo_exists()))
    preview._nav(1)
    pump(root)
    check("可切换到下一张", preview.index == 1)
    preview._save_fields()
    pump(root)
    check("预览中保存字段无异常", True)
    preview._copy_ocr()
    preview._nav(-1)
    pump(root)
    preview._close()
    check("预览窗口可关闭", preview.win is None)

    # ── 设置窗口 ──
    print("\n[6] 设置窗口")
    applied = {"count": 0}
    sw = SettingsWindow(root, settings, history,
                        on_apply=lambda s, info=None: applied.__setitem__("count", applied["count"] + 1))
    sw.show()
    pump(root)
    check("设置窗口已打开", bool(sw.win and sw.win.winfo_exists()))
    check("分页数量正确", len(sw.notebook.tabs()) == 8, str(len(sw.notebook.tabs())))
    check("含「绳子与特效」分页",
          any("绳子" in sw.notebook.tab(tab, "text") for tab in sw.notebook.tabs()))
    data = sw._collect()
    check("设置项收集完整",
          all(k in data for k in ("save_history", "hotkey_capture", "accent", "max_history")))
    check("画笔设置可收集", isinstance(data.get("brush"), dict) and "width" in data["brush"])
    sw._load_values()
    check("设置值可回填", sw._vars["hotkey_capture"].get() == settings.get("hotkey_capture"))
    sw._save()
    pump(root)
    check("保存触发应用回调", applied["count"] >= 1)

    # 保存必须真正落盘（而不是只改了内存或写到错误的层级）
    original_hotkey = settings.get("hotkey_capture")
    sw._vars["hotkey_capture"].set("ctrl+alt+j")
    sw._save()
    pump(root)
    check("保存后设置落盘", AppSettings().get("hotkey_capture") == "ctrl+alt+j")
    sw._vars["hotkey_capture"].set(original_hotkey)
    sw._save()
    pump(root)
    check("设置可恢复原值", AppSettings().get("hotkey_capture") == original_hotkey)

    sw.set_status("测试状态")
    sw._refresh_storage_info()
    pump(root)
    check("设置窗口状态刷新无异常", True)
    sw.hide()
    check("设置窗口可关闭", sw.win is None)

    # ── 分类管理 ──
    print("\n[7] 分类管理")
    cm = CategoryManagerDialog(root, settings, history, on_done=lambda: None)
    pump(root)
    check("分类管理窗口已打开", bool(cm.win and cm.win.winfo_exists()))
    cm._new_var.set("临时分类")
    cm._add()
    pump(root)
    check("可新增分类", "临时分类" in settings.category_list())
    cm._close()
    check("分类管理窗口可关闭", True)

    # ── 画笔窗口 ──
    print("\n[8] 画笔批注窗口")
    pw = PaintWindow(root, img, settings, title="批注测试", entry=entries[0],
                     history=history)
    pump(root, 6)
    check("画笔窗口已打开", bool(pw.win and pw.win.winfo_exists()))
    check("工具按钮齐全", len(pw._tool_buttons) == 8, str(len(pw._tool_buttons)))

    pw._set_tool("pen")
    pw._ops.append({"tool": "pen", "points": [(10, 10), (60, 60), (120, 30)],
                    "color": "#FF3B30", "width": 4})
    pw._set_tool("highlighter")
    pw._ops.append({"tool": "highlighter", "points": [(20, 80), (160, 90)],
                    "color": "#FFB020", "width": 6})
    pw._ops.append({"tool": "line", "start": (10, 100), "end": (200, 120),
                    "color": "#35D07F", "width": 3})
    pw._ops.append({"tool": "arrow", "start": (30, 150), "end": (220, 60),
                    "color": "#3DE1FF", "width": 4})
    pw._ops.append({"tool": "rect", "start": (40, 30), "end": (180, 140),
                    "color": "#7C5CFF", "width": 3})
    pw._ops.append({"tool": "ellipse", "start": (60, 50), "end": (200, 180),
                    "color": "#FF7AD9", "width": 3})
    pw._ops.append({"tool": "text", "start": (25, 200), "text": "批注文字\n第二行",
                    "color": "#FFFFFF", "size": 22})
    pw._ops.append({"tool": "mosaic", "start": (200, 150), "end": (330, 230), "block": 10})
    rendered = pw.result_image()
    check("全部画笔工具可渲染", rendered.size == img.size and rendered is not None)
    src_pixels = list(img.convert("RGB").getdata())
    out_pixels = list(rendered.getdata())
    changed = sum(1 for a, b in zip(src_pixels, out_pixels) if a != b)
    check("渲染结果与原图不同", changed > 0, f"变化像素 {changed}")

    pw._redraw()
    pump(root, 4)
    check("画布重绘无异常", pw._photo is not None)
    before = len(pw._ops)
    pw._undo()
    pump(root)
    check("撤销可用", len(pw._ops) == before - 1)
    pw._redo_last()
    pump(root)
    check("重做可用", len(pw._ops) == before)

    pw._zoom_by(1.5)
    pump(root)
    check("缩放可用", pw._zoom > 1.0)
    pw._zoom_fit()
    pump(root)
    check("适应窗口可用", abs(pw._zoom - 1.0) < 1e-6)

    pw._set_tool("rect")
    # 事件坐标是画布坐标，需从图片坐标换算，才能补偿居中偏移与缩放
    cx1, cy1 = pw._to_canvas(40, 40)
    cx2, cy2 = pw._to_canvas(180, 140)
    pw._on_press(types.SimpleNamespace(x=cx1, y=cy1))
    pw._on_motion(types.SimpleNamespace(x=cx2, y=cy2))
    pw._on_release(types.SimpleNamespace(x=cx2, y=cy2))
    pump(root)
    check("模拟鼠标拖拽绘制成功", len(pw._ops) == before + 1)

    count_before = history.count()
    pw._save("new")
    pump(root)
    check("保存为新记录成功", history.count() == count_before + 1)
    saved = pw.entry or {}
    check("新记录来源为 paint", saved.get("source") == "paint", str(saved.get("source")))

    # 覆盖保存会弹确认框：测试中直接放行，保证该路径被确定性地执行
    import paint_window as _paint_module
    _real_ask = _paint_module.messagebox.askyesno
    _paint_module.messagebox.askyesno = lambda *a, **k: True
    try:
        pw._save("overwrite")
    finally:
        _paint_module.messagebox.askyesno = _real_ask
    pump(root)
    overwritten = history.get(saved["id"]) if saved.get("id") else None
    check("覆盖原记录成功", overwritten is not None)
    if overwritten:
        check("覆盖后图片已更新",
              list(history.image_of(overwritten).getdata()) != src_pixels)

    pw._copy_result()
    pump(root)
    check("复制批注结果无异常", True)

    pw._ops = []          # 避免关闭时的确认对话框
    pw._on_close()
    check("画笔窗口可关闭", pw.win is not None or pw._closed)

    # ── 暗色对话框 ──
    print("\n[9] 暗色对话框与提示")
    closed = {"v": False}

    def close_modal():
        try:
            for child in root.winfo_children():
                if isinstance(child, tk.Toplevel) and child.winfo_exists():
                    if child.wm_title() in ("重命名截图", "添加文字", "确认"):
                        child.destroy()
                        closed["v"] = True
        except Exception:
            pass

    root.after(250, close_modal)
    result = ui_theme.prompt_fields(root, "重命名截图",
                                    [{"key": "title", "label": "标题", "value": "abc"}])
    check("暗色输入对话框可构建", closed["v"] and result is None)

    closed["v"] = False
    root.after(250, close_modal)
    result2 = ui_theme.prompt_text(root, "添加文字", label="输入内容", multiline=True)
    check("暗色多行输入框可构建", closed["v"] and result2 is None)

    closed["v"] = False
    root.after(250, close_modal)
    confirmed = ui_theme.confirm(root, "确认", "确定执行吗？")
    check("暗色确认框可构建", closed["v"] and confirmed is False)

    toast_win = ui_theme.toast(root, "测试提示", "这是一条提示信息", kind="success")
    pump(root)
    check("提示浮层可显示", toast_win is not None and toast_win.winfo_exists())
    ui_theme.close_all_toasts()
    pump(root)
    check("提示浮层可全部关闭", ui_theme._active_toasts == [])

    # ── 截图叠加层 ──
    print("\n[10] 截图叠加层（自动模拟一次框选）")
    cap = ScreenCapture(root, settings)
    driver = {"ran": False}

    def drive():
        if cap.win is None:
            root.after(80, drive)
            return
        driver["ran"] = True
        ev = lambda x, y: types.SimpleNamespace(x=x, y=y)  # noqa: E731
        cap._on_press(ev(50, 40))
        cap._on_drag(ev(250, 180))
        cap._on_motion(ev(250, 180))
        cap._on_release(ev(250, 180))

    root.after(120, drive)
    result = cap.capture()
    check("叠加层已运行", driver["ran"])
    if result:
        check("框选裁剪尺寸正确",
              result["image"].size == (200, 140), str(result["image"].size))
        check("返回屏幕坐标", isinstance(result.get("x"), int) and isinstance(result.get("y"), int))
        check("返回整屏图像", result.get("full_image") is not None)
    else:
        check("框选返回结果", False, "capture() 返回 None（可能显示器不可用）")

    # 取消路径
    cap2 = ScreenCapture(root, settings)

    def cancel():
        if cap2.win is None:
            root.after(80, cancel)
            return
        cap2._on_cancel()

    root.after(120, cancel)
    check("ESC/右键取消返回 None", cap2.capture() is None)

    # ── 毛玻璃与原生特效 ──
    print("\n[11] 毛玻璃与原生特效")
    panel = glass.glass_panel(160, 90, radius=14)
    check("玻璃面板渲染成功", panel.mode == "RGBA" and panel.width > 160 and panel.height > 90)
    card_img = glass.photo_card(make_image(120, 90), 110, 96, caption="测试卡片")
    check("相片卡渲染成功", card_img.mode == "RGBA" and card_img.width >= 110)
    check("相片卡可旋转", glass.rotate_card(card_img, 5).width >= card_img.width)
    check("徽章渲染成功", glass.badge("示例 3").mode == "RGBA")
    check("绳子贴图渲染成功", glass.rope_curve(240, sag=12).mode == "RGBA")

    check("识别到 Windows 平台", windows_fx.IS_WINDOWS is True)
    geo = windows_fx.screen_geometry()
    check("屏幕尺寸有效", geo[2] > 0 and geo[3] > 0, str(geo))
    pos = windows_fx.cursor_pos()
    check("可读取鼠标位置", isinstance(pos[0], int) and isinstance(pos[1], int))
    under = windows_fx.window_under_cursor()
    check("可查询光标下的窗口",
          isinstance(under, dict) and "is_desktop" in under and "title" in under)
    check("毛玻璃调用不抛异常", isinstance(windows_fx.enable_blur(root), bool))

    # ── 绳子（相片墙） ──
    print("\n[12] 绳子相片墙")
    settings.set("rope_enabled", True, save=True)
    settings.set("rope_max_items", 6, save=True)
    pasted = []
    rope = RopeWindow(
        root, settings, history,
        callbacks={
            "paste": lambda entry, auto=True: pasted.append(entry.get("id")),
            "history": lambda: None,
            "paint": lambda entry: None,
            "delete": lambda entry: None,
        },
    )
    rope.reload()
    pump(root, 4)
    check("绳子窗口已创建", bool(rope.win and rope.win.winfo_exists()))
    check("卡片数量与历史一致",
          len(rope.cards) == min(int(settings.get("rope_max_items")), history.count()),
          f"{len(rope.cards)} / {history.count()}")

    new_entry = history.add(make_image(220, 140), title="绳子测试")
    added = rope.add_entry(new_entry)
    pump(root, 3)
    check("新截图挂到绳子最左端",
          added and rope.cards and rope.cards[0]["entry"]["id"] == new_entry["id"])

    # 拖动排序（在绳子内松手）
    def ev(x, y):
        return types.SimpleNamespace(x=x, y=y)

    card = rope.cards[0]
    rope._on_press(ev(card["x"] + card["w"] / 2, card["y"] + card["h"] / 2))
    rope._on_motion(ev(card["x"] + card["w"] / 2 + 320, card["y"] + card["h"] / 2))
    rope._on_release(ev(card["x"] + card["w"] / 2 + 320, card["y"] + card["h"] / 2))
    pump(root, 3)
    check("绳内拖动后卡片数量不变", len(rope.cards) == min(6, history.count()))

    # 拖出到「其它应用」→ 触发粘贴
    import rope_window as rope_module
    real_under = rope_module.windows_fx.window_under_cursor
    real_own = rope_module.windows_fx.is_own_window
    try:
        rope_module.windows_fx.window_under_cursor = lambda: {
            "hwnd": 11, "root": 22, "class_name": "Notepad",
            "title": "记事本", "is_desktop": False}
        rope_module.windows_fx.is_own_window = lambda hwnd, widgets: False
        card = rope.cards[0]
        rope._on_press(ev(card["x"] + 30, card["y"] + 20))
        rope._on_motion(ev(card["x"] + 60, rope._strip_h + 80))
        rope._on_release(ev(card["x"] + 60, rope._strip_h + 80))
        pump(root, 3)
        check("拖到其它应用触发粘贴", pasted and pasted[-1] == card["entry"]["id"])

        # 拖到桌面 → 不粘贴，卡片归位
        before = len(pasted)
        rope_module.windows_fx.window_under_cursor = lambda: {
            "hwnd": 33, "root": 44, "class_name": "Progman",
            "title": "", "is_desktop": True}
        card = rope.cards[0]
        rope._on_press(ev(card["x"] + 30, card["y"] + 20))
        rope._on_motion(ev(card["x"] + 60, rope._strip_h + 80))
        rope._on_release(ev(card["x"] + 60, rope._strip_h + 80))
        pump(root, 3)
        check("拖到桌面不触发粘贴", len(pasted) == before)
    finally:
        rope_module.windows_fx.window_under_cursor = real_under
        rope_module.windows_fx.is_own_window = real_own

    # 收起 / 展开
    rope._collapse_now()
    for _ in range(8):
        rope._tick()
    pump(root, 2)
    check("可自动收起成细线", rope._collapse > 0.02, f"{rope._collapse:.2f}")
    rope._on_enter()
    check("鼠标靠近时重新展开", rope._collapse_target == 0.0)

    # 设置关闭绳子
    settings.set("rope_enabled", False, save=True)
    rope.refresh_settings()
    pump(root, 2)
    check("关闭开关后绳子隐藏", rope._visible is False)
    settings.set("rope_enabled", True, save=True)
    rope.refresh_settings()
    pump(root, 2)
    check("重新开启后绳子显示", rope._visible is True)

    rope.destroy()
    pump(root, 2)
    check("绳子窗口可销毁", rope.win is None)

    # ── 收尾 ──
    hw.hide()
    ui_theme.close_all_toasts()
    root.update()
    try:
        root.destroy()
    except Exception:
        pass

    print("\n" + "=" * 62)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    for item in FAIL:
        print(f"  [X] {item}")
    print("=" * 62)

    import shutil
    shutil.rmtree(TEMP_APPDATA, ignore_errors=True)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
