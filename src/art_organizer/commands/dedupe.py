import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from pathlib import Path
from typing import List, Dict, Tuple
from send2trash import send2trash

from ..utils import (
    scan_files,
    find_duplicates,
    human_readable_size,
    get_file_date,
    is_image_file,
    calculate_hash,
)
from ..metadata import get_image_info

console = Console()

PREVIEW_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
SOURCE_EXTENSIONS = {'.psd', '.ai', '.tif', '.tiff', '.raw', '.heic', '.heif', '.svg'}


def check_missing_previews(files: List[Path]) -> List[Tuple[Path, str]]:
    """检查源文件是否缺失预览图。"""
    missing = []
    file_stems = {}
    for f in files:
        stem = f.stem.lower()
        if stem not in file_stems:
            file_stems[stem] = []
        file_stems[stem].append(f)

    for stem, stem_files in file_stems.items():
        has_source = any(f.suffix.lower() in SOURCE_EXTENSIONS for f in stem_files)
        has_preview = any(f.suffix.lower() in PREVIEW_EXTENSIONS for f in stem_files)
        if has_source and not has_preview:
            source_files = [f for f in stem_files if f.suffix.lower() in SOURCE_EXTENSIONS]
            for sf in source_files:
                missing.append((sf, f"缺少预览图 (建议: {stem}.png 或 {stem}.jpg)"))
    return missing


def cmd_dedupe(
    directory: str,
    recursive: bool = True,
    check_previews: bool = True,
    delete_duplicates: bool = False,
    keep: str = "newest",
    dry_run: bool = False,
):
    """查找重复文件并检查缺失预览图。"""
    click.echo(f"\n[bold blue]目录:[/bold blue] {directory}")
    click.echo(f"[bold blue]递归子目录:[/bold blue] {'是' if recursive else '否'}")
    click.echo(f"[bold blue]检查预览图:[/bold blue] {'是' if check_previews else '否'}")
    if delete_duplicates:
        click.echo(f"[bold blue]删除重复:[/bold blue] 是 (保留{keep}文件)")
    click.echo()

    try:
        files = scan_files(directory, recursive=recursive)
    except (FileNotFoundError, NotADirectoryError) as e:
        click.echo(f"[bold red]错误:[/bold red] {e}")
        return

    if not files:
        click.echo("[yellow]未找到任何支持的文件[/yellow]")
        return

    with click.progressbar(length=1, label="分析中") as bar:
        duplicates = find_duplicates(files)
        bar.update(1)

    if duplicates:
        total_duplicate_count = sum(len(paths) - 1 for paths in duplicates.values())
        total_wasted_space = 0

        table = Table(title="重复文件组", show_header=True, header_style="bold red")
        table.add_column("组", justify="right", style="dim")
        table.add_column("哈希值", style="red")
        table.add_column("文件路径", style="yellow")
        table.add_column("大小", justify="right")
        table.add_column("日期", style="cyan")
        table.add_column("状态", style="bold")

        for group_idx, (file_hash, paths) in enumerate(sorted(duplicates.items()), 1):
            sorted_paths = sorted(
                paths,
                key=lambda p: get_file_date(p),
                reverse=(keep == "newest")
            )
            file_size = paths[0].stat().st_size
            total_wasted_space += file_size * (len(paths) - 1)

            for i, path in enumerate(sorted_paths):
                status = "[green]保留[/green]" if i == 0 else "[red]重复[/red]"
                table.add_row(
                    str(group_idx) if i == 0 else "",
                    file_hash[:16] + "..." if i == 0 else "",
                    str(path),
                    human_readable_size(file_size),
                    get_file_date(path).strftime("%Y-%m-%d"),
                    status
                )
            table.add_row("", "", "", "", "", "")

        console.print(table)

        console.print(Panel(
            f"[bold red]发现 {len(duplicates)} 组重复文件[/bold red]\n"
            f"共 {total_duplicate_count} 个重复文件\n"
            f"[bold]可释放空间: {human_readable_size(total_wasted_space)}[/bold]",
            title="重复文件统计",
            border_style="red"
        ))

        if delete_duplicates:
            deleted_count = 0
            failed_count = 0
            freed_space = 0

            if dry_run:
                click.echo("\n[bold yellow]预览模式: 显示将要删除的文件[/bold yellow]")
                for file_hash, paths in duplicates.items():
                    sorted_paths = sorted(
                        paths,
                        key=lambda p: get_file_date(p),
                        reverse=(keep == "newest")
                    )
                    for path in sorted_paths[1:]:
                        click.echo(f"  [yellow]将删除:[/yellow] {path}")
            else:
                if not click.confirm(
                    f"\n确认删除 {total_duplicate_count} 个重复文件?\n"
                    f"(文件将被移动到回收站)",
                    default=False
                ):
                    click.echo("[yellow]已取消删除[/yellow]")
                else:
                    for file_hash, paths in duplicates.items():
                        sorted_paths = sorted(
                            paths,
                            key=lambda p: get_file_date(p),
                            reverse=(keep == "newest")
                        )
                        for path in sorted_paths[1:]:
                            try:
                                send2trash(str(path))
                                deleted_count += 1
                                freed_space += path.stat().st_size
                            except Exception as e:
                                failed_count += 1
                                click.echo(f"[red]删除失败 {path}: {e}[/red]")

                    console.print(Panel(
                        f"[bold green]已删除: {deleted_count} 个文件[/bold green]\n"
                        f"[bold]释放空间: {human_readable_size(freed_space)}[/bold]\n"
                        f"[bold red]失败: {failed_count}[/bold red]",
                        title="删除完成",
                        border_style="green" if failed_count == 0 else "red"
                    ))
    else:
        console.print(Panel(
            "[bold green]未发现重复文件[/bold green]",
            title="重复文件检查",
            border_style="green"
        ))

    if check_previews:
        missing_previews = check_missing_previews(files)
        if missing_previews:
            table = Table(title="缺失预览图的源文件", show_header=True, header_style="bold yellow")
            table.add_column("#", justify="right", style="dim")
            table.add_column("源文件", style="yellow")
            table.add_column("问题", style="red")

            for idx, (file_path, reason) in enumerate(missing_previews, 1):
                table.add_row(str(idx), str(file_path), reason)
            console.print(table)

            console.print(Panel(
                f"[bold yellow]发现 {len(missing_previews)} 个文件缺失预览图[/bold yellow]",
                title="预览图检查",
                border_style="yellow"
            ))
        else:
            console.print(Panel(
                "[bold green]所有源文件都有对应的预览图[/bold green]",
                title="预览图检查",
                border_style="green"
            ))

    if dry_run and not delete_duplicates:
        click.echo("\n[bold yellow]预览模式: 未执行任何修改[/bold yellow]")
