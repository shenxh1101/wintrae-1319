import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

CONFIG_FILENAME = ".art-organizer.json"

DEFAULT_CONFIG = {
    "recursive": True,
    "output_dir": "./delivery",
    "common_tags": [],
    "naming_pattern": "date_tags_name",
    "delivery_template": "{project}/{type}/{tags}",
    "report_dir": "./reports",
    "cache_dir": "./.art-organizer-cache",
    "history_dir": "./.art-organizer-history",
    "supported_extensions": {
        "images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp", ".svg", ".raw", ".heic", ".heif"],
        "brushes": [".abr", ".tpl", ".brush", ".gbr", ".vbr", ".brushset"]
    }
}


def find_config_file(directory: str) -> Optional[Path]:
    """从指定目录向上查找配置文件。"""
    current = Path(directory).resolve()
    while True:
        config_path = current / CONFIG_FILENAME
        if config_path.exists():
            return config_path
        parent = current.parent
        if parent == current:
            return None
        current = parent


def load_config(directory: Optional[str] = None) -> Dict[str, Any]:
    """加载配置文件，合并默认配置。"""
    config = DEFAULT_CONFIG.copy()

    if directory:
        config_path = find_config_file(directory)
        if config_path and config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                config = deep_merge(config, user_config)
                config["_config_file"] = str(config_path)
            except Exception as e:
                print(f"[yellow]警告: 读取配置文件失败 {config_path}: {e}[/yellow]")

    return config


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """深度合并两个字典，override 覆盖 base。"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def save_config(config: Dict[str, Any], directory: str) -> Path:
    """保存配置文件到指定目录。"""
    config_path = Path(directory) / CONFIG_FILENAME
    save_config = {k: v for k, v in config.items() if not k.startswith("_")}
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(save_config, f, ensure_ascii=False, indent=2)
    return config_path


def get_config_value(config: Dict[str, Any], key: str, default: Any = None) -> Any:
    """安全获取嵌套配置值，支持点号分隔的路径。"""
    keys = key.split('.')
    value = config
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return default
    return value


def merge_cli_args(config: Dict[str, Any], cli_args: Dict[str, Any]) -> Dict[str, Any]:
    """合并 CLI 参数到配置，CLI 参数优先。"""
    merged = config.copy()
    for key, value in cli_args.items():
        if value is not None and value is not False:
            merged[key] = value
    return merged


def generate_default_config() -> str:
    """生成默认配置文件内容示例。"""
    example_config = {
        "recursive": True,
        "output_dir": "./delivery",
        "common_tags": ["风景", "人物", "插画", "草稿", "定稿"],
        "naming_pattern": "date_tags_name",
        "delivery_template": "{project}/{type}/{tags}",
        "report_dir": "./reports",
        "cache_dir": "./.art-organizer-cache",
        "history_dir": "./.art-organizer-history",
        "supported_extensions": {
            "images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp", ".svg", ".raw", ".heic", ".heif"],
            "brushes": [".abr", ".tpl", ".brush", ".gbr", ".vbr", ".brushset"]
        },
        "_notes": [
            "delivery_template 可用变量: {project}, {type}, {tags}, {date}, {client}",
            "naming_pattern 可用: date_tags_name, tags_date_name, name_date_tags 等",
            "配置文件会从当前目录向上查找，命令行参数会覆盖配置文件"
        ]
    }
    return json.dumps(example_config, ensure_ascii=False, indent=2)
