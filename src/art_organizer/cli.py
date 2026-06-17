import click
from rich.console import Console
from rich.panel import Panel
from . import __version__

from .config import load_config, generate_default_config, save_config, find_config_file
from .commands.scan import cmd_scan, cmd_cache_info, cmd_clear_cache
from .commands.tag import cmd_tag
from .commands.rename import cmd_rename
from .commands.dedupe import cmd_dedupe
from .commands.pack import cmd_pack
from .commands.report import cmd_report
from .commands.undo import cmd_undo, cmd_history, cmd_clear_history

console = Console()


def get_config(ctx: click.Context, directory: str):
    """从上下文中获取配置，如果没有则加载。"""
    if "config" not in ctx.obj:
        ctx.obj["config"] = load_config(directory)
    return ctx.obj["config"]


@click.group(
    help="""
    插画师素材整理工具 - 管理你的本地素材文件夹

    核心命令：
      scan     - 扫描文件并按尺寸/格式统计（支持缓存加速）
      tag      - 批量添加/移除主题标签（支持操作回滚）
      rename   - 根据标签和日期重命名文件（支持操作回滚）
      dedupe   - 查找重复文件，检查缺失预览图
      pack     - 生成素材包清单，按项目复制到交付目录（支持模板和校验）
      report   - 输出详细的空间占用报告（支持导出和历史对比）

    管理命令：
      undo     - 撤回最近一次 tag/rename 操作
      history  - 查看操作历史记录
      config   - 生成/查看配置文件
      cache    - 管理扫描缓存

    所有修改操作都支持 --dry-run 预览模式。
    """,
    context_settings={"help_option_names": ["-h", "--help"]}
)
@click.version_option(__version__, "-V", "--version")
@click.pass_context
def cli(ctx):
    """插画师素材整理工具。"""
    ctx.ensure_object(dict)
    ctx.obj["config"] = {}


# ==================== scan 命令 ====================
@cli.command("scan")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option("--no-recursive", is_flag=True, default=False, help="不递归处理子目录")
@click.option("--details", "-d", is_flag=True, default=False, help="显示详细文件列表和标签统计")
@click.option("--images-only", is_flag=True, default=False, help="仅显示图片文件")
@click.option("--brushes-only", is_flag=True, default=False, help="仅显示画笔文件")
@click.option("--extension", "-e", default=None, help="仅显示指定扩展名的文件，如 .png 或 png")
@click.option("--no-cache", is_flag=True, default=False, help="不使用缓存，强制重新扫描")
@click.option("--refresh", is_flag=True, default=False, help="强制刷新缓存")
@click.option("--dry-run", is_flag=True, default=False, help="预览模式，不执行任何修改")
@click.pass_context
def scan(ctx, directory, no_recursive, details, images_only, brushes_only, extension, no_cache, refresh, dry_run):
    """扫描目录中的图片和画笔文件，按尺寸和格式统计。

    示例：
      art-organizer scan ./images --images-only
      art-organizer scan ./images --brushes-only
      art-organizer scan ./images --extension .png
      art-organizer scan ./images --refresh
      art-organizer scan ./images --no-cache
    """
    config = get_config(ctx, directory)
    recursive = not no_recursive if no_recursive else config.get("recursive", True)

    cmd_scan(
        directory=directory,
        recursive=recursive,
        show_details=details,
        images_only=images_only,
        brushes_only=brushes_only,
        extension=extension,
        use_cache=not no_cache,
        force_refresh=refresh,
        dry_run=dry_run
    )


# ==================== cache 子命令组 ====================
@cli.group("cache", help="管理扫描缓存")
def cache():
    """缓存管理命令。"""
    pass


@cache.command("info")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True))
def cache_info(directory):
    """显示指定目录的缓存信息。"""
    cmd_cache_info(directory)


@cache.command("clear")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option("--all", is_flag=True, default=False, help="清除所有缓存")
def cache_clear(directory, all):
    """清除指定目录的缓存。

    示例：
      art-organizer cache clear ./images
      art-organizer cache clear ./images --all
    """
    cmd_clear_cache(directory, all=all)


