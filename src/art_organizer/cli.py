import click
from rich.console import Console
from rich.panel import Panel
from . import __version__

from .commands.scan import cmd_scan
from .commands.tag import cmd_tag
from .commands.rename import cmd_rename
from .commands.dedupe import cmd_dedupe
from .commands.pack import cmd_pack
from .commands.report import cmd_report

console = Console()


@click.group(
    help="""
    插画师素材整理工具 - 管理你的本地素材文件夹

    支持 6 个核心命令：
      scan   - 扫描文件并按尺寸/格式统计
      tag    - 批量添加/移除主题标签
      rename - 根据标签和日期重命名文件
      dedupe - 查找重复文件，检查缺失预览图
      pack   - 生成素材包清单，按项目复制到交付目录
      report - 输出详细的空间占用报告
    """,
    context_settings={"help_option_names": ["-h", "--help"]}
)
@click.version_option(__version__, "-V", "--version")
def cli():
    """插画师素材整理工具。"""
    pass


@cli.command("scan")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option("--no-recursive", is_flag=True, default=False, help="不递归处理子目录")
@click.option("--details", "-d", is_flag=True, default=False, help="显示详细文件列表和标签统计")
@click.option("--images-only", is_flag=True, default=False, help="仅显示图片文件")
@click.option("--brushes-only", is_flag=True, default=False, help="仅显示画笔文件")
@click.option("--extension", "-e", default=None, help="仅显示指定扩展名的文件，如 .png 或 png")
@click.option("--dry-run", is_flag=True, default=False, help="预览模式，不执行任何修改")
def scan(directory, no_recursive, details, images_only, brushes_only, extension, dry_run):
    """扫描目录中的图片和画笔文件，按尺寸和格式统计。

    示例：
      art-organizer scan ./images --images-only
      art-organizer scan ./images --brushes-only
      art-organizer scan ./images --extension .png
    """
    cmd_scan(
        directory=directory,
        recursive=not no_recursive,
        show_details=details,
        images_only=images_only,
        brushes_only=brushes_only,
        extension=extension,
        dry_run=dry_run
    )


@cli.command("tag")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option("--add", "-a", "tags", multiple=True, required=False, help="要添加的标签，可多次指定")
@click.option("--remove", "-r", "remove_tags", multiple=True, required=False, help="要移除的标签，可多次指定")
@click.option("--no-recursive", is_flag=True, default=False, help="不递归处理子目录")
@click.option("--filter", "-f", "filter_tag", default=None, help="仅处理包含指定标签的文件")
@click.option("--dry-run", is_flag=True, default=False, help="预览模式，不执行任何修改")
def tag(directory, tags, remove_tags, no_recursive, filter_tag, dry_run):
    """批量添加或移除主题标签到文件名。

    示例：
      art-organizer tag ./images -a 风景 -a 插画
      art-organizer tag ./images -r 旧标签 --filter 项目A
      art-organizer tag ./images -a 草稿 --dry-run
    """
    if not tags and not remove_tags:
        raise click.UsageError("请使用 --add 或 --remove 指定要操作的标签")

    if remove_tags:
        cmd_tag(
            directory=directory,
            tags=list(remove_tags),
            recursive=not no_recursive,
            remove=True,
            filter_tag=filter_tag,
            dry_run=dry_run
        )
    else:
        cmd_tag(
            directory=directory,
            tags=list(tags),
            recursive=not no_recursive,
            remove=False,
            filter_tag=filter_tag,
            dry_run=dry_run
        )


@cli.command("rename")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option("--pattern", "-p", default="date_tags_name",
              type=click.Choice([
                  "date_tags_name", "date_name_tags", "tags_date_name",
                  "tags_name_date", "name_date_tags", "name_tags_date",
                  "date_tags", "tags_date", "date_name", "name_date"
              ]),
              help="命名模式，默认: date_tags_name")
