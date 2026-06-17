import click
import json
import csv
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from pathlib import Path
from typing import List, Dict, Optional

from ..utils import (
    scan_files,
    safe_copy,
    human_readable_size,
    extract_tags,
    get_file_date,
    is_image_file,
    is_brush_file,
)
from ..metadata import get_image_info

console = Console()


def group_by_project(files: List[Path], group_by: str) -> Dict[str, List[Path]]:
    """按项目标签或目录分组文件。"""
    groups: Dict[str, List[Path]] = {}

    if group_by == "tag":
        for file_path in files:
            tags = extract_tags(file_path.name)
            if tags:
                for tag in tags:
                    if tag not in groups:
                        groups[tag] = []
                    groups[tag].append(file_path)
            else:
                if "未分类" not in groups:
                    groups["未分类"] = []
                groups["未分类"].append(file_path)
    elif group_by == "directory":
        for file_path in files:
            parent_name = file_path.parent.name
            if parent_name not in groups:
                groups[parent_name] = []
            groups[parent_name].append(file_path)
    else:
        groups["全部"] = files

    return groups


def generate_manifest(
    files: List[Path],
    output_path: Path,
    source_directory: str,
    group_name: str,
    delivery_path: Optional[Path] = None,
    format: str = "json",
):
    """生成素材包清单文件。"""
    image_count = sum(1 for f in files if is_image_file(f))
    brush_count = sum(1 for f in files if is_brush_file(f))
    all_tags = []
    for f in files:
        all_tags.extend(extract_tags(f.name))
    unique_tags = sorted(list(set(all_tags)))

    manifest = {
        "manifest_info": {
            "generated_at": datetime.now().isoformat(),
            "group_name": group_name,
            "source_directory": str(Path(source_directory).resolve()),
            "delivery_directory": str(delivery_path.resolve()) if delivery_path else None,
            "manifest_file": str(output_path.resolve()),
        },
        "summary": {
            "total_files": len(files),
            "total_size_bytes": sum(f.stat().st_size for f in files),
            "total_size_human": human_readable_size(sum(f.stat().st_size for f in files)),
            "image_files": image_count,
            "brush_files": brush_count,
            "unique_tags": unique_tags,
            "tags_count": len(unique_tags),
        },
        "delivery_structure": {
            "root": group_name,
            "files": [f.name for f in sorted(files)],
        },
        "files": []
    }

    for file_path in sorted(files):
        info = get_image_info(file_path)
        tags = extract_tags(file_path.name)
        file_entry = {
            "filename": file_path.name,
            "source_path": str(file_path.resolve()),
            "source_directory": str(file_path.parent.resolve()),
            "delivery_path": str(delivery_path / file_path.name) if delivery_path else None,
            "size_bytes": file_path.stat().st_size,
            "size_human": human_readable_size(file_path.stat().st_size),
            "extension": info["extension"],
            "type": "image" if info["is_image"] else "brush",
            "tags": tags,
            "tags_formatted": ' '.join(f'[{t}]' for t in tags),
            "created_at": get_file_date(file_path).isoformat(),
            "created_at_formatted": get_file_date(file_path).strftime("%Y-%m-%d %H:%M:%S"),
        }
        if info["dimensions"]:
            file_entry["width"] = info["dimensions"][0]
            file_entry["height"] = info["dimensions"][1]
            file_entry["resolution"] = f"{info['dimensions'][0]}x{info['dimensions'][1]}"
            file_entry["aspect_ratio"] = round(info['dimensions'][0] / info['dimensions'][1], 2)
        if info["image_format"]:
            file_entry["image_format"] = info["image_format"]
        if info["mode"]:
            file_entry["color_mode"] = info["mode"]
        manifest["files"].append(file_entry)

    if format == "json":
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
    elif format == "csv":
        with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "序号", "文件名", "来源路径", "来源目录", "交付路径",
                "大小(字节)", "大小", "扩展名", "类型",
                "标签", "标签格式", "创建日期",
                "宽度", "高度", "分辨率", "宽高比", "图片格式", "色彩模式"
            ])
            for idx, fe in enumerate(manifest["files"], 1):
                writer.writerow([
                    idx,
                    fe["filename"],
                    fe["source_path"],
                    fe["source_directory"],
                    fe.get("delivery_path", ""),
                    fe["size_bytes"],
                    fe["size_human"],
                    fe["extension"],
                    fe["type"],
                    ','.join(fe["tags"]),
                    fe["tags_formatted"],
                    fe["created_at_formatted"],
                    fe.get("width", ""),
                    fe.get("height", ""),
                    fe.get("resolution", ""),
                    fe.get("aspect_ratio", ""),
                    fe.get("image_format", ""),
                    fe.get("color_mode", ""),
                ])

    return manifest


