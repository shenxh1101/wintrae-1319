from pathlib import Path
from typing import Optional, Tuple
from PIL import Image
from .utils import is_image_file


def get_image_dimensions(file_path: Path) -> Optional[Tuple[int, int]]:
    if not is_image_file(file_path):
        return None
    try:
        with Image.open(file_path) as img:
            return img.size
    except Exception:
        return None


def get_image_format(file_path: Path) -> Optional[str]:
    if not is_image_file(file_path):
        return None
    try:
        with Image.open(file_path) as img:
            return img.format
    except Exception:
        return None


def get_image_info(file_path: Path) -> dict:
    info = {
        "path": file_path,
        "extension": file_path.suffix.lower(),
        "size_bytes": file_path.stat().st_size,
        "is_image": is_image_file(file_path),
        "is_brush": not is_image_file(file_path),
        "dimensions": None,
        "image_format": None,
        "mode": None,
    }
    if info["is_image"]:
        try:
            with Image.open(file_path) as img:
                info["dimensions"] = img.size
                info["image_format"] = img.format
                info["mode"] = img.mode
        except Exception:
            pass
    return info