# ==================== tag 命令 ====================
@cli.command("tag")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option("--add", "-a", "tags", multiple=True, required=False, help="要添加的标签，可多次指定")
@click.option("--remove", "-r", "remove_tags", multiple=True, required=False, help="要移除的标签，可多次指定")
@click.option("--no-recursive", is_flag=True, default=False, help="不递归处理子目录")
@click.option("--filter", "-f", "filter_tag", default=None, help="仅处理包含指定标签的文件")
@click.option("--no-history", is_flag=True, default=False, help="不保存操作历史")
@click.option("--dry-run", is_flag=True, default=False, help="预览模式，不执行任何修改")
@click.pass_context
def tag(ctx, directory, tags, remove_tags, no_recursive, filter_tag, no_history, dry_run):
    """批量添加或移除主题标签到文件名（支持回滚）。

    操作后会自动保存历史记录，使用 'art-organizer undo' 可撤回。

    示例：
      art-organizer tag ./images -a 风景 -a 插画
      art-organizer tag ./images -r 旧标签 --filter 项目A
      art-organizer tag ./images -a 草稿 --dry-run
    """
    if not tags and not remove_tags:
        raise click.UsageError("请使用 --add 或 --remove 指定要操作的标签")

    config = get_config(ctx, directory)
    recursive = not no_recursive if no_recursive else config.get("recursive", True)
    history_dir = config.get("history_dir", None)

    if remove_tags:
        cmd_tag(
            directory=directory,
            tags=list(remove_tags),
            recursive=recursive,
            remove=True,
            filter_tag=filter_tag,
            dry_run=dry_run,
            save_history=not no_history,
            history_dir=history_dir
        )
    else:
        cmd_tag(
            directory=directory,
            tags=list(tags),
            recursive=recursive,
            remove=False,
            filter_tag=filter_tag,
            dry_run=dry_run,
            save_history=not no_history,
            history_dir=history_dir
        )


# ==================== rename 命令 ====================
@cli.command("rename")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option("--pattern", "-p", default=None,
              type=click.Choice([
                  "date_tags_name", "date_name_tags", "tags_date_name",
                  "tags_name_date", "name_date_tags", "name_tags_date",
                  "date_tags", "tags_date", "date_name", "name_date"
              ]),
              help="命名模式")
@click.option("--prefix", default=None, help="添加文件名前缀")
@click.option("--no-recursive", is_flag=True, default=False, help="不递归处理子目录")
@click.option("--modified-date", is_flag=True, default=False, help="使用修改时间而非创建时间")
@click.option("--no-history", is_flag=True, default=False, help="不保存操作历史")
@click.option("--dry-run", is_flag=True, default=False, help="预览模式，不执行任何修改")
@click.pass_context
def rename(ctx, directory, pattern, prefix, no_recursive, modified_date, no_history, dry_run):
    """根据标签和日期重命名文件（支持回滚）。

    操作后会自动保存历史记录，使用 'art-organizer undo' 可撤回。

    可用命名模式：
      date_tags_name  - 20240115_[风景][插画]_文件名
      tags_date_name  - [风景][插画]_20240115_文件名
      name_date_tags  - 文件名_20240115_[风景][插画]
      ... (更多模式请查看帮助)

    示例：
      art-organizer rename ./images --pattern tags_date_name
      art-organizer rename ./images --prefix 项目A --dry-run
    """
    config = get_config(ctx, directory)
    if pattern is None:
        pattern = config.get("naming_pattern", "date_tags_name")
    recursive = not no_recursive if no_recursive else config.get("recursive", True)
    history_dir = config.get("history_dir", None)

    cmd_rename(
        directory=directory,
        pattern=pattern,
        prefix=prefix,
        recursive=recursive,
        use_modified_date=modified_date,
        dry_run=dry_run,
        save_history=not no_history,
        history_dir=history_dir
    )


# ==================== undo 命令 ====================
@cli.command("undo")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option("-n", default=1, type=int, help="撤回最近第 n 次操作，默认: 1")
@click.option("--dry-run", is_flag=True, default=False, help="预览模式，不执行任何修改")
@click.pass_context
def undo(ctx, directory, n, dry_run):
    """撤回最近一次 tag/rename 操作。

    示例：
      art-organizer undo ./images
      art-organizer undo ./images -n 2
      art-organizer undo ./images --dry-run
    """
    config = get_config(ctx, directory)
    history_dir = config.get("history_dir", None)

    cmd_undo(
        directory=directory,
        n=n,
        dry_run=dry_run,
        history_dir=history_dir
    )


# ==================== history 命令 ====================
@cli.command("history")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option("--limit", "-l", default=10, type=int, help="显示最近的记录数，默认: 10")
@click.pass_context
def history(ctx, directory, limit):
    """查看操作历史记录。

    示例：
      art-organizer history ./images
      art-organizer history ./images --limit 20
    """
    config = get_config(ctx, directory)
    history_dir = config.get("history_dir", None)

    cmd_history(
        directory=directory,
        limit=limit,
        history_dir=history_dir
    )