@click.option("--prefix", default=None, help="添加文件名前缀")
@click.option("--no-recursive", is_flag=True, default=False, help="不递归处理子目录")
@click.option("--modified-date", is_flag=True, default=False, help="使用修改时间而非创建时间")
@click.option("--dry-run", is_flag=True, default=False, help="预览模式，不执行任何修改")
def rename(directory, pattern, prefix, no_recursive, modified_date, dry_run):
    """根据标签和日期重命名文件。

    可用命名模式：
      date_tags_name  - 20240115_[风景][插画]_文件名
      tags_date_name  - [风景][插画]_20240115_文件名
      name_date_tags  - 文件名_20240115_[风景][插画]
      date_tags       - 20240115_[风景][插画]
      ... (更多模式请查看帮助)

    示例：
      art-organizer rename ./images --pattern tags_date_name
      art-organizer rename ./images --prefix 项目A --dry-run
    """
    cmd_rename(
        directory=directory,
        pattern=pattern,
        prefix=prefix,
        recursive=not no_recursive,
        use_modified_date=modified_date,
        dry_run=dry_run
    )


@cli.command("dedupe")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option("--no-recursive", is_flag=True, default=False, help="不递归处理子目录")
@click.option("--no-preview-check", is_flag=True, default=False, help="不检查缺失的预览图")
@click.option("--delete", is_flag=True, default=False, help="删除重复文件（移动到回收站）")
@click.option("--keep", default="newest", type=click.Choice(["newest", "oldest"]),
              help="删除时保留的文件版本，默认: newest")
@click.option("--dry-run", is_flag=True, default=False, help="预览模式，不执行任何修改")
def dedupe(directory, no_recursive, no_preview_check, delete, keep, dry_run):
    """查找重复文件，检查缺失预览图。

    使用 SHA-256 哈希检测完全相同的文件。
    检查源文件（PSD、AI、TIFF 等）是否缺少对应的预览图（JPG、PNG 等）。

    示例：
      art-organizer dedupe ./images
      art-organizer dedupe ./images --delete --keep oldest
      art-organizer dedupe ./images --dry-run
    """
    cmd_dedupe(
        directory=directory,
        recursive=not no_recursive,
        check_previews=not no_preview_check,
        delete_duplicates=delete,
        keep=keep,
        dry_run=dry_run
    )


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
@click.option("--dry-run", is_flag=True, default=False, help="预览模式，不执行任何修改")
def pack(directory, output_dir, group_by, project_tag, manifest_format, manifest_only, no_recursive, dry_run):
    """生成素材包清单，按项目复制到交付目录。

    清单包含：文件名、路径、大小、标签、创建日期、分辨率等元数据。

    示例：
      art-organizer pack ./images -o ./delivery --manifest-only
      art-organizer pack ./images -o ./delivery --group-by directory
      art-organizer pack ./images -o ./delivery --project 客户A --format csv
      art-organizer pack ./images --group-by all --dry-run
    """
    cmd_pack(
        directory=directory,
        output_dir=output_dir,
        group_by=group_by,
        project_tag=project_tag,
        manifest_format=manifest_format,
        manifest_only=manifest_only,
        recursive=not no_recursive,
        dry_run=dry_run
    )


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
@click.option("--dry-run", is_flag=True, default=False, help="预览模式，不执行任何修改")
def report(directory, no_recursive, no_extension, no_size, no_date, no_tag, no_directory, top_n, images_only, brushes_only, extension, dry_run):
    """输出详细的素材空间占用报告。

    报告包含多个维度的统计信息，帮助你了解素材库的使用情况。

    示例：
      art-organizer report ./images
      art-organizer report ./images --top 10 --no-size
      art-organizer report ./images --images-only
      art-organizer report ./images --extension .jpg
    """
    cmd_report(
        directory=directory,
        recursive=not no_recursive,
        by_extension=not no_extension,
        by_size=not no_size,
        by_date=not no_date,
        by_tag=not no_tag,
        by_directory=not no_directory,
        top_n=top_n,
        images_only=images_only,
        brushes_only=brushes_only,
        extension=extension,
        dry_run=dry_run
    )


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
