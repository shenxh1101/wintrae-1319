import click
import json
import csv
import re
import hashlib
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import track
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
from datetime import datetime, timedelta

from ..utils import (
    scan_files,
    human_readable_size,
    is_image_file,
    is_brush_file,
    IMAGE_EXTENSIONS,
    BRUSH_EXTENSIONS,
    extract_tags,
    get_file_date,
    parse_size_category,
    calculate_hash,
)
from ..metadata import get_image_info
from ..config import get_config_value

console = Console()


def get_report_dir(base_dir: str, report_dir: Optional[str] = None) -> Path:
    """获取报告目录。"""
    if report_dir:
        report_path = Path(report_dir)
    else:
        report_path = Path(base_dir) / "reports"
    report_path.mkdir(parents=True, exist_ok=True)
    return report_path


def _parse_report_from_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _parse_report_from_csv(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with open(path, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            files = []
            for row in reader:
                size_bytes = int(row.get("大小(字节)", 0) or 0)
                tags_str = row.get("标签", "")
                tags = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else []
                fe = {
                    "path": row.get("路径", ""),
                    "name": row.get("文件名", ""),
                    "extension": row.get("扩展名", ""),
                    "type": row.get("类型", ""),
                    "size_bytes": size_bytes,
                    "size_human": row.get("大小", ""),
                    "tags": tags,
                    "directory": row.get("目录", ""),
                    "created_at": row.get("创建日期", ""),
                }
                width = row.get("宽度", "")
                height = row.get("高度", "")
                if width and height:
                    fe["width"] = int(width)
                    fe["height"] = int(height)
                    fe["resolution"] = row.get("分辨率", "")
                files.append(fe)

        total_size = sum(fe["size_bytes"] for fe in files)
        total_files = len(files)
        image_count = sum(1 for fe in files if fe["type"] == "图片")
        brush_count = sum(1 for fe in files if fe["type"] == "画笔")
        image_size = sum(fe["size_bytes"] for fe in files if fe["type"] == "图片")
        brush_size = sum(fe["size_bytes"] for fe in files if fe["type"] == "画笔")

        ts_match = re.search(r'report_(\d{8}_\d{6})', path.name)
        generated_at = ""
        if ts_match:
            generated_at = datetime.strptime(ts_match.group(1), "%Y%m%d_%H%M%S").isoformat()

        return {
            "generated_at": generated_at,
            "directory": "",
            "summary": {
                "total_files": total_files,
                "total_size_bytes": total_size,
                "total_size_human": human_readable_size(total_size),
                "image_count": image_count,
                "image_size_bytes": image_size,
                "brush_count": brush_count,
                "brush_size_bytes": brush_size,
            },
            "files": files,
        }
    except Exception:
        return None


def get_previous_report(report_dir: Path) -> Tuple[Optional[Dict[str, Any]], Optional[Path]]:
    """获取最近的历史报告，同时返回报告文件路径。

    对比始终在导出之前执行，所以目录中的报告都是已保存的历史版本，
    直接取最新的一份作为对比基准。

    Returns:
        (报告数据, 报告文件路径) 或 (None, None)
    """
    all_reports = []
    for p in report_dir.glob("report_*"):
        if p.suffix.lower() not in ('.json', '.csv'):
            continue
        all_reports.append(p)

    if not all_reports:
        return None, None

    all_reports.sort(reverse=True)

    for rf in all_reports:
        if rf.suffix.lower() == '.json':
            data = _parse_report_from_json(rf)
        elif rf.suffix.lower() == '.csv':
            data = _parse_report_from_csv(rf)
        else:
            continue
        if data is not None:
            return data, rf

    return None, None


def compare_reports(
    current: Dict[str, Any],
    previous: Dict[str, Any]
) -> Dict[str, Any]:
    """对比两个报告，找出差异。"""
    current_files = {f["path"]: f for f in current.get("files", [])}
    previous_files = {f["path"]: f for f in previous.get("files", [])}

    added = []
    removed = []
    changed = []
    grew = []

    for path, info in current_files.items():
        if path not in previous_files:
            added.append(info)
        else:
            prev_info = previous_files[path]
            if info["size_bytes"] != prev_info["size_bytes"]:
                changed.append({
                    "path": path,
                    "name": info["name"],
                    "old_size": prev_info["size_bytes"],
                    "new_size": info["size_bytes"],
                    "size_diff": info["size_bytes"] - prev_info["size_bytes"],
                })
                if info["size_bytes"] > prev_info["size_bytes"]:
                    grew.append(changed[-1])

    for path, info in previous_files.items():
        if path not in current_files:
            removed.append(info)

    current_total = current.get("summary", {}).get("total_size_bytes", 0)
    previous_total = previous.get("summary", {}).get("total_size_bytes", 0)

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "grew": grew,
        "total_size_diff": current_total - previous_total,
        "total_count_diff": len(current_files) - len(previous_files),
    }


def export_report_json(report_data: Dict[str, Any], output_path: Path) -> None:
    """导出报告为 JSON 格式。"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)


def export_report_csv(report_data: Dict[str, Any], output_path: Path) -> None:
    """导出报告为 CSV 格式。"""
    files = report_data.get("files", [])
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "序号", "文件名", "路径", "扩展名", "类型",
            "大小(字节)", "大小", "宽度", "高度", "分辨率",
            "标签", "创建日期", "目录"
        ])
        for idx, fe in enumerate(files, 1):
            writer.writerow([
                idx,
                fe["name"],
                fe["path"],
                fe["extension"],
                fe["type"],
                fe["size_bytes"],
                fe["size_human"],
                fe.get("width", ""),
                fe.get("height", ""),
                fe.get("resolution", ""),
                ','.join(fe.get("tags", [])),
                fe.get("created_at", ""),
                fe.get("directory", ""),
            ])


def cmd_report(
    directory: str,
    recursive: bool = True,
    by_extension: bool = True,
    by_size: bool = True,
    by_date: bool = True,
    by_tag: bool = True,
    by_directory: bool = True,
    top_n: int = 20,
    images_only: bool = False,
    brushes_only: bool = False,
    extension: Optional[str] = None,
    export_format: Optional[str] = None,
    compare: bool = False,
    report_dir: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    dry_run: bool = False,
):
    """输出素材占用空间详细报告。"""
    if config is None:
        config = {}

    if report_dir is None:
        report_dir = get_config_value(config, "report_dir", None)

    click.echo(f"\n[bold blue]目录:[/bold blue] {directory}")
    click.echo(f"[bold blue]递归子目录:[/bold blue] {'是' if recursive else '否'}")
    if images_only:
        click.echo(f"[bold blue]筛选:[/bold blue] 仅图片")
    elif brushes_only:
        click.echo(f"[bold blue]筛选:[/bold blue] 仅画笔")
    elif extension:
        click.echo(f"[bold blue]筛选:[/bold blue] 扩展名 {extension}")
    if export_format:
        click.echo(f"[bold blue]导出格式:[/bold blue] {export_format}")
    if compare:
        click.echo(f"[bold blue]对比模式:[/bold blue] 开启")
    click.echo()

    try:
        files = scan_files(
            directory,
            recursive=recursive,
            images_only=images_only,
            brushes_only=brushes_only,
            extension_filter=extension
        )
    except (FileNotFoundError, NotADirectoryError) as e:
        click.echo(f"[bold red]错误:[/bold red] {e}")
        return

    if not files:
        click.echo("[yellow]未找到任何支持的文件[/yellow]")
        return

    total_size = 0
    image_count = 0
    brush_count = 0
    image_size = 0
    brush_size = 0

    ext_stats: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "size": 0})
    size_stats: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "size": 0})
    date_stats: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "size": 0})
    tag_stats: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "size": 0})
    dir_stats: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "size": 0})
    largest_files: List[tuple] = []
    file_entries: List[Dict[str, Any]] = []

    for file_path in track(files, description="分析中..."):
        try:
            file_size = file_path.stat().st_size
            total_size += file_size

            if is_image_file(file_path):
                image_count += 1
                image_size += file_size
            else:
                brush_count += 1
                brush_size += file_size

            ext = file_path.suffix.lower()
            ext_stats[ext]["count"] += 1
            ext_stats[ext]["size"] += file_size

            info = get_image_info(file_path)
            file_entry = {
                "path": str(file_path.resolve()),
                "name": file_path.name,
                "extension": ext,
                "type": "image" if is_image_file(file_path) else "brush",
                "size_bytes": file_size,
                "size_human": human_readable_size(file_size),
                "tags": extract_tags(file_path.name),
                "directory": str(file_path.parent),
                "created_at": get_file_date(file_path).strftime("%Y-%m-%d %H:%M:%S"),
            }
            if info["dimensions"]:
                file_entry["width"] = info["dimensions"][0]
                file_entry["height"] = info["dimensions"][1]
                file_entry["resolution"] = f"{info['dimensions'][0]}x{info['dimensions'][1]}"
                category = parse_size_category(info["dimensions"][0], info["dimensions"][1])
                size_stats[category]["count"] += 1
                size_stats[category]["size"] += file_size
            file_entries.append(file_entry)

            file_date = get_file_date(file_path)
            date_key = file_date.strftime("%Y-%m")
            date_stats[date_key]["count"] += 1
            date_stats[date_key]["size"] += file_size

            tags = extract_tags(file_path.name)
            for tag in tags:
                tag_stats[tag]["count"] += 1
                tag_stats[tag]["size"] += file_size

            parent_dir = str(file_path.parent)
            dir_stats[parent_dir]["count"] += 1
            dir_stats[parent_dir]["size"] += file_size

            largest_files.append((file_size, file_path.name, str(file_path.parent)))

        except Exception:
            continue

    console.print(Panel(
        f"[bold]总览[/bold]\n\n"
        f"[cyan]文件总数:[/cyan] {len(files)} 个\n"
        f"  图片文件: {image_count} 个 ({human_readable_size(image_size)})\n"
        f"  画笔文件: {brush_count} 个 ({human_readable_size(brush_size)})\n\n"
        f"[bold]总占用空间: {human_readable_size(total_size)}[/bold]",
        title="空间占用概览",
        border_style="blue"
    ))

    if by_extension and ext_stats:
        table = Table(title="按扩展名统计", show_header=True, header_style="bold cyan")
        table.add_column("扩展名", style="cyan")
        table.add_column("数量", justify="right")
        table.add_column("总大小", justify="right")
        table.add_column("占比", justify="right")
        table.add_column("类型", style="green")

        for ext in sorted(ext_stats.keys(), key=lambda x: -ext_stats[x]["size"]):
            stat = ext_stats[ext]
            percentage = (stat["size"] / total_size * 100) if total_size > 0 else 0
            file_type = "图片" if ext in IMAGE_EXTENSIONS else "画笔"
            table.add_row(
                ext.upper(),
                str(stat["count"]),
                human_readable_size(stat["size"]),
                f"{percentage:.1f}%",
                file_type
            )
        console.print(table)

    if by_size and size_stats:
        table = Table(title="按图片尺寸分类统计", show_header=True, header_style="bold magenta")
        table.add_column("尺寸类别", style="magenta")
        table.add_column("数量", justify="right")
        table.add_column("总大小", justify="right")
        table.add_column("占比", justify="right")

        for category in sorted(size_stats.keys()):
            stat = size_stats[category]
            percentage = (stat["size"] / image_size * 100) if image_size > 0 else 0
            table.add_row(
                category,
                str(stat["count"]),
                human_readable_size(stat["size"]),
                f"{percentage:.1f}%"
            )
        console.print(table)

    if by_date and date_stats:
        table = Table(title="按月份统计", show_header=True, header_style="bold green")
        table.add_column("月份", style="green")
        table.add_column("数量", justify="right")
        table.add_column("总大小", justify="right")

        for date_key in sorted(date_stats.keys(), reverse=True):
            stat = date_stats[date_key]
            table.add_row(
                date_key,
                str(stat["count"]),
                human_readable_size(stat["size"])
            )
        console.print(table)

    if by_tag and tag_stats:
        table = Table(title=f"按标签统计 (Top {top_n})", show_header=True, header_style="bold yellow")
        table.add_column("标签", style="yellow")
        table.add_column("数量", justify="right")
        table.add_column("总大小", justify="right")

        sorted_tags = sorted(tag_stats.items(), key=lambda x: -x[1]["size"])[:top_n]
        for tag, stat in sorted_tags:
            table.add_row(
                f"[{tag}]",
                str(stat["count"]),
                human_readable_size(stat["size"])
            )
        console.print(table)

    if by_directory and dir_stats:
        table = Table(title=f"按目录统计 (Top {top_n})", show_header=True, header_style="bold blue")
        table.add_column("目录", style="blue")
        table.add_column("数量", justify="right")
        table.add_column("总大小", justify="right")

        sorted_dirs = sorted(dir_stats.items(), key=lambda x: -x[1]["size"])[:top_n]
        for dir_path, stat in sorted_dirs:
            table.add_row(
                dir_path,
                str(stat["count"]),
                human_readable_size(stat["size"])
            )
        console.print(table)

    if largest_files:
        largest_files.sort(reverse=True)
        table = Table(title=f"最大文件 (Top {top_n})", show_header=True, header_style="bold red")
        table.add_column("#", justify="right", style="dim")
        table.add_column("文件名", style="red")
        table.add_column("大小", justify="right")
        table.add_column("目录", style="dim")

        for idx, (size, name, parent) in enumerate(largest_files[:top_n], 1):
            table.add_row(
                str(idx),
                name,
                human_readable_size(size),
                parent
            )
        console.print(table)

    report_data = {
        "generated_at": datetime.now().isoformat(),
        "directory": str(Path(directory).resolve()),
        "summary": {
            "total_files": len(files),
            "total_size_bytes": total_size,
            "total_size_human": human_readable_size(total_size),
            "image_count": image_count,
            "image_size_bytes": image_size,
            "brush_count": brush_count,
            "brush_size_bytes": brush_size,
        },
        "files": file_entries,
        "stats": {
            "by_extension": dict(ext_stats),
            "by_size": dict(size_stats),
            "by_date": dict(date_stats),
            "by_tag": dict(tag_stats),
            "by_directory": dict(dir_stats),
        }
    }

    if compare:
        rpt_dir = get_report_dir(directory, report_dir)
        prev_report, prev_path = get_previous_report(rpt_dir)
        if prev_report and prev_path:
            diff = compare_reports(report_data, prev_report)
            prev_label = prev_path.name
            prev_time = prev_report.get("generated_at", "")
            if prev_time:
                try:
                    prev_time = datetime.fromisoformat(prev_time).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    prev_time = ""
            _display_comparison(diff, top_n, prev_label, prev_time)
        else:
            click.echo("\n[yellow]未找到历史报告，跳过对比[/yellow]")

    if export_format and not dry_run:
        rpt_dir = get_report_dir(directory, report_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{timestamp}.{export_format}"
        output_path = rpt_dir / filename

        if export_format == "json":
            export_report_json(report_data, output_path)
        elif export_format == "csv":
            export_report_csv(report_data, output_path)

        click.echo(f"\n[green]报告已导出:[/green] {output_path}")

    if dry_run:
        click.echo("\n[bold yellow]预览模式: 未执行任何修改[/bold yellow]")


def _display_comparison(diff: Dict[str, Any], top_n: int, prev_label: str = "", prev_time: str = ""):
    """显示对比结果。"""
    version_info = f"[bold]对比基准:[/bold] {prev_label}"
    if prev_time:
        version_info += f"  ({prev_time})"
    console.print(Panel(
        f"[bold]与上一次报告对比[/bold]\n\n"
        f"{version_info}\n\n"
        f"[cyan]文件数变化:[/cyan] {diff['total_count_diff']:+d}\n"
        f"[cyan]空间变化:[/cyan] {human_readable_size(abs(diff['total_size_diff']))} "
        f"({'增加' if diff['total_size_diff'] >= 0 else '减少'})\n"
        f"[green]新增文件:[/green] {len(diff['added'])} 个\n"
        f"[red]删除文件:[/red] {len(diff['removed'])} 个\n"
        f"[yellow]变动文件:[/yellow] {len(diff['changed'])} 个\n"
        f"[magenta]变大文件:[/magenta] {len(diff['grew'])} 个",
        title="历史对比",
        border_style="yellow"
    ))

    if diff["added"]:
        table = Table(title=f"新增文件 (Top {top_n})", show_header=True, header_style="bold green")
        table.add_column("#", justify="right", style="dim")
        table.add_column("文件名", style="green")
        table.add_column("大小", justify="right")
        for idx, f in enumerate(sorted(diff["added"], key=lambda x: -x["size_bytes"])[:top_n], 1):
            table.add_row(str(idx), f["name"], f["size_human"])
        console.print(table)

    if diff["removed"]:
        table = Table(title=f"删除文件 (Top {top_n})", show_header=True, header_style="bold red")
        table.add_column("#", justify="right", style="dim")
        table.add_column("文件名", style="red")
        table.add_column("大小", justify="right")
        for idx, f in enumerate(sorted(diff["removed"], key=lambda x: -x["size_bytes"])[:top_n], 1):
            table.add_row(str(idx), f["name"], f["size_human"])
        console.print(table)

    if diff["grew"]:
        table = Table(title=f"变大文件 (Top {top_n})", show_header=True, header_style="bold magenta")
        table.add_column("#", justify="right", style="dim")
        table.add_column("文件名", style="magenta")
        table.add_column("原大小", justify="right")
        table.add_column("新大小", justify="right")
        table.add_column("增量", justify="right")
        for idx, f in enumerate(sorted(diff["grew"], key=lambda x: -x["size_diff"])[:top_n], 1):
            table.add_row(
                str(idx),
                f["name"],
                human_readable_size(f["old_size"]),
                human_readable_size(f["new_size"]),
                f"+{human_readable_size(f['size_diff'])}"
            )
        console.print(table)