@cli.command("clear-history")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option("--keep", default=0, type=int, help="保留最近的记录数，默认: 0（全部删除）")
@click.pass_context
def clear_history_cmd(ctx, directory, keep):
    """清理操作历史记录。

    示例：
      art-organizer clear-history ./images
      art-organizer clear-history ./images --keep 5
    """
    config = get_config(ctx, directory)
    history_dir = config.get("history_dir", None)

    cmd_clear_history(
        directory=directory,
        keep=keep,
        history_dir=history_dir
    )


# ==================== dedupe 命令 ====================
@cli.command("dedupe")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option("--no-recursive", is_flag=True, default=False, help="不递归处理子目录")
@click.option("--no-preview-check", is_flag=True, default=False, help="不检查缺失的预览图")
@click.option("--delete", is_flag=True, default=False, help="删除重复文件（移动到回收站）")
@click.option("--keep", default="newest", type=click.Choice(["newest", "oldest"]),
              help="删除时保留的文件版本，默认: newest")
@click.option("--dry-run", is_flag=True, default=False, help="预览模式，不执行任何修改")
@click.pass_context
def dedupe(ctx, directory, no_recursive, no_preview_check, delete, keep, dry_run):
    """查找重复文件，检查缺失预览图。

    使用 SHA-256 哈希检测完全相同的文件。
    检查源文件（PSD、AI、TIFF 等）是否缺少对应的预览图（JPG、PNG 等）。

    示例：
      art-organizer dedupe ./images
      art-organizer dedupe ./images --delete --keep oldest
      art-organizer dedupe ./images --dry-run
    """
    config = get_config(ctx, directory)
    recursive = not no_recursive if no_recursive else config.get("recursive", True)

    cmd_dedupe(
        directory=directory,
        recursive=recursive,
        check_previews=not no_preview_check,
        delete_duplicates=delete,
        keep=keep,
        dry_run=dry_run
    )


# ==================== pack 命令 ====================
@cli.command("pack")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option("--output-dir", "-o", type=click.Path(file_okay=False, dir_okay=True),
              help="输出目录，用于存放清单和/或复制的文件")
@click.option("--group-by", default="tag", type=click.Choice(["tag", "directory", "all"]),
              help="分组方式：按标签/目录/全部，默认: tag")
@click.option("--project", "project_tag", default=None, help="仅处理包含指定项目标签的文件")
@click.option("--format", "manifest_format", default="json", type=click.Choice(["json", "csv"]),
              help="清单文件格式，默认: json")
@click.option("--manifest-only", is_flag=True, default=False, help="仅生成清单，不复制文件")
@click.option("--no-recursive", is_flag=True, default=False, help="不递归处理子目录")
@click.option("--template", "delivery_template", default=None,
              help="交付目录模板，如 '{client}/{project}/{type}/{tag}'")
@click.option("--project-name", default=None, help="项目名，用于模板变量")
@click.option("--client", default=None, help="客户名，用于模板变量")
@click.option("--no-checksum", is_flag=True, default=False, help="不生成文件校验值")
@click.option("--dry-run", is_flag=True, default=False, help="预览模式，不执行任何修改")
@click.pass_context
def pack(ctx, directory, output_dir, group_by, project_tag, manifest_format, manifest_only,
         no_recursive, delivery_template, project_name, client, no_checksum, dry_run):
    """生成素材包清单，按项目复制到交付目录（支持模板和校验）。

    交付模板可用变量：{project}, {client}, {type}, {tag}, {tags}, {date}, {year}, {month}

    清单包含：文件名、路径、大小、标签、创建日期、分辨率、SHA-256 校验值等。

    示例：
      art-organizer pack ./images -o ./delivery --manifest-only
      art-organizer pack ./images -o ./delivery --group-by directory
      art-organizer pack ./images -o ./delivery --template '{client}/{project}/{type}/{tag}' --client 某公司 --project-name 插画项目
      art-organizer pack ./images -o ./delivery --no-checksum
      art-organizer pack ./images --group-by all --dry-run
    """
    config = get_config(ctx, directory)
    recursive = not no_recursive if no_recursive else config.get("recursive", True)

    cmd_pack(
        directory=directory,
        output_dir=output_dir,
        group_by=group_by,
        project_tag=project_tag,
        manifest_format=manifest_format,
        manifest_only=manifest_only,
        recursive=recursive,
        delivery_template=delivery_template,
        project=project_name,
        client=client,
        no_checksum=no_checksum,
        config=config,
        dry_run=dry_run
    )


