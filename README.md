# Dolphin 批量重命名 / Dolphin Batch Rename

一个给 KDE Dolphin 用的表达式式批量重命名插件。选中文件后右键即可使用，实时预览新名称，
自动检测冲突，并支持一键撤销。

![Dolphin 25.04](https://img.shields.io/badge/Dolphin-25.04-blue) ![KF6](https://img.shields.io/badge/KF6-KDE%20Plasma%206-green)

## 为什么做这个 / Why

Dolphin 自带的批量重命名只能做简单编号；KRename 功能强但是独立程序，且没有表达式模板这种
轻量用法。这个插件参考 MT 管理器的批量重命名表达式，把「一个模板 + 实时预览」直接放进
Dolphin 右键菜单。


| 方案 | 表达式模板 | 实时预览 | 原地集成 | 撤销 |
| --- | --- | --- | --- | --- |
| Dolphin 内置 | 仅 `#` 编号 | 有 | 是 | 否 |
| KRename | 有（独立界面） | 有 | 否 | 有 |
| 本插件 | 有 | 有 | 是（右键菜单） | 有 |

## 功能

- 表达式模板：原名、扩展名、序号、补零序号、修改时间、EXIF 拍摄时间
- 实时预览表格，逐项显示「将重命名 / 不变 / 冲突 / 错误」及原因
- 冲突检测：批次内重名、目标已存在、目标被未改名文件占用、非法文件名
- 两阶段重命名：支持 `a → b`、`b → a` 这类交换和链式改名，失败自动回滚
- 撤销：每次成功重命名都会记录日志，可从右键菜单撤销
- 排序：文件名自然排序、倒序、修改时间、大小
- 预设：内置 6 个常用模板，可保存/删除自己的预设

## 安装

```bash
cd ~/path/to/dolphin-batch-rename
./install.sh
```

安装脚本会：

1. 在项目内创建 `.venv` 并安装 `PySide6-Essentials`（有 `uv` 用 `uv`，否则用 `python3 -m venv`）
2. 在 `~/.local/bin` 建立启动器
3. 写入 `~/.local/share/kio/servicemenus/dolphin-batch-rename.desktop` 并加上可执行位
4. 刷新 `kbuildsycoca6`

## 使用

在 Dolphin 中选中若干文件或文件夹 → 右键 → **批量重命名 → 表达式批量重命名…**，
输入表达式后按「执行重命名」。撤销入口在同一子菜单中。

### 表达式

| 表达式 | 含义 |
| --- | --- |
| `{P}` | 原文件名（不含扩展名）；目录为完整名称 |
| `{S}` | 原扩展名（含点，如 `.txt`）；没有则为空 |
| `{T}` | 修改时间，默认 `%Y-%m-%d %H.%M.%S` |
| `{T:%Y%m%d}` | 自定义 `strftime` 格式 |
| `{E}` / `{E:%Y%m%d}` | EXIF 拍摄时间（JPEG/PNG，缺失时回退到修改时间） |
| `{1}` `{0}` | 从指定数字开始递增的序号 |
| `{z1}` `{z8}` | 序号并补零到至少两位：`01`、`02` … `10` |
| `{{` `}}` | 输出字面量 `{` `}` |

模板中的多个序号表达式共享同一个递增计数，起始值取第一个序号表达式。

示例：

| 模板 | 结果 |
| --- | --- |
| `{P}{S}` | 原样保留 |
| `{P}_备份{S}` | `报告.docx` → `报告_备份.docx` |
| `假期_{z1}{S}` | `IMG_1.jpg` … → `假期_01.jpg`、`假期_02.jpg` … |
| `{T:%Y%m%d}_{P}{S}` | `2026-11-07_报告.docx`（按修改日期加前缀） |
| `IMG_{E:%Y%m%d_%H%M%S}{S}` | 用 EXIF 拍摄时间命名照片 |
| `{P}.bak` | 扩展名替换为 `.bak` |

## 安全设计

- 应用前必须没有冲突/错误，否则按钮禁用
- 重命名分两阶段（先改临时名，再改目标名），支持交换与链式改名
- 任一阶段失败会尽力回滚已完成的步骤
- 每次成功操作写入 `~/.local/state/dolphin-batch-rename/history/`，保留最近 50 条
- 撤销前会检查目标位置是否被占用，绝不覆盖已有文件

## 开发 / 测试

```bash
cd ~/path/to/dolphin-batch-rename
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

项目结构：

```
bin/dolphin-batch-rename        启动器
packaging/*.desktop             Dolphin ServiceMenu 模板
src/dolphin_batch_rename/
  engine.py                     模板解析、预览、冲突检测、执行与撤销
  exif.py                       无依赖的 JPEG/PNG EXIF 时间读取
  gui.py                        PySide6 对话框
  presets.py                    预设读写
  i18n.py                       中英文案
  app.py                        入口（GUI / --undo-last）
tests/                          单元测试与 offscreen GUI 冒烟测试
```

## 限制

- 只处理本地文件系统路径（Dolphin 传入的 `%F`）
- EXIF 仅支持 JPEG/PNG
- 撤销记录按用户保存，不跨用户共享

## 卸载

```bash
./uninstall.sh
```

会删除右键菜单和启动器，保留项目目录、虚拟环境与撤销记录。
