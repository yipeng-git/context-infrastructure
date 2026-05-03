"""从 outline.json 渲染社媒用脑图 PNG。

推荐输入是播客流程生成的 outline.json，格式与 generate_xmind.py 一致：

    {
      "title": "根标题",
      "children": [
        {"title": "主题1", "children": [{"title": "要点1"}]}
      ]
    }

用法：
    context-infrastructure/.venv/bin/python context-infrastructure/tools/render_mindmap_png.py collected-contents/播客名/集标题/outline.json
    context-infrastructure/.venv/bin/python context-infrastructure/tools/render_mindmap_png.py outline.json --layout tree --width 1280 --height 720 --scale 2

默认输出同目录的 mindmap.svg 和 mindmap.png。SVG 便于调样式，PNG 用于社媒发布。
默认生成 960x1600 竖版内容卡片式脑图，适合社媒 portrait 发布。
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


DEFAULT_WIDTH = 960
DEFAULT_HEIGHT = 1600
DEFAULT_MAX_DEPTH = 2
BACKGROUND = "#050914"
TEXT_PRIMARY = "#e9eef8"
TEXT_SECONDARY = "#cbd5e1"
TEXT_MUTED = "#94a3b8"

BRANCH_COLORS = [
    "#f97316",
    "#94a3b8",
    "#38bdf8",
    "#d946ef",
    "#22d3ee",
    "#f59e0b",
    "#84cc16",
    "#ec4899",
    "#a855f7",
    "#14b8a6",
]


@dataclass
class TreeNode:
    title: str
    children: list["TreeNode"] = field(default_factory=list)


@dataclass
class LayoutNode:
    title: str
    depth: int
    x: float = 0.0
    y: float = 0.0
    color: str = BRANCH_COLORS[0]
    lines: list[str] = field(default_factory=list)
    children: list["LayoutNode"] = field(default_factory=list)


@dataclass
class PortraitSection:
    node: LayoutNode
    time_label: str
    title_lines: list[str]
    child_lines: list[list[str]]
    hidden_children: int
    x: float
    y: float
    width: float
    height: float
    color: str


def load_outline(path: Path) -> TreeNode:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("outline.json 顶层必须是对象")
    return parse_node(data)


def parse_node(data: dict) -> TreeNode:
    title = str(data.get("title", "")).strip()
    if not title:
        raise ValueError("每个节点都需要 title")

    children_data = data.get("children", [])
    if children_data is None:
        children_data = []
    if not isinstance(children_data, list):
        raise ValueError(f"节点 children 必须是数组: {title}")

    children = []
    for child in children_data:
        if not isinstance(child, dict):
            raise ValueError(f"子节点必须是对象: {title}")
        children.append(parse_node(child))
    return TreeNode(title=title, children=children)


def max_depth(node: TreeNode, depth: int = 0) -> int:
    if not node.children:
        return depth
    return max(max_depth(child, depth + 1) for child in node.children)


def leaf_count(node: TreeNode) -> int:
    if not node.children:
        return 1
    return sum(leaf_count(child) for child in node.children)


def display_width(text: str) -> float:
    width = 0.0
    for char in text:
        if unicodedata.east_asian_width(char) in {"F", "W"}:
            width += 2.0
        elif char.isspace():
            width += 0.7
        else:
            width += 1.0
    return width


def wrap_text(text: str, max_units: float, max_lines: int) -> list[str]:
    """按近似显示宽度换行，兼容中文和英文混排。"""
    text = " ".join(text.split())
    if display_width(text) <= max_units:
        return [text]

    lines: list[str] = []
    current = ""
    current_width = 0.0

    for char in text:
        char_width = display_width(char)
        if current and current_width + char_width > max_units:
            lines.append(current.rstrip())
            current = char
            current_width = char_width
            if len(lines) == max_lines:
                break
        else:
            current += char
            current_width += char_width

    if len(lines) < max_lines and current:
        lines.append(current.rstrip())

    if len(lines) > max_lines:
        lines = lines[:max_lines]

    if lines and display_width("".join(lines)) < display_width(text):
        lines[-1] = trim_to_width(lines[-1], max_units - 2) + "…"
    return lines or [trim_to_width(text, max_units)]


def trim_to_width(text: str, max_units: float) -> str:
    current = ""
    current_width = 0.0
    for char in text:
        char_width = display_width(char)
        if current_width + char_width > max_units:
            break
        current += char
        current_width += char_width
    return current.rstrip()


def text_limits_for_depth(depth: int) -> tuple[float, int]:
    if depth == 0:
        return 28, 2
    if depth == 1:
        return 34, 2
    if depth == 2:
        return 26, 2
    return 24, 1


def font_size_for_depth(depth: int) -> int:
    if depth == 0:
        return 14
    if depth == 1:
        return 13
    if depth == 2:
        return 11
    return 9


def line_height_for_depth(depth: int) -> float:
    return font_size_for_depth(depth) * 1.28


def build_layout_tree(
    node: TreeNode,
    *,
    depth: int,
    color: str,
    max_render_depth: int | None,
) -> LayoutNode:
    max_units, max_lines = text_limits_for_depth(depth)
    layout = LayoutNode(
        title=node.title,
        depth=depth,
        color=color,
        lines=wrap_text(node.title, max_units, max_lines),
    )
    if max_render_depth is not None and depth >= max_render_depth:
        return layout
    layout.children = [
        build_layout_tree(
            child,
            depth=depth + 1,
            color=color,
            max_render_depth=max_render_depth,
        )
        for child in node.children
    ]
    return layout


def iter_nodes(node: LayoutNode) -> Iterable[LayoutNode]:
    yield node
    for child in node.children:
        yield from iter_nodes(child)


def assign_colors(root: LayoutNode) -> None:
    for index, child in enumerate(root.children):
        child_color = BRANCH_COLORS[index % len(BRANCH_COLORS)]
        apply_color(child, child_color)


def apply_color(node: LayoutNode, color: str) -> None:
    node.color = color
    for child in node.children:
        apply_color(child, color)


def layout_tree(root: LayoutNode, width: int, height: int) -> None:
    max_tree_depth = max(node.depth for node in iter_nodes(root))
    left_margin = width * 0.14
    right_margin = width * 0.06
    top_margin = height * 0.08
    bottom_margin = height * 0.08

    root.x = left_margin
    root.y = height / 2

    if max_tree_depth == 0:
        return

    x_span = width - left_margin - right_margin
    x_step = x_span / (max_tree_depth + 0.45)
    for node in iter_nodes(root):
        if node.depth == 0:
            continue
        node.x = left_margin + x_step * node.depth

    leaves = [node for node in iter_nodes(root) if not node.children and node.depth > 0]
    if not leaves:
        return

    usable_height = height - top_margin - bottom_margin
    y_step = usable_height / max(len(leaves) - 1, 1)
    for index, leaf in enumerate(leaves):
        leaf.y = top_margin + y_step * index

    assign_internal_y(root)
    reduce_branch_crowding(root, min_gap=max(10.0, height / 72))


def assign_internal_y(node: LayoutNode) -> float:
    if not node.children:
        return node.y
    child_ys = [assign_internal_y(child) for child in node.children]
    if node.depth > 0:
        node.y = sum(child_ys) / len(child_ys)
    return node.y


def reduce_branch_crowding(node: LayoutNode, min_gap: float) -> None:
    """让同层兄弟节点至少保持一个很小的间距，降低文字压线概率。"""
    if len(node.children) > 1:
        node.children.sort(key=lambda child: child.y)
        previous_y = -math.inf
        for child in node.children:
            if child.y - previous_y < min_gap:
                child.y = previous_y + min_gap
            previous_y = child.y
    for child in node.children:
        reduce_branch_crowding(child, min_gap)


def estimate_text_width(lines: list[str], font_size: int) -> float:
    if not lines:
        return 0
    return max(display_width(line) for line in lines) * font_size * 0.55


def split_time_title(title: str) -> tuple[str, str]:
    match = re.match(r"^(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)$", title.strip())
    if not match:
        return "", title.strip()
    return match.group(1), match.group(2).strip()


def portrait_title_units(width: float, font_size: int) -> float:
    return max(12.0, width / (font_size * 0.55))


def build_portrait_sections(root: LayoutNode, width: int, height: int) -> list[PortraitSection]:
    children = root.children
    if not children:
        return []

    left_margin = width * 0.12
    right_margin = width * 0.07
    card_x = width * 0.18
    card_width = width - card_x - right_margin
    top = height * 0.19
    bottom = height * 0.05
    gap = max(12.0, height * 0.009)
    card_height = (height - top - bottom - gap * (len(children) - 1)) / len(children)
    card_height = max(92.0, min(156.0, card_height))

    sections: list[PortraitSection] = []
    y = top
    for index, child in enumerate(children):
        color = BRANCH_COLORS[index % len(BRANCH_COLORS)]
        time_label, title = split_time_title(child.title)
        title_lines = wrap_text(
            title,
            portrait_title_units(card_width - 170, 19),
            2,
        )

        max_child_count = 4 if card_height >= 116 else 3
        child_lines = [
            wrap_text(grand_child.title, portrait_title_units((card_width - 84) / 2, 14), 1)
            for grand_child in child.children[:max_child_count]
        ]
        hidden_children = max(0, len(child.children) - max_child_count)
        sections.append(
            PortraitSection(
                node=child,
                time_label=time_label,
                title_lines=title_lines,
                child_lines=child_lines,
                hidden_children=hidden_children,
                x=card_x,
                y=y,
                width=card_width,
                height=card_height,
                color=color,
            )
        )
        y += card_height + gap

    return sections


def render_portrait_svg(root: LayoutNode, width: int, height: int) -> str:
    sections = build_portrait_sections(root, width, height)
    root_lines = wrap_text(root.title, portrait_title_units(width - 112, 34), 2)
    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="100%" height="100%" fill="{BACKGROUND}"/>',
        f'<ellipse cx="{width * 0.14:.1f}" cy="{height * 0.16:.1f}" rx="{width * 0.42:.1f}" ry="{height * 0.18:.1f}" fill="#101a33" opacity="0.75"/>',
        '<g font-family="-apple-system, BlinkMacSystemFont, \'PingFang SC\', \'Hiragino Sans GB\', \'Microsoft YaHei\', sans-serif">',
        f'<text x="{width * 0.08:.1f}" y="{height * 0.06:.1f}" font-size="18" font-weight="700" fill="{TEXT_MUTED}" letter-spacing="3">PODCAST MINDMAP</text>',
        f'<text x="{width * 0.08:.1f}" y="{height * 0.105:.1f}" font-size="34" font-weight="800" fill="{TEXT_PRIMARY}">',
    ]
    for index, line in enumerate(root_lines):
        dy = 0 if index == 0 else 42
        svg.append(f'<tspan x="{width * 0.08:.1f}" dy="{dy}">{html.escape(line)}</tspan>')
    svg.append("</text>")

    if sections:
        spine_x = width * 0.10
        svg.append(
            f'<line x1="{spine_x:.1f}" y1="{sections[0].y + 12:.1f}" x2="{spine_x:.1f}" '
            f'y2="{sections[-1].y + sections[-1].height - 12:.1f}" stroke="#23304a" stroke-width="3" stroke-linecap="round"/>'
        )
    for section in sections:
        svg.append(portrait_section_svg(section, width))
    svg.append("</g>")
    svg.append("</svg>")
    return "\n".join(svg)


def portrait_section_svg(section: PortraitSection, width: int) -> str:
    spine_x = width * 0.10
    marker_y = section.y + section.height / 2
    parts = [
        f'<line x1="{spine_x:.1f}" y1="{marker_y:.1f}" x2="{section.x:.1f}" y2="{marker_y:.1f}" stroke="{section.color}" stroke-width="2.4" opacity="0.75"/>',
        f'<circle cx="{spine_x:.1f}" cy="{marker_y:.1f}" r="8" fill="{section.color}" stroke="#0b1020" stroke-width="3"/>',
        f'<rect x="{section.x:.1f}" y="{section.y:.1f}" width="{section.width:.1f}" height="{section.height:.1f}" rx="22" fill="#0f172a" stroke="#22304a" stroke-width="1"/>',
        f'<rect x="{section.x:.1f}" y="{section.y:.1f}" width="5" height="{section.height:.1f}" rx="2.5" fill="{section.color}"/>',
    ]
    text_x = section.x + 26
    if section.time_label:
        parts.append(
            f'<rect x="{text_x:.1f}" y="{section.y + 16:.1f}" width="68" height="24" rx="12" fill="{section.color}" opacity="0.18"/>'
        )
        parts.append(
            f'<text x="{text_x + 12:.1f}" y="{section.y + 33:.1f}" font-size="13" font-weight="700" fill="{section.color}">{html.escape(section.time_label)}</text>'
        )
        title_x = text_x + 84
    else:
        title_x = text_x
    title_y = section.y + 34
    parts.append(f'<text x="{title_x:.1f}" y="{title_y:.1f}" font-size="19" font-weight="800" fill="{TEXT_PRIMARY}">')
    for index, line in enumerate(section.title_lines):
        dy = 0 if index == 0 else 24
        parts.append(f'<tspan x="{title_x:.1f}" dy="{dy}">{html.escape(line)}</tspan>')
    parts.append("</text>")

    tag_top = section.y + 58 + max(0, len(section.title_lines) - 1) * 18
    col_width = (section.width - 62) / 2
    for index, lines in enumerate(section.child_lines):
        col = index % 2
        row = index // 2
        tag_x = text_x + col * col_width
        tag_y = tag_top + row * 28
        label = lines[0] if lines else ""
        parts.append(
            f'<circle cx="{tag_x + 5:.1f}" cy="{tag_y + 8:.1f}" r="3" fill="{section.color}" opacity="0.9"/>'
        )
        parts.append(
            f'<text x="{tag_x + 15:.1f}" y="{tag_y + 13:.1f}" font-size="14" font-weight="500" fill="{TEXT_SECONDARY}">{html.escape(label)}</text>'
        )
    if section.hidden_children:
        parts.append(
            f'<text x="{section.x + section.width - 70:.1f}" y="{section.y + section.height - 20:.1f}" font-size="13" fill="{TEXT_MUTED}">+{section.hidden_children}</text>'
        )
    return "\n".join(parts)


def render_svg(root: LayoutNode, width: int, height: int) -> str:
    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<defs>",
        '<radialGradient id="bg" cx="30%" cy="45%" r="80%">',
        '<stop offset="0%" stop-color="#0b1224"/>',
        f'<stop offset="100%" stop-color="{BACKGROUND}"/>',
        "</radialGradient>",
        "</defs>",
        f'<rect width="100%" height="100%" fill="url(#bg)"/>',
        '<g fill="none" stroke-linecap="round" stroke-linejoin="round">',
    ]
    for node in iter_nodes(root):
        for child in node.children:
            svg.append(edge_path(node, child))
    svg.append("</g>")
    svg.append('<g font-family="-apple-system, BlinkMacSystemFont, \'PingFang SC\', \'Hiragino Sans GB\', \'Microsoft YaHei\', sans-serif">')
    svg.append(root_badge(root))
    for node in iter_nodes(root):
        if node.depth == 0:
            continue
        svg.append(node_marker(node))
        svg.append(node_text(node))
    svg.append("</g>")
    svg.append("</svg>")
    return "\n".join(svg)


def render_png(
    root: LayoutNode,
    png_path: Path,
    width: int,
    height: int,
    scale: float,
    font_path: str | None,
    layout: str,
) -> None:
    if layout == "portrait":
        render_portrait_png(root, png_path, width, height, scale, font_path)
    else:
        render_tree_png(root, png_path, width, height, scale, font_path)


def render_tree_png(root: LayoutNode, png_path: Path, width: int, height: int, scale: float, font_path: str | None) -> None:
    factor = scale
    image = Image.new("RGB", (int(width * factor), int(height * factor)), BACKGROUND)
    draw = ImageDraw.Draw(image, "RGBA")
    draw_background_glow(draw, width, height, factor)

    for node in iter_nodes(root):
        for child in node.children:
            draw_edge(draw, node, child, factor)

    draw_root_badge(draw, root, factor, font_path)
    for node in iter_nodes(root):
        if node.depth == 0:
            continue
        draw_node_marker(draw, node, factor)
        draw_node_text(draw, node, factor, font_path)

    image.save(png_path)


def render_portrait_png(
    root: LayoutNode,
    png_path: Path,
    width: int,
    height: int,
    scale: float,
    font_path: str | None,
) -> None:
    image = Image.new("RGB", (int(width * scale), int(height * scale)), BACKGROUND)
    draw = ImageDraw.Draw(image, "RGBA")
    draw_portrait_background(draw, width, height, scale)
    draw_portrait_header(draw, root, width, height, scale, font_path)

    sections = build_portrait_sections(root, width, height)
    if sections:
        spine_x = width * 0.10
        draw.line(
            [
                (round(spine_x * scale), round((sections[0].y + 12) * scale)),
                (round(spine_x * scale), round((sections[-1].y + sections[-1].height - 12) * scale)),
            ],
            fill=hex_to_rgba("#263653", 210),
            width=max(2, round(3 * scale)),
        )
    for section in sections:
        draw_portrait_section(draw, section, width, scale, font_path)

    image.save(png_path)


def draw_portrait_background(draw: ImageDraw.ImageDraw, width: int, height: int, scale: float) -> None:
    draw.ellipse(
        (
            int(-width * 0.28 * scale),
            int(-height * 0.08 * scale),
            int(width * 0.82 * scale),
            int(height * 0.34 * scale),
        ),
        fill=(19, 30, 58, 165),
    )
    draw.ellipse(
        (
            int(width * 0.50 * scale),
            int(height * 0.58 * scale),
            int(width * 1.35 * scale),
            int(height * 1.08 * scale),
        ),
        fill=(11, 53, 74, 72),
    )
    for index, color in enumerate(BRANCH_COLORS[:7]):
        x = (width * (0.18 + index * 0.105)) * scale
        y = height * 0.155 * scale
        draw.line(
            [(round(x), round(y)), (round(x + width * 0.045 * scale), round(y))],
            fill=hex_to_rgba(color, 180),
            width=max(2, round(4 * scale)),
        )


def draw_portrait_header(
    draw: ImageDraw.ImageDraw,
    root: LayoutNode,
    width: int,
    height: int,
    scale: float,
    font_path: str | None,
) -> None:
    margin_x = width * 0.08
    label_font = load_font(15, scale, font_path, bold=True)
    title_font = load_font(34, scale, font_path, bold=True)
    subtitle_font = load_font(14, scale, font_path, bold=False)
    draw.text(
        (round(margin_x * scale), round(height * 0.045 * scale)),
        "PODCAST MINDMAP",
        font=label_font,
        fill=hex_to_rgba(TEXT_MUTED, 230),
    )

    root_lines = wrap_text(root.title, portrait_title_units(width - margin_x * 2, 34), 2)
    title_y = height * 0.075
    for index, line in enumerate(root_lines):
        draw.text(
            (round(margin_x * scale), round((title_y + index * 42) * scale)),
            line,
            font=title_font,
            fill=hex_to_rgba(TEXT_PRIMARY, 255),
        )
    draw.text(
        (round(margin_x * scale), round((height * 0.155) * scale)),
        "核心章节 / 关键论点 / 可读版脑图",
        font=subtitle_font,
        fill=hex_to_rgba(TEXT_MUTED, 220),
    )


def draw_portrait_section(
    draw: ImageDraw.ImageDraw,
    section: PortraitSection,
    width: int,
    scale: float,
    font_path: str | None,
) -> None:
    spine_x = width * 0.10
    marker_y = section.y + section.height / 2
    draw.line(
        [
            (round(spine_x * scale), round(marker_y * scale)),
            (round(section.x * scale), round(marker_y * scale)),
        ],
        fill=hex_to_rgba(section.color, 190),
        width=max(2, round(2.4 * scale)),
    )
    draw_node_marker_at(draw, spine_x, marker_y, 8, section.color, scale)

    shadow_box = tuple(
        round(value * scale)
        for value in (
            section.x + 4,
            section.y + 6,
            section.x + section.width + 4,
            section.y + section.height + 6,
        )
    )
    draw.rounded_rectangle(shadow_box, radius=round(24 * scale), fill=(0, 0, 0, 56))

    box = tuple(
        round(value * scale)
        for value in (
            section.x,
            section.y,
            section.x + section.width,
            section.y + section.height,
        )
    )
    draw.rounded_rectangle(
        box,
        radius=round(24 * scale),
        fill=hex_to_rgba("#0f172a", 242),
        outline=hex_to_rgba("#253650", 235),
        width=max(1, round(scale)),
    )
    accent = tuple(
        round(value * scale)
        for value in (
            section.x,
            section.y,
            section.x + 6,
            section.y + section.height,
        )
    )
    draw.rounded_rectangle(accent, radius=round(3 * scale), fill=hex_to_rgba(section.color, 255))

    text_x = section.x + 26
    title_font = load_font(19, scale, font_path, bold=True)
    time_font = load_font(13, scale, font_path, bold=True)
    child_font = load_font(14, scale, font_path, bold=False)
    more_font = load_font(13, scale, font_path, bold=True)

    if section.time_label:
        pill = tuple(
            round(value * scale)
            for value in (
                text_x,
                section.y + 15,
                text_x + 74,
                section.y + 41,
            )
        )
        draw.rounded_rectangle(pill, radius=round(13 * scale), fill=hex_to_rgba(section.color, 42))
        draw.text(
            (round((text_x + 12) * scale), round((section.y + 20) * scale)),
            section.time_label,
            font=time_font,
            fill=hex_to_rgba(section.color, 255),
        )
        title_x = text_x + 88
    else:
        title_x = text_x

    title_y = section.y + 17
    for index, line in enumerate(section.title_lines):
        draw.text(
            (round(title_x * scale), round((title_y + index * 23) * scale)),
            line,
            font=title_font,
            fill=hex_to_rgba(TEXT_PRIMARY, 255),
        )

    tag_top = section.y + 62 + max(0, len(section.title_lines) - 1) * 18
    col_width = (section.width - 62) / 2
    for index, lines in enumerate(section.child_lines):
        col = index % 2
        row = index // 2
        tag_x = text_x + col * col_width
        tag_y = tag_top + row * 27
        label = lines[0] if lines else ""
        draw_node_marker_at(draw, tag_x + 5, tag_y + 9, 3, section.color, scale)
        draw.text(
            (round((tag_x + 15) * scale), round(tag_y * scale)),
            label,
            font=child_font,
            fill=hex_to_rgba(TEXT_SECONDARY, 238),
        )

    if section.hidden_children:
        draw.text(
            (round((section.x + section.width - 54) * scale), round((section.y + section.height - 29) * scale)),
            f"+{section.hidden_children}",
            font=more_font,
            fill=hex_to_rgba(TEXT_MUTED, 235),
        )


def draw_background_glow(draw: ImageDraw.ImageDraw, width: int, height: int, scale: float) -> None:
    draw.ellipse(
        (
            int(-width * 0.12 * scale),
            int(-height * 0.18 * scale),
            int(width * 0.72 * scale),
            int(height * 1.12 * scale),
        ),
        fill=(18, 27, 52, 90),
    )


def draw_edge(draw: ImageDraw.ImageDraw, parent: LayoutNode, child: LayoutNode, scale: float) -> None:
    start_x = parent.x
    if parent.depth == 0:
        start_x += root_badge_width(parent) / 2
    else:
        start_x += 4
    end_x = child.x
    curve = max(36.0, (end_x - start_x) * 0.45)
    points = cubic_points(
        (start_x, parent.y),
        (start_x + curve, parent.y),
        (end_x - curve, child.y),
        (end_x, child.y),
        steps=32,
    )
    scaled_points = [(round(x * scale), round(y * scale)) for x, y in points]
    width = max(1, round((2.5 - child.depth * 0.35) * scale))
    color = hex_to_rgba(child.color, alpha=max(110, 235 - child.depth * 30))
    draw.line(scaled_points, fill=color, width=width, joint="curve")


def cubic_points(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    steps: int,
) -> list[tuple[float, float]]:
    points = []
    for index in range(steps + 1):
        t = index / steps
        inv = 1 - t
        x = inv**3 * p0[0] + 3 * inv**2 * t * p1[0] + 3 * inv * t**2 * p2[0] + t**3 * p3[0]
        y = inv**3 * p0[1] + 3 * inv**2 * t * p1[1] + 3 * inv * t**2 * p2[1] + t**3 * p3[1]
        points.append((x, y))
    return points


def draw_root_badge(draw: ImageDraw.ImageDraw, root: LayoutNode, scale: float, font_path: str | None) -> None:
    font_size = font_size_for_depth(0)
    line_height = line_height_for_depth(0)
    font = load_font(font_size, scale, font_path, bold=True)
    width = root_badge_width(root)
    height = max(36.0, len(root.lines) * line_height + 18)
    x = root.x - width / 2
    y = root.y - height / 2
    box = tuple(round(value * scale) for value in (x, y, x + width, y + height))
    draw.rounded_rectangle(
        box,
        radius=round(18 * scale),
        fill=hex_to_rgba("#0f172a", 236),
        outline=hex_to_rgba("#1f2937", 255),
        width=max(1, round(scale)),
    )
    draw_node_marker_at(draw, root.x + width / 2, root.y, 3.8, BRANCH_COLORS[0], scale)

    first_y = root.y - (len(root.lines) - 1) * line_height / 2
    for index, line in enumerate(root.lines):
        line_y = (first_y + index * line_height) * scale
        bbox = draw.textbbox((0, 0), line, font=font)
        line_x = root.x * scale - (bbox[2] - bbox[0]) / 2
        draw.text((line_x, line_y - font_size * scale * 0.72), line, font=font, fill=hex_to_rgba(TEXT_PRIMARY, 255))


def draw_node_marker(draw: ImageDraw.ImageDraw, node: LayoutNode, scale: float) -> None:
    radius = 3.1 if node.depth == 1 else 2.5
    draw_node_marker_at(draw, node.x, node.y, radius, node.color, scale)


def draw_node_marker_at(
    draw: ImageDraw.ImageDraw,
    x: float,
    y: float,
    radius: float,
    color: str,
    scale: float,
) -> None:
    box = tuple(
        round(value * scale)
        for value in (
            x - radius,
            y - radius,
            x + radius,
            y + radius,
        )
    )
    draw.ellipse(box, fill=hex_to_rgba(color, 255), outline=hex_to_rgba("#0b1020", 255), width=max(1, round(scale)))


def draw_node_text(draw: ImageDraw.ImageDraw, node: LayoutNode, scale: float, font_path: str | None) -> None:
    font_size = font_size_for_depth(node.depth)
    line_height = line_height_for_depth(node.depth)
    font = load_font(font_size, scale, font_path, bold=node.depth <= 1)
    fill = TEXT_PRIMARY if node.depth <= 1 else TEXT_SECONDARY
    if node.depth >= 3:
        fill = TEXT_MUTED
    x = (node.x + 9) * scale
    first_y = node.y - (len(node.lines) - 1) * line_height / 2
    for index, line in enumerate(node.lines):
        y = (first_y + index * line_height) * scale
        draw.text((x, y - font_size * scale * 0.72), line, font=font, fill=hex_to_rgba(fill, 255))


def load_font(size: int, scale: float, font_path: str | None, bold: bool) -> ImageFont.FreeTypeFont:
    font_size = max(1, round(size * scale))
    candidates = []
    if font_path:
        candidates.append(font_path)
    if bold:
        candidates.extend([
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
        ])
    candidates.extend([
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ])
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, font_size)
        except OSError:
            continue
    return ImageFont.load_default()


def hex_to_rgba(color: str, alpha: int) -> tuple[int, int, int, int]:
    value = color.lstrip("#")
    return (
        int(value[0:2], 16),
        int(value[2:4], 16),
        int(value[4:6], 16),
        alpha,
    )


def edge_path(parent: LayoutNode, child: LayoutNode) -> str:
    start_x = parent.x
    if parent.depth == 0:
        start_x += root_badge_width(parent) / 2
    else:
        start_x += 4
    end_x = child.x
    curve = max(36.0, (end_x - start_x) * 0.45)
    stroke_width = max(1.1, 2.5 - child.depth * 0.35)
    opacity = max(0.42, 0.92 - child.depth * 0.12)
    d = (
        f"M {start_x:.1f} {parent.y:.1f} "
        f"C {start_x + curve:.1f} {parent.y:.1f}, "
        f"{end_x - curve:.1f} {child.y:.1f}, "
        f"{end_x:.1f} {child.y:.1f}"
    )
    return f'<path d="{d}" stroke="{child.color}" stroke-width="{stroke_width:.2f}" opacity="{opacity:.2f}"/>'


def root_badge_width(root: LayoutNode) -> float:
    return max(170.0, estimate_text_width(root.lines, font_size_for_depth(0)) + 34)


def root_badge(root: LayoutNode) -> str:
    font_size = font_size_for_depth(0)
    line_height = line_height_for_depth(0)
    width = root_badge_width(root)
    height = max(36.0, len(root.lines) * line_height + 18)
    x = root.x - width / 2
    y = root.y - height / 2
    parts = [
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="18" fill="#0f172a" stroke="#1f2937" stroke-width="1"/>',
        f'<circle cx="{root.x + width / 2:.1f}" cy="{root.y:.1f}" r="3.8" fill="{BRANCH_COLORS[0]}"/>',
        f'<text x="{root.x:.1f}" y="{root.y - (len(root.lines) - 1) * line_height / 2:.1f}" text-anchor="middle" font-size="{font_size}" font-weight="600" fill="{TEXT_PRIMARY}">',
    ]
    for index, line in enumerate(root.lines):
        dy = 0 if index == 0 else line_height
        parts.append(f'<tspan x="{root.x:.1f}" dy="{dy:.1f}">{html.escape(line)}</tspan>')
    parts.append("</text>")
    return "\n".join(parts)


def node_marker(node: LayoutNode) -> str:
    radius = 3.1 if node.depth == 1 else 2.5
    return (
        f'<circle cx="{node.x:.1f}" cy="{node.y:.1f}" r="{radius:.1f}" '
        f'fill="{node.color}" stroke="#0b1020" stroke-width="1.1"/>'
    )


def node_text(node: LayoutNode) -> str:
    font_size = font_size_for_depth(node.depth)
    line_height = line_height_for_depth(node.depth)
    fill = TEXT_PRIMARY if node.depth <= 1 else TEXT_SECONDARY
    if node.depth >= 3:
        fill = TEXT_MUTED
    weight = "600" if node.depth == 1 else "500"
    x = node.x + 9
    y = node.y - (len(node.lines) - 1) * line_height / 2
    parts = [
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{font_size}" font-weight="{weight}" fill="{fill}">'
    ]
    for index, line in enumerate(node.lines):
        dy = 0 if index == 0 else line_height
        parts.append(f'<tspan x="{x:.1f}" dy="{dy:.1f}">{html.escape(line)}</tspan>')
    parts.append("</text>")
    return "\n".join(parts)


def default_output_paths(outline_path: Path, output: str | None, svg_output: str | None) -> tuple[Path, Path]:
    png_path = Path(output) if output else outline_path.parent / "mindmap.png"
    svg_path = Path(svg_output) if svg_output else png_path.with_suffix(".svg")
    return png_path, svg_path


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须是正整数")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须是正数")
    return parsed


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="从 outline.json 渲染深色脑图 PNG")
    parser.add_argument("outline", help="outline.json 文件路径")
    parser.add_argument("--output", "-o", help="输出 PNG 路径，默认同目录 mindmap.png")
    parser.add_argument("--svg-output", help="输出 SVG 路径，默认与 PNG 同名 .svg")
    parser.add_argument("--width", type=positive_int, default=DEFAULT_WIDTH, help="画布宽度，默认 960")
    parser.add_argument("--height", type=positive_int, default=DEFAULT_HEIGHT, help="画布高度，默认 1600")
    parser.add_argument("--scale", type=positive_float, default=2.0, help="PNG 导出倍率，默认 2")
    parser.add_argument(
        "--layout",
        choices=["portrait", "tree"],
        default="portrait",
        help="渲染布局，默认 portrait；tree 为横向 XMind 风格",
    )
    parser.add_argument(
        "--max-depth",
        type=positive_int,
        default=DEFAULT_MAX_DEPTH,
        help="最多渲染到第 N 层，默认 2；根节点是第 0 层",
    )
    parser.add_argument("--font", help="自定义字体路径；默认自动使用 macOS 中文字体")
    parser.add_argument("--svg-only", action="store_true", help="只输出 SVG，不转换 PNG")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    outline_path = Path(args.outline)
    if not outline_path.exists():
        print(f"错误: 文件不存在: {outline_path}", file=sys.stderr)
        sys.exit(1)

    png_path, svg_path = default_output_paths(outline_path, args.output, args.svg_output)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.parent.mkdir(parents=True, exist_ok=True)

    tree = load_outline(outline_path)
    depth_limit = min(args.max_depth, max_depth(tree))
    layout_root = build_layout_tree(
        tree,
        depth=0,
        color=BRANCH_COLORS[0],
        max_render_depth=depth_limit,
    )
    assign_colors(layout_root)
    if args.layout == "tree":
        layout_tree(layout_root, args.width, args.height)

    svg = (
        render_portrait_svg(layout_root, args.width, args.height)
        if args.layout == "portrait"
        else render_svg(layout_root, args.width, args.height)
    )
    svg_path.write_text(svg, encoding="utf-8")
    result = {"svg": str(svg_path)}

    if not args.svg_only:
        render_png(layout_root, png_path, args.width, args.height, args.scale, args.font, args.layout)
        result["png"] = str(png_path)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
