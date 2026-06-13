"""
PyInstaller runtime hook:
1. 提供递归 dummy torch 模块，避免 PaddleOCR 依赖链访问 torch.* 时的 AttributeError
2. 伪造 ocr-core 包的版本元数据，绕过 paddlex 的 pipeline_requires_extra 检查
"""
import sys
import types
import importlib.machinery
import importlib.metadata as _importlib_metadata


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Part 1: 递归 dummy torch 模块
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class _TorchDummyModule(types.ModuleType):
    """
    递归 dummy 模块：任何属性访问都自动创建子 dummy 并注册到 sys.modules。
    同时支持 callable 调用。
    """

    def __new__(cls, name: str):
        existing = sys.modules.get(name)
        if existing is not None and isinstance(existing, cls):
            return existing
        return super().__new__(cls, name)

    def __init__(self, name: str):
        super().__init__(name)
        self.__spec__ = importlib.machinery.ModuleSpec(name, None)
        self.__path__ = []
        self.__package__ = name.rsplit('.', 1)[0] if '.' in name else ''

    def __getattr__(self, name: str):
        if name.startswith('__') and name.endswith('__'):
            raise AttributeError(name)
        sub_name = f'{self.__name__}.{name}' if self.__name__ else name
        if sub_name in sys.modules:
            return sys.modules[sub_name]
        sub = _TorchDummyModule(sub_name)
        sys.modules[sub_name] = sub
        return sub

    def __call__(self, *args, **kwargs):
        return self

    def __repr__(self):
        return f'<_TorchDummy {self.__name__}>'


def _patch_torch():
    """在 sys.modules 中注入递归 dummy torch 模块。"""
    for name in (
        'torch', 'torch.multiprocessing', 'torch.distributed',
        'torch.nn', 'torch.utils', 'torch.cuda', 'torch.autograd',
    ):
        sys.modules[name] = _TorchDummyModule(name)


_patch_torch()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Part 2: 伪造 ocr-core 依赖的版本元数据
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# paddlex/inference/pipelines/ocr/pipeline.py:510
#   @pipeline_requires_extra("ocr", alt="ocr-core")
#
# 该检查通过 importlib.metadata.version() 验证包是否安装。
# PyInstaller 不会自动收集未显式导入的包的 dist-info，
# 导致 PackageNotFoundError → DependencyError → RuntimeError。
# 这里对 ocr-core 的 6 个包返回假版本号，绕过检查且不增加 EXE 体积。

_OCR_CORE_FAKES = frozenset({
    'imagesize', 'opencv-contrib-python', 'pyclipper',
    'pypdfium2', 'python-bidi', 'shapely',
})

# 这些包被排除在 EXE 外，但 PyInstaller 可能仍保留了 dist-info 元数据。
# 若 is_dep_available() 返回 True，get_default_device() 会检测到它们并错误判定为 GPU。
# 强制让 is_dep_available 返回 False，避免 dummy torch 的 truthy 值误导 GPU 检测。
_BLOCK_DEP_AVAILABLE = frozenset({'torch', 'paddlepaddle'})

_original_version = _importlib_metadata.version

def _patched_version(distribution_name):
    if distribution_name in _OCR_CORE_FAKES:
        return '0.0.0'
    if distribution_name in _BLOCK_DEP_AVAILABLE:
        raise _importlib_metadata.PackageNotFoundError(distribution_name)
    return _original_version(distribution_name)

_importlib_metadata.version = _patched_version
