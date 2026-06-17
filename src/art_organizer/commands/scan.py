import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from pathlib import Path
from typing import List, Dict, Optional, Any

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
from ..cache import scan_with_cache, get_cache_info, clear_cache, clear_all_cache

console = Console()


def cmd_scan(
    directory: str,
    recursive: bool = True,
    show_details: bool = False,
    images_only: bool = False,
    brushes_only: bool = False,
    extension: Optional[str] = None,
    use_cache: bool = True,
    force_refresh: bool = False,
    dry_run: bool = False,
):
    """扫描目录中的图片和画笔文件，按尺寸和格式统计。"""
    click.echo(f"\n[bold blue]扫描目录:[/bold blue] {directory}")
    click.echo(f"[bold blue]递归子目录:[/bold blue] {'是' if recursive else '否'}")
    if images_only:
        click.echo(f"[bold blue]筛选:[/bold blue] 仅图片")
    elif brushes_only:
        click.echo(f"[bold blue]筛选:[/bold blue] 仅画笔")
    elif extension:
        click.echo(f"[bold blue]筛选:[/bold blue] 扩展名 {extension}")
    if use_cache:
        click.echo(f"[bold blue]使用缓存:[/bold blue] 是")
    click.echo()

    try:
        if use_cache:
            records, cache_stats = scan_with_cache(
                directory,
                recursive=recursive,
                force_refresh=force_refresh,
                images_only=images_only,
                brushes_only=brushes_only,
                extension_filter=extension,
            )
            files = [Path(r["path"]) for r in records]
            _display_cache_stats(cache_stats)
        else:
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


def cmd_cache_info(directory: str):
    """显示缓存信息。"""
    info = get_cache_info(directory)
    console.print(Panel(
        f"[bold]缓存目录:[/bold] {info['cache_dir']}\n"
        f"[bold]缓存文件:[/bold] {info['cache_file']}\n"
        f"[bold]是否存在:[/bold] {'是' if info['exists'] else '否'}\n"
        f"[bold]文件数:[/bold] {info['file_count']}\n"
        f"[bold]生成时间:[/bold] {info.get('generated_at', '-')}\n"
        f"[bold]缓存大小:[/bold] {human_readable_size(info['size_bytes']) if info['size_bytes'] > 0 else '-'}",
        title="缓存信息",
        border_style="cyan"
    ))


def cmd_clear_cache(directory: str, all: bool = False):
    """清除缓存。"""
    if all:
        import os
        cache_dir = os.path.join(directory, ".art-organizer-cache")
        count = clear_all_cache(cache_dir)
        if count > 0:
            click.echo(f"[bold green]已清除 {count} 个缓存文件[/bold green]")
        else:
            click.echo("[yellow]没有找到缓存文件[/yellow]")
    else:
        if clear_cache(directory):
            click.echo("[bold green]缓存已清除[/bold green]")
        else:
            click.echo("[yellow]没有找到该目录的缓存[/yellow]")


def _display_cache_stats(stats: Dict[str, Any]):
    """显示缓存统计信息。"""
    if stats["cached_files"] > 0 or stats["changed_files"] > 0 or stats["new_files"] > 0:
        table = Table(title="缓存使用情况", show_header=True, header_style="bold cyan")
        table.add_column("项目", style="cyan")
        table.add_column("数量", justify="right")

        table.add_row("总文件数", str(stats["total_files"]))
        table.add_row("[green]从缓存读取[/green]", str(stats["cached_files"]))
        table.add_row("[yellow]新增文件[/yellow]", str(stats["new_files"]))
        table.add_row("[magenta]变动文件[/magenta]", str(stats["changed_files"]))
        table.add_row("[red]已删除文件[/red]", str(stats["removed_files"]))
        console.print(table)
