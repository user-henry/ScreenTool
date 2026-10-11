"""
ScreenTool 用户偏好设置 v2

- 默认全部保存在本地：%APPDATA%/ScreenTool/settings.json
- 支持读取 / 写入 / 恢复默认 / 变更存储目录 / 变更监听
- 所有写入均为原子写入（tmp + os.replace），线程安全
"""

import copy
import json
import os
import threading

APP_NAME = "ScreenTool"
APP_VERSION = "2.3.0"


# 默认设置
DEFAULTS = {
    # ── 外观 ──
    "theme": "dark",
    "accent": "#3DE1FF",
    "show_toast": True,           # 显示右下角操作提示
    "result_topmost": True,       # 结果面板置顶
    "history_columns": 3,         # 历史窗口每行卡片数（0 = 自动）

    # ── 截图 ──
    "auto_copy_image": True,      # 截图后自动复制到剪贴板
    "show_result_window": True,   # 截图后自动弹出结果面板
    "capture_hint": True,         # 框选时显示提示条
    "magnifier": True,            # 框选时显示放大镜
    "dim_strength": 0.40,         # 框选时背景暗化程度
    "restore_clipboard": False,   # 粘贴历史截图后恢复原剪贴板内容

    # ── OCR ──
    "ocr_enabled": True,          # 自动识别文字
    "ocr_save_to_history": True,  # 把识别结果一起存入历史
    "max_colors": 8,              # 最多提取的主色数量

    # ── 历史记录（默认开启：所有截图本地保存） ──
    "save_history": True,
    "history_dir": "",            # 空 = 默认目录
    "max_history": 500,           # 0 = 不限制
    "confirm_delete": True,       # 删除前确认
    "history_categories": ["默认", "代码", "设计", "文档", "聊天", "临时"],
    "auto_title": True,           # 自动用时间生成标题

    # ── 绳子（屏幕顶部的相片墙） ──
    "rope_enabled": True,         # 截图后自动挂到绳子上
    "rope_position": "top",       # top = 屏幕顶部 / bottom = 屏幕底部
    "rope_height": 200,           # 绳子条带高度（像素）
    "rope_max_items": 8,          # 绳子上最多挂几张
    "rope_autohide": True,        # 无操作后自动收起成一条细线
    "rope_autohide_delay": 6,     # 自动收起延迟（秒）
    "rope_swing": True,           # 挂上后轻微摆动
    "rope_drag_paste": True,      # 拖出绳子松手即粘贴到当前窗口
    "rope_remove_after_paste": False,   # 粘贴后是否从绳子取下

    # ── 毛玻璃与视觉特效 ──
    "glass_enabled": True,        # 原生毛玻璃背景
    "glass_mode": "blur",         # blur（平滑）/ acrylic（更亮，Win10 上可能掉帧）
    "glass_alpha": 0.97,          # 窗口整体不透明度
    "glass_tint": "#0B1020",      # 玻璃染色
    "glass_tint_alpha": 112,      # 染色浓度 0-255

    # ── 快捷键 ──
    "hotkey_capture": "ctrl+alt+x",
    "hotkey_history": "ctrl+alt+h",
    "hotkey_paste_last": "ctrl+alt+z",
    "hotkey_settings": "",        # 空 = 不注册

    # ── 画笔 ──
    "brush": {
        "tool": "pen",
        "color": "#FF3B30",
        "width": 3,
        "text_size": 20,
        "mosaic_block": 12,
        "recent_colors": ["#FF3B30", "#FFB020", "#35D07F", "#3DE1FF", "#7C5CFF", "#FFFFFF", "#000000"],
    },
}


def data_dir() -> str:
    """应用数据目录（%APPDATA%/ScreenTool）"""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def default_history_dir() -> str:
    """默认历史截图目录"""
    path = os.path.join(data_dir(), "history")
    os.makedirs(path, exist_ok=True)
    return path


