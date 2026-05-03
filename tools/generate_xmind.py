"""XMind 思维导图生成工具

从 JSON 大纲生成 .xmind 文件。

用法:
    python tools/generate_xmind.py outline.json
    python tools/generate_xmind.py outline.json --output mindmap.xmind

JSON 格式:
    {
      "title": "根标题",
      "children": [
        {"title": "主题1", "children": [{"title": "要点1"}, ...]},
        ...
      ]
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import xmind


def add_topic(parent_topic, node: dict):
    """递归添加子节点"""
    sub = parent_topic.addSubTopic()
    sub.setTitle(node.get("title", ""))
    for child in node.get("children", []):
        add_topic(sub, child)


def main():
    parser = argparse.ArgumentParser(description="从 JSON 大纲生成 XMind 思维导图")
    parser.add_argument("outline", help="outline.json 文件路径")
    parser.add_argument("--output", "-o", help="输出 .xmind 路径 (默认同目录 mindmap.xmind)")
    args = parser.parse_args()

    outline_path = Path(args.outline)
    if not outline_path.exists():
        print(f"错误: 文件不存在: {outline_path}", file=sys.stderr)
        sys.exit(1)

    outline = json.loads(outline_path.read_text(encoding="utf-8"))
    output_path = Path(args.output) if args.output else outline_path.parent / "mindmap.xmind"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    workbook = xmind.load(str(output_path))
    sheet = workbook.getPrimarySheet()
    title = outline.get("title", "思维导图")
    sheet.setTitle(title)

    root = sheet.getRootTopic()
    root.setTitle(title)
    for child in outline.get("children", []):
        add_topic(root, child)

    xmind.save(workbook, path=str(output_path))
    print(f"完成: {output_path}", file=sys.stderr)
    print(str(output_path))


if __name__ == "__main__":
    main()
