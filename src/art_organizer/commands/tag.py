import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from pathlib import Path
from typing import List

from ..utils import (
    scan_files,
    add_tags_to_filename,
    safe_rename,
    extract_tags,
    human_readable_size,
    is_image_file,
)
from ..metadata import get_image_info

console = Console()


def cmd_tag(
    directory: str,
    tags: List[str],
    recursive: bool = True,
    remove: bool = False,
    filter_tag: str = None,
    dry_run: bool = False,
):
    """批量添加或移除主题标签到文件名。"""
    click.echo(f"\n[bold blue]目录:[/bold blue] {directory}")
    click.echo(f"[bold blue]操作:[/bold blue] {'移除标签' if remove else '添加标签'}")
    click.echo(f"[bold blue]标签:[/bold blue] {', '.join(tags)}")
    click.echo(f"[bold blue]递归子目录:[/bold blue] {'是' if recursive else '否'}")
    if filter_tag:
        click.echo(f"[bold blue]筛选标签:[/bold blue] {filter_tag}")
    click.echo()

    try:
        files = scan_files(directory, recursive=recursive)
    except (FileNotFoundError, NotADirectoryError) as e:
        click.echo(f"[bold red]错误:[/bold red] {e}")
        return

    if not files:
        click.echo("[yellow]未找到任何支持的文件[/yellow]")
        return

    if filter_tag:
        files = [f for f in files if filter_tag in extract_tags(f.name)]
        if not files:
            click.echo(f"[yellow]未找到包含标签 [{filter_tag}] 的文件[/yellow]")
            return

    changes = []
    for file_path in files:
        current_tags = extract_tags(file_path.name)
        if remove:
            new_tags = [t for t in current_tags if t not in tags]
            new_name = add_tags_to_filename(file_path.name, new_tags)
        else:
            new_name = add_tags_to_filename(file_path.name, tags)

        if new_name != file_path.name:
            changes.append((file_path, new_name, current_tags))

    if not changes:
        click.echo("[yellow]没有需要修改的文件[/yellow]")
        return

    table = Table(title="将要执行的变更", show_header=True, header_style="bold yellow")
    table.add_column("#", justify="right", style="dim")
    table.add_column("原文件名", style="red")
    table.add_column("→", style="dim")
    table.add_column("新文件名", style="green")
    table.add_column("当前标签", style="cyan")

    for idx, (old_path, new_name, current_tags) in enumerate(changes, 1):
        tags_str = ', '.join(f'[{t}]' for t in current_tags) if current_tags else '-'
        table.add_row(
            str(idx),
            old_path.name,
            "→",
            new_name,
            tags_str
        )
    console.print(table)

    console.print(Panel(
        f"[bold]计划修改 {len(changes)} 个文件[/bold]",
        title="预览",
        border_style="yellow"
    ))

    if dry_run:
        click.echo("\n[bold yellow]预览模式: 未执行任何修改[/bold yellow]")
        return

    if not click.confirm("\n确认执行以上修改?", default=False):
        click.echo("[yellow]已取消操作[/yellow]")
        return

    success_count = 0
    fail_count = 0
    results = []

    with click.progressbar(changes, label="处理中") as bar:
        for old_path, new_name, _ in bar:
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
        title="操作完成",
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