def generate_summary_manifest(
    all_groups: Dict[str, List[Path]],
    output_path: Path,
    source_directory: str,
    format: str = "json",
):
    """生成总的素材包汇总清单。"""
    total_files = sum(len(files) for files in all_groups.values())
    total_size = sum(f.stat().st_size for files in all_groups.values() for f in files)
    all_tags = []
    for files in all_groups.values():
        for f in files:
            all_tags.extend(extract_tags(f.name))
    unique_tags = sorted(list(set(all_tags)))

    summary = {
        "manifest_info": {
            "generated_at": datetime.now().isoformat(),
            "source_directory": str(Path(source_directory).resolve()),
            "summary_file": str(output_path.resolve()),
        },
        "overview": {
            "total_groups": len(all_groups),
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_human": human_readable_size(total_size),
            "unique_tags": unique_tags,
            "tags_count": len(unique_tags),
        },
        "groups": [],
    }

    for group_name in sorted(all_groups.keys()):
        group_files = all_groups[group_name]
        group_size = sum(f.stat().st_size for f in group_files)
        group_tags = set()
        for f in group_files:
            group_tags.update(extract_tags(f.name))
        summary["groups"].append({
            "group_name": group_name,
            "file_count": len(group_files),
            "total_size_bytes": group_size,
            "total_size_human": human_readable_size(group_size),
            "tags": sorted(list(group_tags)),
            "files": [f.name for f in sorted(group_files)],
        })

    if format == "json":
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
    elif format == "csv":
        with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "分组", "文件数", "总大小(字节)", "总大小", "标签", "文件列表"
            ])
            for group in summary["groups"]:
                writer.writerow([
                    group["group_name"],
                    group["file_count"],
                    group["total_size_bytes"],
                    group["total_size_human"],
                    ','.join(group["tags"]),
                    '; '.join(group["files"]),
                ])

    return summary


