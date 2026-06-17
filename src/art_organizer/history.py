import json
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from .utils import safe_rename

def get_history_dir(base_dir: str, history_dir: Optional[str] = None) -> Path:
    """获取历史记录目录路径。"""
    if history_dir:
        history_path = Path(history_dir)
    else:
        history_path = Path(base_dir) / ".art-organizer-history"
    history_path.mkdir(parents=True, exist_ok=True)
    return history_path


def get_history_files(history_dir: Path) -> List[Path]:
    """获取所有历史记录文件，按时间倒序排列。"""
    files = list(history_dir.glob("history_*.json"))
    files.sort(key=lambda x: x.stem, reverse=True)
    return files


def save_operation_history(
    base_dir: str,
    operation_type: str,
    changes: List[Dict[str, Any]],
    history_dir: Optional[str] = None,
    description: str = ""
) -> Path:
    """保存操作历史记录。

    Args:
        base_dir: 基础目录
        operation_type: 操作类型 (tag, rename 等
        changes: 变更列表，每项包含 old_path, new_path, old_name, new_name
        history_dir: 历史记录目录
        description: 操作描述
    """
    hist_dir = get_history_dir(base_dir, history_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    history_file = hist_dir / f"history_{timestamp}_{operation_type}.json"

    history_data = {
        "timestamp": datetime.now().isoformat(),
        "timestamp_pretty": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "operation_type": operation_type,
        "base_directory": str(Path(base_dir).resolve()),
        "description": description,
        "total_changes": len(changes),
        "successful_changes": [c for c in changes if c.get("success", True)],
        "failed_changes": [c for c in changes if not c.get("success", True)],
        "changes": changes,
    }

    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)

    return history_file


def load_history(history_file: Path) -> Dict[str, Any]:
    """加载历史记录文件。"""
    with open(history_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_latest_history(base_dir: str, history_dir: Optional[str] = None, n: int = 1) -> Optional[Dict[str, Any]]:
    """获取最近的历史记录。

    Args:
        base_dir: 基础目录
        history_dir: 历史记录目录
        n: 获取最近第 n 条记录 (1 是最新)
    """
    hist_dir = get_history_dir(base_dir, history_dir)
    history_files = get_history_files(hist_dir)

    if n <= len(history_files):
        return load_history(history_files[n - 1])
    return None


def list_history(base_dir: str, history_dir: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """列出历史记录摘要。"""
    hist_dir = get_history_dir(base_dir, history_dir)
    history_files = get_history_files(hist_dir)

    summaries = []
    for hf in history_files[:limit]:
        data = load_history(hf)
        summaries.append({
            "file": str(hf),
            "timestamp": data.get("timestamp"),
            "timestamp_pretty": data.get("timestamp_pretty"),
            "operation_type": data.get("operation_type"),
            "description": data.get("description"),
            "total_changes": data.get("total_changes", 0),
        })

    return summaries


def rollback_history(
    history_data: Dict[str, Any],
    dry_run: bool = False
) -> Tuple[int, int, List[Dict[str, Any]]]:
    """回滚操作历史。

    Args:
        history_data: 历史记录数据
        dry_run: 是否仅预览

    Returns:
        (成功数量, 失败数量, 回滚结果列表)
    """
    changes = history_data.get("changes", [])
    success_count = 0
    fail_count = 0
    results = []

    for change in reversed(changes):
        if not change.get("success", True):
            continue

        old_path = Path(change["new_path"])
        target_path = Path(change["old_path"])

        result = {
            "old_path": str(old_path),
            "target_path": str(target_path),
            "old_name": change["new_name"],
            "target_name": change["old_name"],
            "success": False,
            "error": None,
        }

        if dry_run:
            result["success"] = True
            success_count += 1
            results.append(result)
            continue

        try:
            if old_path.exists():
                target_full_path = old_path.parent / target_path.name
                ok, actual_path = safe_rename(old_path, target_full_path)
                if ok:
                    result["actual_path"] = str(actual_path)
                    result["success"] = True
                    success_count += 1
                else:
                    result["error"] = str(actual_path)
                    fail_count += 1
            else:
                result["error"] = "文件不存在"
                fail_count += 1
        except Exception as e:
            result["error"] = str(e)
            fail_count += 1

        results.append(result)

    return success_count, fail_count, results


def rollback_latest(
    base_dir: str,
    history_dir: Optional[str] = None,
    n: int = 1,
    dry_run: bool = False
) -> Tuple[Optional[Dict[str, Any]], int, int, List[Dict[str, Any]]]:
    """回滚最近的操作。

    Returns:
        (回滚的历史记录, 成功数, 失败数, 结果列表)
    """
    history_data = get_latest_history(base_dir, history_dir, n)
    if not history_data:
        return None, 0, 0, []

    success_count, fail_count, results = rollback_history(history_data, dry_run)
    return history_data, success_count, fail_count, results


def clear_history(base_dir: str, history_dir: Optional[str] = None, keep: int = 0) -> int:
    """清理历史记录。

    Args:
        base_dir: 基础目录
        history_dir: 历史记录目录
        keep: 保留最近的数量，0 表示全部删除

    Returns:
        删除的记录数
    """
    hist_dir = get_history_dir(base_dir, history_dir)
    history_files = get_history_files(hist_dir)

    files_to_delete = history_files[keep:] if keep > 0 else history_files

    count = 0
    for hf in files_to_delete:
        try:
            hf.unlink()
            count += 1
        except Exception:
            pass

    return count


def create_change_record(
    old_path: Path,
    new_path: Path,
    success: bool = True,
    error: Optional[str] = None
) -> Dict[str, Any]:
    """创建变更记录。"""
    return {
        "old_path": str(old_path),
        "new_path": str(new_path),
        "old_name": old_path.name,
        "new_name": new_path.name,
        "success": success,
        "error": error,
        "timestamp": datetime.now().isoformat(),
    }
