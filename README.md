# Art Organizer - 插画师素材整理工具

一个功能强大的命令行工具，帮助插画师整理本地素材文件夹。

## 功能特性

- **scan** - 扫描图片和画笔文件，按尺寸、格式统计
- **tag** - 批量添加/移除主题标签到文件名
- **rename** - 根据标签和日期智能重命名文件
- **dedupe** - 查找重复文件，检查缺失预览图
- **pack** - 生成素材包清单，按项目复制到交付目录
- **report** - 输出多维度的空间占用报告

## 支持的文件格式

### 图片格式
`.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.tiff`, `.tif`, `.webp`, `.svg`, `.raw`, `.heic`, `.heif`

### 画笔格式
`.abr`, `.tpl`, `.brush`, `.gbr`, `.vbr`, `.brushset`

## 安装

### 方式一：直接安装（推荐）

```bash
pip install -e .
```

### 方式二：安装依赖后直接运行

```bash
pip install -e .
```

### 依赖包

- `click` - 命令行框架
- `Pillow` - 图片处理
- `send2trash` - 安全删除文件到回收站
- `rich` - 美观的终端输出

## 快速开始

### 1. 扫描目录

```bash
# 基本扫描
art-organizer scan ./素材

# 显示详细信息
art-organizer scan ./素材 --details

# 不递归子目录
art-organizer scan ./素材 --no-recursive
```

### 2. 添加标签

标签使用方括号 `[标签名]` 格式添加到文件名中。

```bash
# 添加单个标签
art-organizer tag ./素材 -a 风景

# 添加多个标签
art-organizer tag ./素材 -a 风景 -a 插画 -a 草稿

# 仅给特定标签的文件添加新标签
art-organizer tag ./素材 -a 已完成 --filter 项目A

# 预览将要进行的修改
art-organizer tag ./素材 -a 人物 --dry-run
```

### 3. 移除标签

```bash
# 移除标签
art-organizer tag ./素材 -r 旧标签

# 移除多个标签
art-organizer tag ./素材 -r 标签1 -r 标签2
```

### 4. 重命名文件

```bash
# 使用默认模式：日期_标签_文件名
art-organizer rename ./素材

# 使用标签_日期_文件名模式
art-organizer rename ./素材 --pattern tags_date_name

# 添加前缀
art-organizer rename ./素材 --prefix 项目A

# 可用命名模式：
#   date_tags_name   - 20240115_[风景][插画]_文件名
#   date_name_tags   - 20240115_文件名_[风景][插画]
#   tags_date_name   - [风景][插画]_20240115_文件名
#   tags_name_date   - [风景][插画]_文件名_20240115
#   name_date_tags   - 文件名_20240115_[风景][插画]
#   name_tags_date   - 文件名_[风景][插画]_20240115
#   date_tags        - 20240115_[风景][插画]
#   tags_date        - [风景][插画]_20240115
#   date_name        - 20240115_文件名
#   name_date        - 文件名_20240115
```

### 5. 查找重复文件

```bash
# 仅查找，不删除
art-organizer dedupe ./素材

# 查找并删除重复（保留最新文件）
art-organizer dedupe ./素材 --delete

# 删除时保留最旧文件
art-organizer dedupe ./素材 --delete --keep oldest

# 不检查预览图
art-organizer dedupe ./素材 --no-preview-check
```

### 6. 打包素材

```bash
# 仅生成清单（JSON格式）
art-organizer pack ./素材 -o ./交付 --manifest-only

# 按标签分组并复制文件
art-organizer pack ./素材 -o ./交付

# 按目录分组
art-organizer pack ./素材 -o ./交付 --group-by directory

# 导出CSV格式清单
art-organizer pack ./素材 -o ./交付 --format csv --manifest-only

# 仅处理特定项目标签
art-organizer pack ./素材 -o ./交付 --project 客户A
```

### 7. 生成报告

```bash
# 完整报告
art-organizer report ./素材

# 仅显示前10项统计
art-organizer report ./素材 --top 10

# 不显示某些统计
art-organizer report ./素材 --no-size --no-directory
```

## 标签规范

- 标签使用 `[标签名]` 格式，如：`风景插画_[人物][背景].png`
- 一个文件可以有多个标签
- 标签中可以包含中文、英文、数字
- 重命名和打包命令会自动识别和处理标签

## 预览模式

所有涉及文件修改的命令都支持 `--dry-run` 参数，可以预览将要执行的操作，确认无误后再执行。

```bash
# 预览重命名结果
art-organizer rename ./素材 --dry-run

# 预览标签添加
art-organizer tag ./素材 -a 新标签 --dry-run
```

## 递归处理

默认情况下，所有命令都会递归处理子目录。使用 `--no-recursive` 参数可以只处理当前目录。

```bash
# 只处理当前目录
art-organizer scan ./素材 --no-recursive
```

## 项目结构

```
art-organizer/
├── pyproject.toml
├── README.md
└── src/
    └── art_organizer/
        ├── __init__.py
        ├── cli.py              # CLI 入口
        ├── utils.py            # 工具函数
        ├── metadata.py         # 元数据处理
        └── commands/
            ├── __init__.py
            ├── scan.py         # scan 命令
            ├── tag.py          # tag 命令
            ├── rename.py       # rename 命令
            ├── dedupe.py       # dedupe 命令
            ├── pack.py         # pack 命令
            └── report.py       # report 命令
```

## 常用工作流

### 新素材入库

```bash
# 1. 扫描查看
art-organizer scan ./新素材 --details

# 2. 添加标签
art-organizer tag ./新素材 -a 人物 -a 写实

# 3. 重命名
art-organizer rename ./新素材 --pattern date_tags_name

# 4. 检查重复
art-organizer dedupe ./新素材
```

### 项目交付

```bash
# 1. 给项目文件打标签
art-organizer tag ./素材 -a 客户A项目 --filter 草稿

# 2. 打包交付
art-organizer pack ./素材 -o ./交付/客户A --project 客户A项目

# 3. 生成报告
art-organizer report ./交付/客户A
```

## 许可证

MIT
