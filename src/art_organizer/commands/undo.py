import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..history import (
    rollback_latest,
    list_history,
    clear_history,
    load_history,
)

console = Console()


def cmd_undo(
    directory: str,
    n: int = 1,
    dry_run: bool = False,
    history_dir: Optional[str] = None,
):
    """撤回最近的 tag/rename 操作。"""
    click.echo(f"\n[bold blue]目录:[/bold blue] {directory}")
    click.echo(f"[bold blue]撤回最近第 {n} 次操作[/bold blue]")
    click.echo()

    history_data, success_count, fail_count, results = rollback_latest(
        directory, history_dir=history_dir, n=n, dry_run=dry_run
    )

    if not history_data:
        click.echo("[yellow]没有找到可撤回的操作记录[/yellow]")
        return

    click.echo(f"[bold]撤回操作:[/bold] {history_data.get('timestamp_pretty')}")
    click.echo(f"[bold]操作类型:[/bold] {history_data.get('operation_type')}")
    click.echo(f"[bold]描述:[/bold] {history_data.get('description', '-')}")
    click.echo()

    if results:
        table = Table(title=f"{'预览撤回' if dry_run else '撤回结果'}", show_header=True, header_style="bold yellow")
        table.add_column("#", justify="right", style="dim")
        table.add_column("当前文件名", style="red")
        table.add_column("→", style="dim")
        table.add_column("恢复为", style="green")
        table.add_column("状态", style="cyan")

        for idx, result in enumerate(results, 1):
            status = "[green]成功[/green]" if result["success"] else f"[red]{result.get('error', '失败')}[/red]"
            table.add_row(
                str(idx),
                result["old_name"],
                "→",
                result["target_name"],
                status
            )
        console.print(table)

    console.print(Panel(
        f"[bold green]成功: {success_count}[/bold green]  |  "
        f"[bold red]失败: {fail_count}[/bold red]",
        title="撤回完成" if not dry_run else "撤回预览",
        border_style="green" if fail_count == 0 else "red"
    ))

    if dry_run:
        click.echo("\n[bold yellow]预览模式: 未执行任何修改[/bold yellow]")


def cmd_history(
    directory: str,
    limit: int = 10,
    history_dir: Optional[str] = None,
):
    """查看操作历史记录。"""
    click.echo(f"\n[bold blue]目录:[/bold blue] {directory}")
    click.echo(f"[bold blue]显示最近 {limit} 条记录[/bold blue]")
    click.echo()

    histories = list_history(directory, history_dir=history_dir, limit=limit)

    if not histories:
        click.echo("[yellow]没有找到操作历史记录[/yellow]")
        return

    table = Table(title="操作历史记录", show_header=True, header_style="bold cyan")
    table.add_column("#", justify="right", style="dim")
    table.add_column("时间", style="cyan")
    table.add_column("类型", style="green")
    table.add_column("描述", style="yellow")
    table.add_column("变更数", justify="right")

    for idx, hist in enumerate(histories, 1):
        op_type = hist["operation_type"]
        type_style = "green" if op_type == "tag" else "magenta" if op_type == "rename" else "cyan"
        table.add_row(
            str(idx),
            hist["timestamp_pretty"],
            f"[{type_style}]{op_type}[/{type_style}]",
            hist.get("description", "-"),
            str(hist["total_changes"])
        )
    console.print(table)

    click.echo("\n[dim]使用 'art-organizer undo -n <序号>' 撤回指定操作[/dim]")


def cmd_clear_history(
    directory: str,
    keep: int = 0,
    history_dir: Optional[str] = None,
):
    """清理操作历史记录。"""
    if keep > 0:
        click.echo(f"[bold yellow]保留最近 {keep} 条记录[/bold yellow]")
    else:
        click.echo("[bold red]将删除所有历史记录！[/bold red]")

    if not click.confirm("\n确认清理历史记录?", default=False):
        click.echo("[yellow]已取消[/yellow]")
        return

    count = clear_history(directory, history_dir=history_dir, keep=keep)
    click.echo(f"[bold green]已删除 {count} 条历史记录[/bold green]")