# ==================== report 命令 ====================
@cli.command("report")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option("--no-recursive", is_flag=True, default=False, help="不递归处理子目录")
@click.option("--no-extension", is_flag=True, default=False, help="不显示按扩展名统计")
@click.option("--no-size", is_flag=True, default=False, help="不显示按尺寸统计")
@click.option("--no-date", is_flag=True, default=False, help="不显示按日期统计")
@click.option("--no-tag", is_flag=True, default=False, help="不显示按标签统计")
@click.option("--no-directory", is_flag=True, default=False, help="不显示按目录统计")
@click.option("--top", "top_n", default=20, type=int, help="Top N 统计数量，默认: 20")
@click.option("--images-only", is_flag=True, default=False, help="仅统计图片文件")
@click.option("--brushes-only", is_flag=True, default=False, help="仅统计画笔文件")
@click.option("--extension", "-e", default=None, help="仅统计指定扩展名的文件，如 .png 或 png")
@click.option("--export", "export_format", default=None, type=click.Choice(["json", "csv"]),
              help="导出报告为指定格式")
@click.option("--compare", is_flag=True, default=False, help="与上一次报告对比，显示变化")
@click.option("--report-dir", default=None, help="报告存储目录")
@click.option("--dry-run", is_flag=True, default=False, help="预览模式，不执行任何修改")
@click.pass_context
def report(ctx, directory, no_recursive, no_extension, no_size, no_date, no_tag, no_directory,
           top_n, images_only, brushes_only, extension, export_format, compare, report_dir, dry_run):
    """输出详细的素材空间占用报告（支持导出和历史对比）。

    报告包含多个维度的统计信息，帮助你了解素材库的使用情况。
    支持导出为 JSON/CSV 格式，并可与上一次报告对比。

    示例：
      art-organizer report ./images
      art-organizer report ./images --top 10 --no-size
      art-organizer report ./images --images-only
      art-organizer report ./images --export json
      art-organizer report ./images --compare
      art-organizer report ./images --export csv --compare
    """
    config = get_config(ctx, directory)
    recursive = not no_recursive if no_recursive else config.get("recursive", True)

    cmd_report(
        directory=directory,
        recursive=recursive,
        by_extension=not no_extension,
        by_size=not no_size,
        by_date=not no_date,
        by_tag=not no_tag,
        by_directory=not no_directory,
        top_n=top_n,
        images_only=images_only,
        brushes_only=brushes_only,
        extension=extension,
        export_format=export_format,
        compare=compare,
        report_dir=report_dir,
        config=config,
        dry_run=dry_run
    )


# ==================== config 命令 ====================
@cli.group("config", help="管理配置文件")
def config_cmd():
    """配置管理命令。"""
    pass


@config_cmd.command("init")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True), default=".")
def config_init(directory):
    """在指定目录生成默认配置文件。

    示例：
      art-organizer config init
      art-organizer config init ./my-project
    """
    config_content = generate_default_config()
    config_path = save_config({"recursive": True}, directory)
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(config_content)
    click.echo(f"[green]已生成配置文件:[/green] {config_path}")
    click.echo("[dim]请编辑配置文件设置常用参数[/dim]")


@config_cmd.command("show")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True), default=".")
def config_show(directory):
    """显示当前生效的配置。

    示例：
      art-organizer config show
      art-organizer config show ./my-project
    """
    config = load_config(directory)
    config_file = config.pop("_config_file", None)

    if config_file:
        click.echo(f"[bold]配置文件:[/bold] {config_file}")
    else:
        click.echo("[yellow]未找到配置文件，使用默认配置[/yellow]")
    click.echo()

    for key, value in sorted(config.items()):
        if isinstance(value, dict):
            click.echo(f"[bold]{key}:[/bold]")
            for k, v in sorted(value.items()):
                click.echo(f"  {k}: {v}")
        else:
            click.echo(f"[bold]{key}:[/bold] {value}")


@config_cmd.command("path")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True), default=".")
def config_path(directory):
    """显示配置文件路径。

    示例：
      art-organizer config path
    """
    config_file = find_config_file(directory)
    if config_file:
        click.echo(str(config_file))
    else:
        click.echo("[yellow]未找到配置文件[/yellow]")


# ==================== 主入口 ====================
def main():
    """程序入口。"""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\n[yellow]操作已取消[/yellow]")
    except Exception as e:
        console.print(Panel(
            f"[bold red]错误:[/bold red] {e}",
            title="程序异常",
            border_style="red"
        ))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
