import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from pathlib import Path
from typing import List, Optional
import re

from ..utils import (
    scan_files,
    safe_rename,
    extract_tags,
    get_file_date,
    format_date,
    human_readable_size,
    is_image_file,
)
from ..metadata import get_image_info

console = Console()

NAME_PATTERNS = {
    "date_tags_name": "{date}_{tags}_{name}",
    "date_name_tags": "{date}_{name}_{tags}",
    "tags_date_name": "{tags}_{date}_{name}",
    "tags_name_date": "{tags}_{name}_{date}",
    "name_date_tags": "{name}_{date}_{tags}",
    "name_tags_date": "{name}_{tags}_{date}",
    "date_tags": "{date}_{tags}",
    "tags_date": "{tags}_{date}",
    "date_name": "{date}_{name}",
    "name_date": "{name}_{date}",
}


def cmd_rename(
    directory: str,
    pattern: str = "date_tags_name",
    prefix: Optional[str] = None,
    recursive: bool = True,
    use_modified_date: bool = False,
    dry_run: bool = False,
):
    """根据标签和日期重命名文件。"""
    click.echo(f"\n[bold blue]目录:[/bold blue] {directory}")
    click.echo(f"[bold blue]命名模式:[/bold blue] {pattern}")
    if prefix:
        click.echo(f"[bold blue]前缀:[/bold blue] {prefix}")
    click.echo(f"[bold blue]日期来源:[/bold blue] {'修改时间' if use_modified_date else '创建时间'}")
    click.echo(f"[bold blue]递归子目录:[/bold blue] {'是' if recursive else '否'}")
    click.echo()

    if pattern not in NAME_PATTERNS:
        click.echo(f"[bold red]错误:[/bold red] 不支持的命名模式 '{pattern}'")
        click.echo(f"可用模式: {', '.join(NAME_PATTERNS.keys())}")
        return

    try:
        files = scan_files(directory, recursive=recursive)
    except (FileNotFoundError, NotADirectoryError) as e:
        click.echo(f"[bold red]错误:[/bold red] {e}")
        return

    if not files:
        click.echo("[yellow]未找到任何支持的文件[/yellow]")
        return

    changes = []
    for file_path in files:
        tags = extract_tags(file_path.name)
        name_without_tags = re.sub(r'\[[^\]]+\]', '', file_path.stem).strip('_-. ')
        ext = file_path.suffix

        file_date = get_file_date(file_path)
        if use_modified_date:
            from datetime import datetime
            file_date = datetime.fromtimestamp(file_path.stat().st_mtime)
        date_str = format_date(file_date)

        tags_str = '_'.join(f'[{t}]' for t in tags) if tags else ''
        name_str = name_without_tags if name_without_tags else 'unnamed'

        format_dict = {
            "date": date_str,
            "tags": tags_str,
            "name": name_str,
        }

        new_stem = NAME_PATTERNS[pattern].format(**format_dict)
        new_stem = re.sub(r'_+', '_', new_stem).strip('_')

        if prefix:
            new_stem = f"{prefix}_{new_stem}"

        new_name = f"{new_stem}{ext}"

        if new_name != file_path.name:
            changes.append((file_path, new_name, tags, date_str))

    if not changes:
        click.echo("[yellow]没有需要重命名的文件[/yellow]")
        return

    table = Table(title="将要执行的重命名", show_header=True, header_style="bold magenta")
    table.add_column("#", justify="right", style="dim")
    table.add_column("原文件名", style="red")
    table.add_column("→", style="dim")
    table.add_column("新文件名", style="green")
    table.add_column("日期", style="cyan")
    table.add_column("标签", style="yellow")

    for idx, (old_path, new_name, tags, date) in enumerate(changes, 1):
        tags_str = ', '.join(f'[{t}]' for t in tags) if tags else '-'
        table.add_row(
            str(idx),
            old_path.name,
            "→",
            new_name,
            date,
            tags_str
        )
    console.print(table)

    console.print(Panel(
        f"[bold]计划重命名 {len(changes)} 个文件[/bold]\n"
        f"模式: {pattern}",
        title="预览",
        border_style="magenta"
    ))

    if dry_run:
        click.echo("\n[bold yellow]预览模式: 未执行任何修改[/bold yellow]")
        return

    if not click.confirm("\n确认执行以上重命名?", default=False):
        click.echo("[yellow]已取消操作[/yellow]")
        return

    success_count = 0
    fail_count = 0
    results = []

    with click.progressbar(changes, label="重命名中") as bar:
        for old_path, new_name, _, _ in bar:
            new_path = old_path.parent / new_name
            ok, result = safe_rename(old_path, new_path, dry_run=False)
            if ok:
                success_count += 1
                results.append((old_path.name, new_name, "成功"))
            else:
                fail_count += 1
                results.append((old_path.name, new_name, f"失败: {result}"))

    console.print(Panel(
        f"[bold green]成功: {success_count}[/bold green]  |  "
        f"[bold red]失败: {fail_count}[/bold red]",
        title="重命名完成",
        border_style="green" if fail_count == 0 else "red"
    ))

    if fail_count > 0:
        table = Table(title="失败详情", show_header=True, header_style="bold red")
        table.add_column("原文件", style="red")
        table.add_column("目标名称", style="yellow")
        table.add_column("错误", style="red")
        for old_name, new_name, status in results:
            if status.startswith("失败"):
                table.add_row(old_name, new_name, status)
        console.print(table)