class AppSettings:
    """设置管理器（线程安全，写入原子，支持变更监听）"""

    def __init__(self, path: str = None):
        self._path = path or os.path.join(data_dir(), "settings.json")
        self._lock = threading.RLock()
        self._listeners = []
        self._data = copy.deepcopy(DEFAULTS)
        self.load()

    # ── 属性 ──

    @property
    def path(self) -> str:
        return self._path

    # ── 监听 ──

    def add_listener(self, callback):
        """注册变更回调（在 set/update/reset 后调用，参数为完整设置字典）"""
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def _notify(self):
        listeners = list(self._listeners)
        snapshot = self.as_dict()
        for cb in listeners:
            try:
                cb(snapshot)
            except Exception:
                pass

    # ── 读写 ──

    def load(self) -> dict:
        """从磁盘载入设置，缺失字段用默认值补齐"""
        with self._lock:
            merged = copy.deepcopy(DEFAULTS)
            try:
                if os.path.exists(self._path):
                    with open(self._path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        for key, value in data.items():
                            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                                merged[key].update(value)
                            else:
                                merged[key] = value
            except Exception:
                pass
            self._data = merged
            return copy.deepcopy(self._data)

    def save(self) -> bool:
        """原子写入磁盘"""
        with self._lock:
            try:
                os.makedirs(os.path.dirname(self._path), exist_ok=True)
                tmp = self._path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, ensure_ascii=False, indent=2)
                os.replace(tmp, self._path)
                return True
            except Exception:
                return False

    # ── 访问 ──

    def get(self, key: str, default=None):
        with self._lock:
            if key in self._data:
                return copy.deepcopy(self._data[key])
            if default is not None:
                return default
            return copy.deepcopy(DEFAULTS.get(key))

    def set(self, key: str, value, save: bool = False) -> None:
        with self._lock:
            self._data[key] = value
            if save:
                self.save()
        self._notify()

    def update(self, mapping: dict, save: bool = False) -> None:
        with self._lock:
            for key, value in mapping.items():
                if key == "brush" and isinstance(value, dict):
                    self._data.setdefault("brush", {}).update(value)
                else:
                    self._data[key] = value
            if save:
                self.save()
        self._notify()

    def reset(self) -> None:
        """恢复默认设置"""
        with self._lock:
            self._data = copy.deepcopy(DEFAULTS)
            self.save()
        self._notify()

    def as_dict(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._data)

    # ── 便捷方法 ──

    def history_dir(self) -> str:
        """当前生效的历史截图目录"""
        custom = (self.get("history_dir") or "").strip()
        if custom:
            try:
                os.makedirs(custom, exist_ok=True)
                return custom
            except Exception:
                pass
        return default_history_dir()

    def category_list(self) -> list:
        """分类列表（去重、保序、去除空项）"""
        out = []
        for name in (self.get("history_categories") or []):
            name = (name or "").strip()
            if name and name not in out:
                out.append(name)
        if "默认" not in out:
            out.insert(0, "默认")
        return out

    def add_category(self, name: str) -> list:
        name = (name or "").strip()
        cats = self.category_list()
        if name and name not in cats:
            cats.append(name)
            self.set("history_categories", cats, save=True)
        return self.category_list()

    def remove_category(self, name: str) -> list:
        cats = [c for c in self.category_list() if c != (name or "").strip()]
        self.set("history_categories", cats, save=True)
        return self.category_list()

    def rename_category(self, old: str, new: str) -> list:
        new = (new or "").strip()
        cats = self.category_list()
        if new and old in cats and new not in cats:
            cats[cats.index(old)] = new
            self.set("history_categories", cats, save=True)
        return self.category_list()

    def brush(self, key: str, default=None):
        brush = self.get("brush") or {}
        return brush.get(key, default)

    def remember_brush(self, **kwargs):
        """保存画笔状态（工具、颜色、粗细等），立即写入本地"""
        brush = self.get("brush") or {}
        brush.update(kwargs)
        self.set("brush", brush)
        self.save()
