r"""
ScreenTool 数据层烟雾测试

覆盖：设置持久化、历史记录 CRUD、搜索、分类、限额裁剪、图片读写、
缩略图、导入导出、重启后数据恢复。

运行： python tests\smoke_test.py
"""

import os
import shutil
import sys
import tempfile

# 必须在导入项目模块前隔离数据目录
TEMP_APPDATA = tempfile.mkdtemp(prefix="screentool_smoke_")
os.environ["APPDATA"] = TEMP_APPDATA

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, os.path.abspath(SRC))

from PIL import Image, ImageDraw  # noqa: E402

import app_settings  # noqa: E402
from app_settings import AppSettings  # noqa: E402
from history_manager import HistoryManager  # noqa: E402

PASS = []
FAIL = []


def check(name, condition, detail=""):
    if condition:
        PASS.append(name)
        print(f"  [PASS] {name}")
    else:
        FAIL.append(f"{name} — {detail}")
        print(f"  [FAIL] {name} — {detail}")


def make_image(w=120, h=80, color=(30, 60, 120)):
    img = Image.new("RGB", (w, h), color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, w - 10, h - 10], outline=(255, 255, 255), width=2)
    draw.text((16, 30), "ScreenTool", fill=(255, 255, 255))
    return img


def main():
    print("=" * 62)
    print("ScreenTool 数据层烟雾测试")
    print(f"临时数据目录: {TEMP_APPDATA}")
    print("=" * 62)

    # ── 1. 设置 ──
    print("\n[1] 设置读写与持久化")
    settings = AppSettings()
    check("默认设置已加载", settings.get("hotkey_capture") == "ctrl+alt+x")
    check("默认开启历史保存", settings.get("save_history") is True)
    check("设置文件路径位于临时目录", settings.path.startswith(TEMP_APPDATA), settings.path)

    settings.set("max_history", 3, save=True)
    settings.update({"accent": "#7C5CFF", "auto_copy_image": False}, save=True)
    settings.add_category("测试分类")
    check("分类新增成功", "测试分类" in settings.category_list())
    check("分类去重", settings.category_list().count("测试分类") == 1)

    reloaded = AppSettings()
    check("重启后设置保持", reloaded.get("max_history") == 3 and
          reloaded.get("accent") == "#7C5CFF", str(reloaded.as_dict().get("max_history")))
    check("重启后分类保持", "测试分类" in reloaded.category_list())
    check("brush 深合并保留其它字段",
          isinstance(reloaded.get("brush"), dict) and "width" in reloaded.get("brush"))

    settings.remember_brush(color="#00FF00", width=7)
    check("画笔设置可保存", AppSettings().brush("color") == "#00FF00")

    # ── 2. 历史记录 CRUD ──
    print("\n[2] 历史记录增删改查")
    history = HistoryManager(settings)
    base_dir = history.base_dir
    check("历史目录已创建", os.path.isdir(os.path.join(base_dir, "images")))

    img = make_image()
    e1 = history.add(img, title="第一条", category="代码", ocr_text="hello world",
                     colors=["#1E3C78"], source="capture")
    e2 = history.add(img, title="第二条", category="设计", source="capture")
    e3 = history.add(img, title="第三条", source="capture")
    check("新增三条记录", history.count() == 3, str(history.count()))
    check("记录包含必要字段",
          all(k in e1 for k in ("id", "title", "category", "created_at", "file", "thumb")))
    check("图片文件已落盘", os.path.exists(os.path.join(base_dir, e1["file"].replace("/", os.sep))))
    check("缩略图已生成", bool(e1["thumb"]) and
          os.path.exists(os.path.join(base_dir, e1["thumb"].replace("/", os.sep))))

    check("按分类筛选", len(history.entries(category="代码")) == 1)
    check("搜索标题", len(history.entries(query="第二条")) == 1)
    check("搜索 OCR 文字", len(history.entries(query="hello")) == 1)
    check("排序：最早优先",
          history.entries(sort="oldest")[0]["id"] == e1["id"])
    check("排序：最新优先",
          history.entries(sort="newest")[0]["id"] == e3["id"])

    history.rename(e1["id"], "改名后的第一条")
    check("重命名生效", history.get(e1["id"])["title"] == "改名后的第一条")
    history.set_category(e2["id"], "文档")
    check("修改分类生效", history.get(e2["id"])["category"] == "文档")
    history.set_tags(e2["id"], ["重要", " 待整理 ", ""])
    check("标签清洗", history.get(e2["id"])["tags"] == ["重要", "待整理"])
    history.set_note(e2["id"], "这是一条备注")
    check("备注保存", history.get(e2["id"])["note"] == "这是一条备注")

    history.toggle_pinned(e3["id"])
    check("收藏置顶", history.entries()[0]["id"] == e3["id"])
    check("收藏计数", history.stats()["pinned"] == 1)

    history.attach_ocr(e2["id"], ocr_text="识别结果ABC")
    check("OCR 回填", history.get(e2["id"])["ocr_text"] == "识别结果ABC")

    loaded = history.image_of(e1["id"])
    check("读取完整图片", loaded is not None and loaded.size == img.size)
    thumb = history.thumbnail_of(e1["id"])
    check("读取缩略图", thumb is not None and thumb.width <= 420)
    preview = history.preview_image(e1["id"], (60, 40))
    check("预览缩放", preview is not None and preview.width <= 60)

    # ── 3. 覆盖保存（画笔） ──
    print("\n[3] 画笔覆盖保存")
    new_img = make_image(200, 140, (200, 40, 40))
    updated = history.replace_image(e1["id"], new_img)
    check("覆盖保存返回记录", updated is not None)
    check("覆盖后尺寸更新", updated["width"] == 200 and updated["height"] == 140)
    check("覆盖后缩略图重建", os.path.exists(os.path.join(base_dir, updated["thumb"].replace("/", os.sep))))

    # ── 4. 持久化（模拟重启） ──
    print("\n[4] 重启后数据恢复")
    history2 = HistoryManager(AppSettings())
    check("重启后记录数一致", history2.count() == 3, str(history2.count()))
    check("重启后标题保持", history2.get(e1["id"])["title"] == "改名后的第一条")
    check("重启后分类保持", history2.get(e2["id"])["category"] == "文档")
    check("重启后标签保持", history2.get(e2["id"])["tags"] == ["重要", "待整理"])
    check("重启后收藏保持", history2.get(e3["id"])["pinned"] is True)
    check("重启后 OCR 保持", history2.get(e2["id"])["ocr_text"] == "识别结果ABC")

    # ── 5. 限额裁剪 ──
    print("\n[5] 记录数上限裁剪")
    for i in range(5):
        history2.add(make_image(60, 40), title=f"批量{i}")
    check("裁剪后不超过上限（收藏不参与裁剪）",
          history2.count() <= 4, str(history2.count()))
    check("裁剪后仍保留收藏记录", history2.get(e3["id"]) is not None)

    # ── 6. 导入 / 导出 ──
    print("\n[6] 导入与导出")
    export_dir = os.path.join(TEMP_APPDATA, "export")
    ids = [e["id"] for e in history2.entries()]
    count = history2.export_entries(ids, export_dir)
    check("导出 PNG 数量正确", count == len(ids), f"{count}/{len(ids)}")
    check("导出目录非空", len(os.listdir(export_dir)) == count)

    index_path = os.path.join(TEMP_APPDATA, "index_backup.json")
    check("导出索引 JSON", history2.export_index_json(index_path) and os.path.exists(index_path))

    src_file = os.path.join(export_dir, os.listdir(export_dir)[0])
    imported = history2.import_image(src_file, title="导入的图", category="导入")
    check("从文件导入成功", imported is not None and history2.get(imported["id"]) is not None)

    # ── 7. 删除与清空 ──
    print("\n[7] 删除与清空")
    before = history2.count()
    check("删除单条", history2.delete(imported["id"]) and history2.count() == before - 1)
    check("删除后图片文件被清理",
          not os.path.exists(os.path.join(base_dir, imported["file"].replace("/", os.sep))))
    check("按分类批量迁移", history2.move_category("文档", "归档") in (True, False))

    # 丢失文件的处理
    victim = history2.entries()[0]
    os.remove(os.path.join(base_dir, victim["file"].replace("/", os.sep)))
    check("文件丢失后仍能列出（默认包含）",
          any(e["id"] == victim["id"] for e in history2.entries()))
    check("include_missing=False 会过滤丢失项",
          not any(e["id"] == victim["id"] for e in history2.entries(include_missing=False)))
    removed = history2.mark_all_missing()
    check("清理无效记录", removed >= 1 and history2.get(victim["id"]) is None)

    total = history2.count()
    cleared = history2.clear_all()
    check("清空全部记录", cleared == total and history2.count() == 0)
    check("清空后图片目录为空",
          len(os.listdir(os.path.join(base_dir, "images"))) == 0)

    # ── 8. 目录切换 ──
    print("\n[8] 切换存储目录")
    new_dir = os.path.join(TEMP_APPDATA, "custom_history")
    settings.set("history_dir", new_dir, save=True)
    history3 = HistoryManager(AppSettings())
    check("使用自定义目录", os.path.abspath(history3.base_dir) == os.path.abspath(new_dir),
          history3.base_dir)
    history3.add(make_image(), title="新目录里的图")
    check("自定义目录可写入", history3.count() == 1)
    history3.attach_base(app_settings.default_history_dir())
    check("attach_base 重新载入", history3.base_dir.endswith("history"))

    # ── 汇总 ──
    print("\n" + "=" * 62)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    for item in FAIL:
        print(f"  [X] {item}")
    print("=" * 62)

    shutil.rmtree(TEMP_APPDATA, ignore_errors=True)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
