import json
import hashlib
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from .utils import scan_files, calculate_hash, is_image_file, is_brush_file
from .metadata import get_image_info


def get_cache_dir(base_dir: str, cache_dir: Optional[str] = None) -> Path:
    """获取缓存目录路径。"""
    if cache_dir:
        cache_path = Path(cache_dir)
    else:
        cache_path = Path(base_dir) / ".art-organizer-cache"
    cache_path.mkdir(parents=True, exist_ok=True)
    return cache_path


def get_dir_hash(directory: str) -> str:
    """生成目录的哈希标识。"""
    abs_path = str(Path(directory).resolve())
    return hashlib.md5(abs_path.encode('utf-8')).hexdigest()


def get_cache_file(cache_dir: Path, dir_hash: str) -> Path:
    """获取指定目录的缓存文件路径。"""
    return cache_dir / f"index_{dir_hash}.json"


def generate_file_record(file_path: Path) -> Dict[str, Any]:
    """生成单个文件的缓存记录。"""
    stat = file_path.stat()
    record = {
        "path": str(file_path.resolve()),
        "name": file_path.name,
        "extension": file_path.suffix.lower(),
        "size_bytes": stat.st_size,
        "mtime": stat.st_mtime,
        "ctime": stat.st_ctime,
        "is_image": is_image_file(file_path),
        "is_brush": is_brush_file(file_path),
        "hash": None,
        "dimensions": None,
        "image_format": None,
        "mode": None,
        "last_analyzed": datetime.now().isoformat(),
    }

    try:
        if record["is_image"]:
            info = get_image_info(file_path)
            record["dimensions"] = info["dimensions"]
            record["image_format"] = info["image_format"]
            record["mode"] = info["mode"]
        record["hash"] = calculate_hash(file_path)
    except Exception:
        pass

    return record


def is_file_changed(file_path: Path, cached_record: Dict[str, Any]) -> bool:
    """检查文件是否已变动。"""
    try:
        stat = file_path.stat()
        return (stat.st_size != cached_record["size_bytes"] or
                abs(stat.st_mtime - cached_record["mtime"]) > 1)
    except Exception:
        return True


def load_cache(cache_file: Path) -> Dict[str, Any]:
    """加载缓存文件。"""
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache_file: Path, cache_data: Dict[str, Any]) -> None:
    """保存缓存文件。"""
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)


def scan_with_cache(
    directory: str,
    recursive: bool = True,
    cache_dir: Optional[str] = None,
    force_refresh: bool = False,
    images_only: bool = False,
    brushes_only: bool = False,
    extension_filter: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """带缓存的扫描，只重新分析变动的文件。

    返回: (文件记录列表, 扫描统计信息)
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        raise FileNotFoundError(f"目录不存在: {directory}")

    cache_path = get_cache_dir(directory, cache_dir)
    dir_hash = get_dir_hash(directory)
    cache_file = get_cache_file(cache_path, dir_hash)

    cached_data = load_cache(cache_file) if not force_refresh else {}
    cached_files = cached_data.get("files", {})

    files = scan_files(
        directory,
        recursive=recursive,
        images_only=images_only,
        brushes_only=brushes_only,
        extension_filter=extension_filter
    )

    records = []
    stats = {
        "total_files": len(files),
        "cached_files": 0,
        "new_files": 0,
        "changed_files": 0,
        "removed_files": 0,
        "scan_time": datetime.now().isoformat(),
        "directory": str(dir_path.resolve()),
    }

    for file_path in files:
        file_key = str(file_path.resolve())

        if file_key in cached_files and not force_refresh:
            if not is_file_changed(file_path, cached_files[file_key]):
                records.append(cached_files[file_key])
                stats["cached_files"] += 1
                continue
            else:
                stats["changed_files"] += 1
        else:
            stats["new_files"] += 1

        record = generate_file_record(file_path)
        records.append(record)
        cached_files[file_key] = record

    valid_keys = {str(f.resolve()) for f in files}
    removed = [k for k in cached_files.keys() if k not in valid_keys]
    stats["removed_files"] = len(removed)
    for k in removed:
        del cached_files[k]

    cache_data = {
        "directory": str(dir_path.resolve()),
        "generated_at": datetime.now().isoformat(),
        "recursive": recursive,
        "files": cached_files,
    }
    save_cache(cache_file, cache_data)

    return records, stats


def clear_cache(directory: str, cache_dir: Optional[str] = None) -> bool:
    """清除指定目录的缓存。"""
    cache_path = get_cache_dir(directory, cache_dir)
    dir_hash = get_dir_hash(directory)
    cache_file = get_cache_file(cache_path, dir_hash)

    if cache_file.exists():
        try:
            cache_file.unlink()
            return True
        except Exception:
            return False
    return False


def clear_all_cache(cache_dir: str) -> int:
    """清除所有缓存文件。"""
    cache_path = Path(cache_dir)
    if not cache_path.exists():
        return 0

    count = 0
    for cache_file in cache_path.glob("index_*.json"):
        try:
            cache_file.unlink()
            count += 1
        except Exception:
            pass
    return count


def get_cache_info(directory: str, cache_dir: Optional[str] = None) -> Dict[str, Any]:
    """获取缓存信息。"""
    cache_path = get_cache_dir(directory, cache_dir)
    dir_hash = get_dir_hash(directory)
    cache_file = get_cache_file(cache_path, dir_hash)

    info = {
        "cache_dir": str(cache_path),
        "cache_file": str(cache_file),
        "exists": cache_file.exists(),
        "file_count": 0,
        "generated_at": None,
        "size_bytes": 0,
    }

    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            info["file_count"] = len(data.get("files", {}))
            info["generated_at"] = data.get("generated_at")
            info["size_bytes"] = cache_file.stat().st_size
        except Exception:
            pass

    return info
