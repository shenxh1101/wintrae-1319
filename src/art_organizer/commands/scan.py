import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from pathlib import Path
from typing import List, Dict

from ..utils import (
    scan_files,
    human_readable_size,
    is_image_file,
    is_brush_file,
    IMAGE_EXTENSIONS,
    BRUSH_EXTENSIONS,
    extract_tags,
    parse_size_category,
)
from ..metadata import get_image_info

console = Console()


def cmd_scan(
    directory: str,
    recursive: bool = True,
    show_details: bool = False,
    dry_run: bool = False,
):
    """扫描目录中的图片和画笔文件，按尺寸和格式统计。"""
    click.echo(f"\n[bold blue]扫描目录:[/bold blue] {directory}")
    click.echo(f"[bold blue]递归子目录:[/bold blue] {'是' if recursive else '否'}")
    click.echo()

    try:
        files = scan_files(directory, recursive=recursive)
    except (FileNotFoundError, NotADirectoryError) as e:
        click.echo(f"[bold red]错误:[/bold red] {e}")
        return

    if not files:
        click.echo("[yellow]未找到任何支持的文件[/yellow]")
        return

    image_files = [f for f in files if is_image_file(f)]
    brush_files = [f for f in files if is_brush_file(f)]

    total_size = sum(f.stat().st_size for f in files)

    format_stats: Dict[str, Dict] = {}
    size_category_stats: Dict[str, int] = {}

    for file_path in files:
        ext = file_path.suffix.lower()
        if ext not in format_stats:
            format_stats[ext] = {"count": 0, "size": 0}
        format_stats[ext]["count"] += 1
        format_stats[ext]["size"] += file_path.stat().st_size

        if is_image_file(file_path):
            info = get_image_info(file_path)
            if info["dimensions"]:
                category = parse_size_category(info["dimensions"][0], info["dimensions"][1])
                size_category_stats[category] = size_category_stats.get(category, 0) + 1

    console.print(Panel(
        f"[bold]共找到 {len(files)} 个文件[/bold]\n"
        f"  图片文件: {len(image_files)} 个\n"
        f"  画笔文件: {len(brush_files)} 个\n"
        f"[bold]总占用空间: {human_readable_size(total_size)}[/bold]",
        title="扫描概览",
        border_style="blue"
    ))

    if format_stats:
        table = Table(title="按格式统计", show_header=True, header_style="bold cyan")
        table.add_column("格式", style="cyan")
        table.add_column("数量", justify="right")
        table.add_column("占用空间", justify="right")
        table.add_column("类型", style="green")

        for ext in sorted(format_stats.keys()):
            stat = format_stats[ext]
            file_type = "图片" if ext in IMAGE_EXTENSIONS else "画笔"
            table.add_row(
                ext.upper(),
                str(stat["count"]),
                human_readable_size(stat["size"]),
                file_type
            )
        console.print(table)

    if size_category_stats:
        table = Table(title="按尺寸分类统计", show_header=True, header_style="bold magenta")
        table.add_column("尺寸类别", style="magenta")
        table.add_column("数量", justify="right")

        for category in sorted(size_category_stats.keys()):
            table.add_row(category, str(size_category_stats[category]))
        console.print(table)

    if show_details:
        all_tags = []
        for file_path in files:
            tags = extract_tags(file_path.name)
            all_tags.extend(tags)

        if all_tags:
            tag_stats: Dict[str, int] = {}
            for tag in all_tags:
                tag_stats[tag] = tag_stats.get(tag, 0) + 1

            table = Table(title="标签统计", show_header=True, header_style="bold yellow")
            table.add_column("标签", style="yellow")
            table.add_column("出现次数", justify="right")

            for tag, count in sorted(tag_stats.items(), key=lambda x: -x[1])[:20]:
                table.add_row(f"[{tag}]", str(count))
            console.print(table)

        table = Table(title="文件列表", show_header=True, header_style="bold green")
        table.add_column("#", justify="right", style="dim")
        table.add_column("文件名", style="green")
        table.add_column("尺寸", justify="right")
        table.add_column("分辨率", justify="center")
        table.add_column("路径", style="dim")

        for idx, file_path in enumerate(files, 1):
            info = get_image_info(file_path)
            dims = f"{info['dimensions'][0]}x{info['dimensions'][1]}" if info["dimensions"] else "-"
            table.add_row(
                str(idx),
                file_path.name,
                human_readable_size(info["size_bytes"]),
                dims,
                str(file_path.parent)
            )
        console.print(table)

    if dry_run:
        click.echo("\n[bold yellow]预览模式: 未执行任何修改[/bold yellow]")