def cmd_pack(
    directory: str,
    output_dir: Optional[str] = None,
    group_by: str = "tag",
    project_tag: Optional[str] = None,
    manifest_format: str = "json",
    manifest_only: bool = False,
    recursive: bool = True,
    dry_run: bool = False,
):
    """生成素材包清单并按项目复制到交付目录。"""
    click.echo(f"\n[bold blue]源目录:[/bold blue] {directory}")
    if output_dir:
        click.echo(f"[bold blue]输出目录:[/bold blue] {output_dir}")
    click.echo(f"[bold blue]分组方式:[/bold blue] {group_by}")
    if project_tag:
        click.echo(f"[bold blue]项目标签:[/bold blue] {project_tag}")
    click.echo(f"[bold blue]清单格式:[/bold blue] {manifest_format}")
    click.echo(f"[bold blue]仅生成清单:[/bold blue] {'是' if manifest_only else '否'}")
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

    if project_tag:
        files = [f for f in files if project_tag in extract_tags(f.name)]
        if not files:
            click.echo(f"[yellow]未找到包含标签 [{project_tag}] 的文件[/yellow]")
            return

    groups = group_by_project(files, group_by)

    table = Table(title="项目分组", show_header=True, header_style="bold cyan")
    table.add_column("项目/标签", style="cyan")
    table.add_column("文件数", justify="right")
    table.add_column("总大小", justify="right")

    for group_name, group_files in sorted(groups.items()):
        total_size = sum(f.stat().st_size for f in group_files)
        table.add_row(
            group_name,
            str(len(group_files)),
            human_readable_size(total_size)
        )
    console.print(table)

    if manifest_only and not output_dir:
        click.echo("[yellow]请指定 --output-dir 用于存放清单文件[/yellow]")
        return

    if not manifest_only and not output_dir:
        click.echo("[yellow]请指定 --output-dir 用于存放复制的文件[/yellow]")
        return

    output_path = Path(output_dir) if output_dir else None
    if output_path and not dry_run:
        output_path.mkdir(parents=True, exist_ok=True)

    all_manifest_files = []
    copy_results = []

    for group_name, group_files in sorted(groups.items()):
        safe_group_name = "".join(c for c in group_name if c.isalnum() or c in (' ', '-', '_')).strip()
        if not safe_group_name:
            safe_group_name = "未命名"

        group_output_dir = output_path / safe_group_name if output_path else None
        if group_output_dir and not dry_run and not manifest_only:
            group_output_dir.mkdir(parents=True, exist_ok=True)

        if output_path:
            manifest_filename = f"{safe_group_name}_manifest.{manifest_format}"
            manifest_path = output_path / manifest_filename
            if dry_run:
                click.echo(f"[yellow]将生成清单:[/yellow] {manifest_path}")
            else:
                manifest = generate_manifest(
                    group_files,
                    manifest_path,
                    source_directory=directory,
                    group_name=group_name,
                    delivery_path=group_output_dir,
                    format=manifest_format
                )
                click.echo(f"[green]已生成清单:[/green] {manifest_path}")
                all_manifest_files.extend(group_files)

        if not manifest_only and group_output_dir:
            for file_path in group_files:
                dst_path = group_output_dir / file_path.name
                if dry_run:
                    click.echo(f"[yellow]将复制:[/yellow] {file_path.name} -> {group_output_dir}/")
                else:
                    ok, result = safe_copy(file_path, dst_path, dry_run=False)
                    if ok:
                        copy_results.append((file_path.name, group_name, "成功"))
                    else:
                        copy_results.append((file_path.name, group_name, f"失败: {result}"))

    if all_manifest_files and output_path and not dry_run:
        summary_filename = f"00_素材包汇总_manifest.{manifest_format}"
        summary_path = output_path / summary_filename
        summary = generate_summary_manifest(
            groups,
            summary_path,
            source_directory=directory,
            format=manifest_format
        )
        click.echo(f"[green]已生成汇总清单:[/green] {summary_path}")

        total_size = sum(f.stat().st_size for f in all_manifest_files)
        console.print(Panel(
            f"[bold]已生成 {len(groups)} 个分组清单 + 1 个汇总清单[/bold]\n"
            f"共 {len(all_manifest_files)} 个文件\n"
            f"[bold]总大小: {human_readable_size(total_size)}[/bold]\n"
            f"[bold]汇总清单:[/bold] {summary_path.name}",
            title="清单生成完成",
            border_style="green"
        ))

    if copy_results:
        success_count = sum(1 for r in copy_results if r[2] == "成功")
        fail_count = len(copy_results) - success_count

        console.print(Panel(
            f"[bold green]成功复制: {success_count}[/bold green]  |  "
            f"[bold red]失败: {fail_count}[/bold red]",
            title="文件复制完成",
            border_style="green" if fail_count == 0 else "red"
        ))

        if fail_count > 0:
            table = Table(title="复制失败详情", show_header=True, header_style="bold red")
            table.add_column("文件名", style="red")
            table.add_column("项目", style="yellow")
            table.add_column("错误", style="red")
            for name, group, status in copy_results:
                if status != "成功":
                    table.add_row(name, group, status)
            console.print(table)

    if dry_run:
        click.echo("\n[bold yellow]预览模式: 未执行任何修改[/bold yellow]")
