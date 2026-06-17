import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import track
from pathlib import Path
from typing import Dict, List, Optional
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
)
from ..metadata import get_image_info

console = Console()


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
    dry_run: bool = False,
):
    """输出素材占用空间详细报告。"""
    click.echo(f"\n[bold blue]目录:[/bold blue] {directory}")
    click.echo(f"[bold blue]递归子目录:[/bold blue] {'是' if recursive else '否'}")
    if images_only:
        click.echo(f"[bold blue]筛选:[/bold blue] 仅图片")
    elif brushes_only:
        click.echo(f"[bold blue]筛选:[/bold blue] 仅画笔")
    elif extension:
        click.echo(f"[bold blue]筛选:[/bold blue] 扩展名 {extension}")
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

            if is_image_file(file_path):
                info = get_image_info(file_path)
                if info["dimensions"]:
                    category = parse_size_category(info["dimensions"][0], info["dimensions"][1])
                    size_stats[category]["count"] += 1
                    size_stats[category]["size"] += file_size

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

    if dry_run:
        click.echo("\n[bold yellow]预览模式: 未执行任何修改[/bold yellow]")
