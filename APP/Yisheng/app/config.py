from __future__ import annotations

import ctypes
import os
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MODEL_ROOT = ROOT / ".models"
WHISPER_MODEL_ROOT = MODEL_ROOT / "whisper"
ARGOS_MODEL_ROOT = MODEL_ROOT / "argos"
ARGOS_STATE_ROOT = MODEL_ROOT / "argos-state"

# Argos reads this environment variable when it is imported.
os.environ.setdefault("XDG_DATA_HOME", str(ARGOS_STATE_ROOT / "data"))
os.environ.setdefault("XDG_CONFIG_HOME", str(ARGOS_STATE_ROOT / "config"))
os.environ.setdefault("XDG_CACHE_HOME", str(ARGOS_STATE_ROOT / "cache"))
os.environ.setdefault("ARGOS_PACKAGES_DIR", str(ARGOS_MODEL_ROOT))
os.environ.setdefault("ARGOS_TRANSLATE_PACKAGE_DIR", str(ARGOS_MODEL_ROOT))
# Hugging Face's optional Xet transfer helper can stall behind some Windows
# networks. Plain HTTPS supports resume and is sufficient for these models.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


LANGUAGES: dict[str, dict[str, str]] = {
    "auto": {"name": "自动识别", "whisper": "", "argos": ""},
    "en": {"name": "英语", "whisper": "en", "argos": "en"},
    "ja": {"name": "日语", "whisper": "ja", "argos": "ja"},
    "ko": {"name": "韩语", "whisper": "ko", "argos": "ko"},
    "fr": {"name": "法语", "whisper": "fr", "argos": "fr"},
    "de": {"name": "德语", "whisper": "de", "argos": "de"},
    "es": {"name": "西班牙语", "whisper": "es", "argos": "es"},
    "ru": {"name": "俄语", "whisper": "ru", "argos": "ru"},
    "pt": {"name": "葡萄牙语", "whisper": "pt", "argos": "pt"},
    "it": {"name": "意大利语", "whisper": "it", "argos": "it"},
    "zh": {"name": "中文", "whisper": "zh", "argos": "zh"},
}


@dataclass(frozen=True)
class HardwareInfo:
    os: str
    cpu: str
    ram_gb: float
    available_ram_gb: float
    gpu: str | None
    vram_mb: int | None
    cuda_runtime_ready: bool

    def to_dict(self) -> dict:
        return asdict(self)


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def memory_gb() -> tuple[float, float]:
    try:
        status = _MemoryStatusEx()
        status.dwLength = ctypes.sizeof(status)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        return (
            round(status.ullTotalPhys / (1024**3), 1),
            round(status.ullAvailPhys / (1024**3), 1),
        )
    except (AttributeError, OSError):
        return 0.0, 0.0


def _cpu_name() -> str:
    if platform.system() == "Windows":
        try:
            import winreg

            path = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
                return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
        except OSError:
            pass
    return platform.processor() or "未知处理器"


def _nvidia_gpu() -> tuple[str | None, int | None]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        system_path = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        candidate = system_path / "System32" / "nvidia-smi.exe"
        executable = str(candidate) if candidate.exists() else None
    if not executable:
        return None, None
    try:
        result = subprocess.run(
            [
                executable,
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=4,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        first = result.stdout.strip().splitlines()[0]
        name, memory = [item.strip() for item in first.rsplit(",", 1)]
        return name, int(memory)
    except (OSError, ValueError, subprocess.SubprocessError, IndexError):
        return None, None


def _dll_available(name: str) -> bool:
    try:
        ctypes.WinDLL(name)
        return True
    except (AttributeError, OSError):
        return False


def detect_hardware() -> HardwareInfo:
    gpu, vram = _nvidia_gpu()
    total_ram, available_ram = memory_gb()
    # Current CTranslate2 GPU wheels expect CUDA 12 + cuDNN 9.
    cuda_ready = bool(gpu) and _dll_available("cublas64_12.dll") and _dll_available("cudnn64_9.dll")
    return HardwareInfo(
        os=f"{platform.system()} {platform.release()} ({platform.machine()})",
        cpu=_cpu_name(),
        ram_gb=total_ram,
        available_ram_gb=available_ram,
        gpu=gpu,
        vram_mb=vram,
        cuda_runtime_ready=cuda_ready,
    )


def recommended_profile(hardware: HardwareInfo) -> dict[str, str | float]:
    if hardware.cuda_runtime_ready and (hardware.vram_mb or 0) >= 6000:
        # Short rolling chunks let the UI publish a provisional sentence while
        # the speaker is still talking. The existing overlap/context merge then
        # revises that same row instead of waiting for a complete 4+ second clip.
        return {"model": "base", "device": "cuda", "compute_type": "float16", "chunk_seconds": 1.4}
    return {"model": "base", "device": "cpu", "compute_type": "int8", "chunk_seconds": 1.8}
