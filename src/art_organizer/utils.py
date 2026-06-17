import os
import re
import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp', '.svg', '.raw', '.heic', '.heif'}
BRUSH_EXTENSIONS = {'.abr', '.tpl', '.brush', '.gbr', '.vbr', '.brushset'}
ALL_SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | BRUSH_EXTENSIONS

TAG_PATTERN = re.compile(r'\[([^\]]+)\]')
DATE_PATTERN = re.compile(r'(\d{4}[-_]?\d{2}[-_]?\d{2})')


def human_readable_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0 B"
    size_names = ("B", "KB", "MB", "GB", "TB")
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"


def scan_files(
    directory: str,
    recursive: bool = True,
    extensions: Optional[set] = None,
    images_only: bool = False,
    brushes_only: bool = False,
    extension_filter: Optional[str] = None,
) -> List[Path]:
    if extensions is None:
        extensions = ALL_SUPPORTED_EXTENSIONS

    if images_only:
        extensions = IMAGE_EXTENSIONS
    elif brushes_only:
        extensions = BRUSH_EXTENSIONS

    if extension_filter:
        ext = extension_filter.lower()
        if not ext.startswith('.'):
            ext = '.' + ext
        extensions = {ext}

    dir_path = Path(directory)
    if not dir_path.exists():
        raise FileNotFoundError(f"目录不存在: {directory}")
    if not dir_path.is_dir():
        raise NotADirectoryError(f"不是目录: {directory}")
    files = []
    pattern = "**/*" if recursive else "*"
    for path in dir_path.glob(pattern):
        if path.is_file() and path.suffix.lower() in extensions:
            files.append(path)
    return sorted(files)


def calculate_hash(file_path: Path, chunk_size: int = 8192) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            sha256.update(chunk)
    return sha256.hexdigest()


def get_file_date(file_path: Path) -> datetime:
    stat = file_path.stat()
    mtime = stat.st_mtime
    ctime = stat.st_ctime
    return datetime.fromtimestamp(min(mtime, ctime))


def extract_tags(filename: str) -> List[str]:
    return TAG_PATTERN.findall(filename)


def remove_tags_from_filename(filename: str, tags_to_remove: List[str]) -> str:
    name, ext = os.path.splitext(filename)
    current_tags = extract_tags(name)
    remaining_tags = [t for t in current_tags if t not in tags_to_remove]
    name_without_tags = TAG_PATTERN.sub('', name).strip('_-. ')
    if remaining_tags:
        tag_str = ''.join(f'[{t}]' for t in remaining_tags)
        if name_without_tags:
            return f"{name_without_tags}_{tag_str}{ext}"
        else:
            return f"{tag_str}{ext}"
    else:
        if name_without_tags:
            return f"{name_without_tags}{ext}"
        else:
            return filename


def add_tags_to_filename(filename: str, tags: List[str]) -> str:
    name, ext = os.path.splitext(filename)
    existing_tags = extract_tags(name)
    new_tags = [t for t in tags if t not in existing_tags]
    all_tags = existing_tags + new_tags
    name_without_tags = TAG_PATTERN.sub('', name).strip('_-. ')
    if all_tags:
        tag_str = ''.join(f'[{t}]' for t in all_tags)
        if name_without_tags:
            return f"{name_without_tags}_{tag_str}{ext}"
        else:
            return f"{tag_str}{ext}"
    return filename


def format_date(date: datetime) -> str:
    return date.strftime("%Y%m%d")


def safe_rename(src: Path, dst: Path, dry_run: bool = False) -> Tuple[bool, Optional[str]]:
    if src == dst:
        return False, None
    if dst.exists():
        base, ext = os.path.splitext(str(dst))
        counter = 1
        while True:
            new_dst = Path(f"{base}_{counter}{ext}")
            if not new_dst.exists():
                dst = new_dst
                break
            counter += 1
    if dry_run:
        return True, str(dst)
    try:
        os.rename(src, dst)
        return True, str(dst)
    except Exception as e:
        return False, str(e)


def safe_copy(src: Path, dst: Path, dry_run: bool = False) -> Tuple[bool, Optional[str]]:
    if dst.exists():
        base, ext = os.path.splitext(str(dst))
        counter = 1
        while True:
            new_dst = Path(f"{base}_{counter}{ext}")
            if not new_dst.exists():
                dst = new_dst
                break
            counter += 1
    if dry_run:
        return True, str(dst)
    try:
        shutil.copy2(src, dst)
        return True, str(dst)
    except Exception as e:
        return False, str(e)


def find_duplicates(files: List[Path]) -> Dict[str, List[Path]]:
    hash_map: Dict[str, List[Path]] = {}
    size_map: Dict[int, List[Path]] = {}
    for file_path in files:
        try:
            size = file_path.stat().st_size
            if size not in size_map:
                size_map[size] = []
            size_map[size].append(file_path)
        except Exception:
            continue
    for size, same_size_files in size_map.items():
        if len(same_size_files) < 2:
            continue
        for file_path in same_size_files:
            try:
                file_hash = calculate_hash(file_path)
                if file_hash not in hash_map:
                    hash_map[file_hash] = []
                hash_map[file_hash].append(file_path)
            except Exception:
                continue
    return {h: paths for h, paths in hash_map.items() if len(paths) > 1}


def is_image_file(file_path: Path) -> bool:
    return file_path.suffix.lower() in IMAGE_EXTENSIONS


def is_brush_file(file_path: Path) -> bool:
    return file_path.suffix.lower() in BRUSH_EXTENSIONS


def parse_size_category(width: int, height: int) -> str:
    total_pixels = width * height
    if total_pixels < 1024 * 1024:
        return "小图 (<1MP)"
    elif total_pixels < 2048 * 2048:
        return "中图 (1-4MP)"
    elif total_pixels < 4096 * 4096:
        return "大图 (4-16MP)"
    else:
        return "超大图 (>16MP)"
