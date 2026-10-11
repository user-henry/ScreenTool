"""
历史截图管理模块

- 每张截图以 PNG 落盘保存到本地（默认 %APPDATA%/ScreenTool/history/）
- 元数据（标题、分类、标签、备注、时间、尺寸、OCR 文本、主色）写入 index.json
- 支持：新增 / 查询 / 搜索 / 重命名 / 分类 / 标签 / 备注 / 删除 / 批量删除 / 清空 / 导入 / 导出
- 全部写入均为原子写入，线程安全；重启后数据完整恢复
"""

import datetime
import json
import os
import random
import shutil
import threading

from PIL import Image

import app_settings


INDEX_VERSION = 2
THUMB_SIZE = (420, 300)


def _now_iso() -> str:
    return datetime.datetime.now().replace(microsecond=0).isoformat()


def _new_id() -> str:
    """生成唯一 ID：时间戳 + 随机串"""
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    rand = "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(6))
    return f"{stamp}_{rand}"


def safe_name(name: str) -> str:
    """把标题转换为安全的文件名片段"""
    bad = '\\/:*?"<>|\r\n\t'
    out = "".join("_" if ch in bad else ch for ch in (name or "")).strip(" .")
    return out[:40] or "screenshot"


class HistoryManager:
    """历史截图存储与索引管理"""

    def __init__(self, settings: "app_settings.AppSettings"):
        self._settings = settings
        self._lock = threading.RLock()
        self._base = None
        self._images_dir = None
        self._thumbs_dir = None
        self._index_path = None
        self._entries = []
        self._seq = 0
        self.attach_base()

    # ════════════════════════════════
    # 目录与索引
    # ════════════════════════════════

    def attach_base(self, base_dir: str = None):
        """绑定存储目录并载入索引（目录变化时调用）"""
        with self._lock:
            self._base = os.path.abspath(base_dir or self._settings.history_dir())
            self._images_dir = os.path.join(self._base, "images")
            self._thumbs_dir = os.path.join(self._base, "thumbs")
            self._index_path = os.path.join(self._base, "index.json")
            for path in (self._base, self._images_dir, self._thumbs_dir):
                try:
                    os.makedirs(path, exist_ok=True)
                except Exception:
                    pass
            self._load()

    @property
    def base_dir(self) -> str:
        return self._base

    def _abs(self, rel_path: str) -> str:
        """索引中的相对路径 → 绝对路径"""
        if not rel_path:
            return ""
        rel_path = str(rel_path).replace("\\", "/")
        return os.path.join(self._base, *rel_path.split("/"))

    def _rel(self, abs_path: str) -> str:
        """绝对路径 → 索引中的相对路径（统一使用 /）"""
        try:
            rel = os.path.relpath(abs_path, self._base)
        except Exception:
            rel = abs_path
        return rel.replace("\\", "/")

    def _load(self):
        """载入 index.json（兼容旧版格式）"""
        entries = []
        try:
            if os.path.exists(self._index_path):
                with open(self._index_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    raw = data.get("entries", [])
                elif isinstance(data, list):
                    raw = data
                else:
                    raw = []
                for item in raw:
                    if isinstance(item, dict) and item.get("file"):
                        entries.append(self._normalize_entry(item))
        except Exception:
            entries = []
        self._entries = entries
        self._resync_seq()

    def _resync_seq(self):
        """
        按列表位置（索引越靠前越新）重建内部序号。
        序号用于「最新/最早」排序与限额裁剪，避免同一秒内的记录顺序错乱。
        """
        for offset, entry in enumerate(reversed(self._entries)):
            entry["_seq"] = offset + 1
        self._seq = len(self._entries)

    def _normalize_entry(self, item: dict) -> dict:
        """补齐缺失字段，保证索引项结构统一"""
        entry = {
            "id": item.get("id") or _new_id(),
            "title": item.get("title") or "未命名截图",
            "category": item.get("category") or "默认",
            "tags": item.get("tags") or [],
            "note": item.get("note") or "",
            "created_at": item.get("created_at") or _now_iso(),
            "width": int(item.get("width") or 0),
            "height": int(item.get("height") or 0),
            "file": item.get("file"),
            "thumb": item.get("thumb") or "",
            "ocr_text": item.get("ocr_text") or "",
            "colors": item.get("colors") or [],
            "source": item.get("source") or "capture",
            "pinned": bool(item.get("pinned")),
            "size_bytes": int(item.get("size_bytes") or 0),
            "_seq": int(item.get("_seq") or 0),
        }
        for key, value in item.items():
            if key not in entry:
                entry[key] = value
        return entry

    def _save(self):
        """原子写入索引"""
        try:
            payload = {
                "version": INDEX_VERSION,
                "updated_at": _now_iso(),
                "entries": self._entries,
            }
            tmp = self._index_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._index_path)
        except Exception:
            pass

    # ════════════════════════════════
    # 新增
    # ════════════════════════════════

    def add(self, image: Image.Image, title: str = None, category: str = None,
            ocr_text: str = "", colors: list = None, source: str = "capture",
            tags: list = None) -> dict:
        """
        保存一张截图到历史记录。

        Returns:
            新记录的元数据字典；失败返回 None
        """
        if image is None:
            return None

        with self._lock:
            entry_id = _new_id()
            title = (title or "").strip()
            if not title:
                if self._settings.get("auto_title", True):
                    title = datetime.datetime.now().strftime("截图 %Y-%m-%d %H:%M:%S")
                else:
                    title = "未命名截图"
            category = (category or "").strip() or self._default_category()

            abs_file = os.path.join(self._images_dir, f"{entry_id}.png")
            try:
                image.save(abs_file, format="PNG", optimize=True)
            except Exception:
                try:
                    image.convert("RGB").save(abs_file, format="PNG")
                except Exception:
                    return None

            try:
                size_bytes = os.path.getsize(abs_file)
            except Exception:
                size_bytes = 0

            entry = {
                "id": entry_id,
                "title": title,
                "category": category,
                "tags": list(tags or []),
                "note": "",
                "created_at": _now_iso(),
                "width": int(image.width),
                "height": int(image.height),
                "file": self._rel(abs_file),
                "thumb": "",
                "ocr_text": ocr_text or "",
                "colors": list(colors or []),
                "source": source,
                "pinned": False,
                "size_bytes": size_bytes,
            }
            entry["thumb"] = self._make_thumb(entry)

            self._seq += 1
            entry["_seq"] = self._seq
            self._entries.insert(0, entry)
            self._settings.add_category(category)
            self.enforce_limit()
            self._save()
            return dict(entry)

    def import_image(self, path: str, title: str = None, category: str = None) -> dict:
        """从本地图片文件导入一条历史记录"""
        try:
            with Image.open(path) as img:
                img.load()
                return self.add(
                    img,
                    title=title or os.path.splitext(os.path.basename(path))[0],
                    category=category,
                    source="import",
                )
        except Exception:
            return None

    def _default_category(self) -> str:
        cats = self._settings.category_list()
        return cats[0] if cats else "默认"

    def _make_thumb(self, entry: dict) -> str:
        """生成缩略图，返回相对路径（失败返回空串）"""
        try:
            src = self._abs(entry["file"])
            with Image.open(src) as img:
                img = img.convert("RGB")
                img.thumbnail(THUMB_SIZE, Image.LANCZOS)
                abs_thumb = os.path.join(self._thumbs_dir, f"{entry['id']}.jpg")
                img.save(abs_thumb, format="JPEG", quality=82)
            return self._rel(abs_thumb)
        except Exception:
            return ""

    # ════════════════════════════════
    # 查询
    # ════════════════════════════════

    def entries(self, category: str = None, query: str = None,
                sort: str = "newest", include_missing: bool = True) -> list:
        """
        查询历史记录。

        Args:
            category: 分类筛选（None / "全部" / "★ 收藏" 有特殊含义）
            query: 搜索关键词（标题 / 分类 / 标签 / 备注 / OCR 文本）
            sort: newest | oldest | title | size
            include_missing: 是否包含文件已丢失的记录
        """
        with self._lock:
            items = [dict(e) for e in self._entries]

        if category and category not in ("全部", "全部记录"):
            if category in ("★ 收藏", "收藏"):
                items = [e for e in items if e.get("pinned")]
            else:
                items = [e for e in items if (e.get("category") or "默认") == category]

        query = (query or "").strip().lower()
        if query:
            def match(e):
                haystack = " ".join([
                    str(e.get("title", "")),
                    str(e.get("category", "")),
                    " ".join(str(t) for t in (e.get("tags") or [])),
                    str(e.get("note", "")),
                    str(e.get("ocr_text", ""))[:2000],
                ]).lower()
                return query in haystack
            items = [e for e in items if match(e)]

        if not include_missing:
            items = [e for e in items if self.exists(e)]

        pinned = [e for e in items if e.get("pinned")]
        normal = [e for e in items if not e.get("pinned")]

        if sort == "oldest":
            key, reverse = (lambda e: int(e.get("_seq") or 0)), False
        elif sort == "title":
            key, reverse = (lambda e: str(e.get("title", ""))), False
        elif sort == "size":
            key, reverse = (lambda e: int(e.get("size_bytes") or 0)), True
        else:
            key, reverse = (lambda e: int(e.get("_seq") or 0)), True

        pinned.sort(key=key, reverse=reverse)
        normal.sort(key=key, reverse=reverse)
        return pinned + normal

    def get(self, entry_id: str) -> dict:
        with self._lock:
            for e in self._entries:
                if e.get("id") == entry_id:
                    return dict(e)
        return None

    def count(self) -> int:
        with self._lock:
            return len(self._entries)

    def latest(self) -> dict:
        """最近一张截图（按时间）"""
        items = self.entries(sort="newest", include_missing=False)
        return items[0] if items else None

    def exists(self, entry: dict) -> bool:
        path = self._abs(entry.get("file", ""))
        return bool(path) and os.path.exists(path)

    def stats(self) -> dict:
        with self._lock:
            entries = list(self._entries)
        total_bytes = 0
        categories = {}
        missing = 0
        for e in entries:
            name = e.get("category") or "默认"
            categories[name] = categories.get(name, 0) + 1
            try:
                total_bytes += os.path.getsize(self._abs(e.get("file", "")))
            except Exception:
                missing += 1
        return {
            "count": len(entries),
            "bytes": total_bytes,
            "categories": categories,
            "pinned": sum(1 for e in entries if e.get("pinned")),
            "missing": missing,
            "base_dir": self._base,
        }

    # ════════════════════════════════
    # 图片读取
    # ════════════════════════════════

    def image_of(self, entry) -> Image.Image:
        """读取完整图片（失败返回 None）"""
        if not entry:
            return None
        if not isinstance(entry, dict):
            entry = self.get(entry)
            if not entry:
                return None
        try:
            img = Image.open(self._abs(entry.get("file", "")))
            img.load()
            return img
        except Exception:
            return None

    def thumbnail_of(self, entry) -> Image.Image:
        """读取缩略图（缺失时自动重建）"""
        if isinstance(entry, str):
            entry = self.get(entry)
        if not entry:
            return None
        path = self._abs(entry.get("thumb", ""))
        if path and os.path.exists(path):
            try:
                img = Image.open(path)
                img.load()
                return img
            except Exception:
                pass
        rel = self._make_thumb(entry)
        if rel:
            with self._lock:
                for e in self._entries:
                    if e.get("id") == entry.get("id"):
                        e["thumb"] = rel
                        break
                self._save()
            updated = dict(entry)
            updated["thumb"] = rel
            return self.thumbnail_of(updated)
        return None

    def preview_image(self, entry: dict, max_size=(760, 560)) -> Image.Image:
        """按等比例缩放到指定上限，用于预览"""
        img = self.image_of(entry)
        if img is None:
            return None
        copy_img = img.copy()
        copy_img.thumbnail(max_size, Image.LANCZOS)
        return copy_img

    # ════════════════════════════════
    # 修改
    # ════════════════════════════════

    def update(self, entry_id: str, **fields) -> dict:
        """更新记录的任意字段"""
        allowed = {"title", "category", "tags", "note", "ocr_text", "colors",
                   "pinned", "source"}
        with self._lock:
            for e in self._entries:
                if e.get("id") == entry_id:
                    for key, value in fields.items():
                        if key in allowed:
                            e[key] = value
                    if fields.get("category"):
                        self._settings.add_category(fields["category"])
                    self._save()
                    return dict(e)
        return None

    def rename(self, entry_id: str, title: str) -> dict:
        title = (title or "").strip() or "未命名截图"
        return self.update(entry_id, title=title)

    def set_category(self, entry_id: str, category: str) -> dict:
        return self.update(entry_id, category=(category or "").strip() or "默认")

    def set_tags(self, entry_id: str, tags: list) -> dict:
        clean = [str(t).strip() for t in (tags or []) if str(t).strip()]
        return self.update(entry_id, tags=clean)

    def set_note(self, entry_id: str, note: str) -> dict:
        return self.update(entry_id, note=note or "")

    def toggle_pinned(self, entry_id: str) -> dict:
        entry = self.get(entry_id)
        if not entry:
            return None
        return self.update(entry_id, pinned=not entry.get("pinned"))

    def attach_ocr(self, entry_id: str, ocr_text: str = None, colors: list = None) -> dict:
        """异步 OCR / 取色结束后回填结果"""
        fields = {}
        if ocr_text is not None:
            fields["ocr_text"] = ocr_text
        if colors is not None:
            fields["colors"] = colors
        if not fields:
            return None
        return self.update(entry_id, **fields)

    def replace_image(self, entry_id: str, image: Image.Image) -> dict:
        """用新图片覆盖原记录（画笔批注「覆盖保存」）"""
        if image is None:
            return None
        with self._lock:
            entry = None
            for e in self._entries:
                if e.get("id") == entry_id:
                    entry = e
                    break
            if entry is None:
                return None
            abs_file = self._abs(entry["file"])
            try:
                image.save(abs_file, format="PNG", optimize=True)
            except Exception:
                try:
                    image.convert("RGB").save(abs_file, format="PNG")
                except Exception:
                    return None
            entry["width"] = int(image.width)
            entry["height"] = int(image.height)
            try:
                entry["size_bytes"] = os.path.getsize(abs_file)
            except Exception:
                pass
            entry["thumb"] = self._make_thumb(entry)
            self._save()
            return dict(entry)

    def move_category(self, old: str, new: str) -> bool:
        """把某个分类下的所有记录迁移到另一个分类"""
        with self._lock:
            changed = False
            for e in self._entries:
                if (e.get("category") or "默认") == old:
                    e["category"] = new
                    changed = True
            if changed:
                self._save()
        return changed

    def mark_all_missing(self) -> int:
        """移除所有源文件已丢失的记录（清理索引）"""
        with self._lock:
            before = len(self._entries)
            self._entries = [e for e in self._entries if self.exists(e)]
            self._save()
            return before - len(self._entries)

    # ════════════════════════════════
    # 删除
    # ════════════════════════════════

    def delete(self, entry_id: str) -> bool:
        """删除一条记录（同时删除图片与缩略图）"""
        with self._lock:
            target = None
            for e in self._entries:
                if e.get("id") == entry_id:
                    target = e
                    break
            if target is None:
                return False
            self._entries = [e for e in self._entries if e.get("id") != entry_id]
            for key in ("file", "thumb"):
                path = self._abs(target.get(key, ""))
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception:
                        pass
            self._save()
            return True

    def delete_many(self, entry_ids: list) -> int:
        count = 0
        for entry_id in list(entry_ids or []):
            if self.delete(entry_id):
                count += 1
        return count

    def clear_all(self) -> int:
        """清空全部历史记录（删除所有本地文件）"""
        with self._lock:
            count = len(self._entries)
            for folder in (self._images_dir, self._thumbs_dir):
                try:
                    shutil.rmtree(folder, ignore_errors=True)
                    os.makedirs(folder, exist_ok=True)
                except Exception:
                    pass
            self._entries = []
            self._save()
            return count

    def enforce_limit(self) -> int:
        """按设置中的 max_history 裁剪最旧记录（0 = 不限制）"""
        limit = int(self._settings.get("max_history") or 0)
        if limit <= 0:
            return 0
        with self._lock:
            if len(self._entries) <= limit:
                return 0
            ordered = sorted(self._entries, key=lambda e: int(e.get("_seq") or 0))
            removable = [e for e in ordered if not e.get("pinned")]
            overflow = len(self._entries) - limit
            removed = 0
            for e in removable[:max(0, overflow)]:
                for key in ("file", "thumb"):
                    path = self._abs(e.get(key, ""))
                    if path and os.path.exists(path):
                        try:
                            os.remove(path)
                        except Exception:
                            pass
                self._entries.remove(e)
                removed += 1
            if removed:
                self._save()
            return removed

    # ════════════════════════════════
    # 导入 / 导出
    # ════════════════════════════════

    def export_entries(self, entry_ids: list, dest_dir: str) -> int:
        """把指定记录导出为 PNG（文件名 = 标题）"""
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except Exception:
            return 0
        count = 0
        used = set()
        for entry_id in list(entry_ids or []):
            entry = self.get(entry_id)
            if not entry:
                continue
            src = self._abs(entry.get("file", ""))
            if not os.path.exists(src):
                continue
            base = safe_name(entry.get("title"))
            name = f"{base}.png"
            i = 1
            while name.lower() in used or os.path.exists(os.path.join(dest_dir, name)):
                name = f"{base}_{i}.png"
                i += 1
            used.add(name.lower())
            try:
                shutil.copy2(src, os.path.join(dest_dir, name))
                count += 1
            except Exception:
                pass
        return count

    def export_index_json(self, dest_path: str) -> bool:
        """导出索引 JSON（备份）"""
        try:
            payload = {
                "version": INDEX_VERSION,
                "exported_at": _now_iso(),
                "base_dir": self._base,
                "entries": self._entries,
            }
            with open(dest_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def categories_in_use(self) -> dict:
        """分类 → 记录数"""
        with self._lock:
            out = {}
            for e in self._entries:
                name = e.get("category") or "默认"
                out[name] = out.get(name, 0) + 1
            return out
