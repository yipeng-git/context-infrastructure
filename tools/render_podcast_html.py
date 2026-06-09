#!/usr/bin/env python3
"""Render a local Podwise-style HTML page for one podcast episode."""

from __future__ import annotations

import argparse
import html
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote

from transcribe_audio import (
    DEFAULT_MAX_GROUP_CHARS,
    DEFAULT_MAX_GROUP_SECONDS,
    load_corrections,
    load_lexicon,
    load_segments_jsonl,
    render_segments,
)


AUDIO_EXTENSIONS = (".mp3", ".m4a", ".wav", ".opus", ".aac", ".flac")
PIPELINE_DIRNAME = "_pipeline"
EMPTY_STATE = '<p class="empty-state">No content yet. Generate the corresponding Markdown file and rerun the HTML renderer.</p>'
ALLOWED_HTML_TAGS = {"p", "br", "strong", "b", "em", "i", "span", "a", "ul", "ol", "li"}
VOID_HTML_TAGS = {"br"}
ALLOWED_HTML_ATTRS = {
    "a": {"href", "class", "data-timestamp", "target", "rel"},
}
MINDMAP_COLORS = [
    "#fb923c",
    "#94a3b8",
    "#38bdf8",
    "#ec4899",
    "#22d3ee",
    "#f97316",
    "#a855f7",
    "#84cc16",
    "#14b8a6",
]


@dataclass
class PodcastHtmlResult:
    episode_dir: str
    html: str
    transcript_source: str
    has_audio: bool
    has_mindmap: bool
    has_insights: bool


def _fmt_ts(seconds: float, force_hours: bool = False) -> str:
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if force_hours or h else f"{m:02d}:{s:02d}"


def _parse_ts(value: str) -> float | None:
    match = re.match(r"^\s*(?P<ts>(?:\d{1,2}:)?\d{1,2}:\d{2})\b", value)
    if not match:
        return None
    parts = [int(part) for part in match.group("ts").split(":")]
    if len(parts) == 2:
        return float(parts[0] * 60 + parts[1])
    if len(parts) == 3:
        return float(parts[0] * 3600 + parts[1] * 60 + parts[2])
    return None


def _join_fragments(fragments: list[str]) -> str:
    end_punctuation = set("。！？!?；;，,、：:\"'）)]}》」』")
    text = ""
    for fragment in fragments:
        fragment = fragment.strip()
        if not fragment:
            continue
        if not text:
            text = fragment
        elif text[-1] in end_punctuation:
            text += fragment
        else:
            text += f"，{fragment}"
    return text


def _pipeline_input_path(episode_dir: Path, filename: str) -> Path:
    preferred = episode_dir / PIPELINE_DIRNAME / filename
    if preferred.exists():
        return preferred
    legacy = episode_dir / filename
    if legacy.exists():
        return legacy
    return preferred


def _load_metadata(episode_dir: Path) -> dict:
    path = episode_dir / "metadata.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_optional_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def _find_audio(episode_dir: Path, metadata: dict) -> Path | None:
    audio_path = metadata.get("audio_path")
    if audio_path:
        candidate = Path(str(audio_path)).expanduser()
        if candidate.exists():
            return candidate
        candidate = episode_dir / str(audio_path)
        if candidate.exists():
            return candidate

    for ext in AUDIO_EXTENSIONS:
        candidate = episode_dir / f"audio{ext}"
        if candidate.exists():
            return candidate
    for child in episode_dir.iterdir():
        if child.is_file() and child.suffix.lower() in AUDIO_EXTENSIONS:
            return child
    return None


def _asset_src(path: Path | None, episode_dir: Path) -> str:
    if path is None:
        return ""
    try:
        return quote(path.resolve().relative_to(episode_dir.resolve()).as_posix())
    except ValueError:
        return path.resolve().as_uri()


def _format_duration(value: object) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, str) and ":" in value:
        return value
    if not isinstance(value, (int, float, str)):
        return str(value)
    try:
        return _fmt_ts(float(value), force_hours=True)
    except (TypeError, ValueError):
        return str(value)


def _format_local_date(value: object) -> str:
    if value is None or value == "":
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        date_match = re.match(r"^(\d{4}-\d{2}-\d{2})", text)
        return date_match.group(1) if date_match else text
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone()
    return parsed.date().isoformat()


def _inline_markdown(text: str) -> str:
    escaped = html.escape(text, quote=True)

    def link_repl(match: re.Match[str]) -> str:
        label = match.group(1)
        href = match.group(2)
        if not re.match(r"^(https?://|mailto:|#)", href):
            return match.group(0)
        return f'<a href="{href}" target="_blank" rel="noopener noreferrer">{label}</a>'

    escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link_repl, escaped)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    return escaped


def markdown_to_html(markdown: str) -> str:
    if not markdown.strip():
        return EMPTY_STATE

    output: list[str] = []
    paragraph: list[str] = []
    list_stack: list[int] = []

    def flush_paragraph() -> None:
        if paragraph:
            output.append(f"<p>{'<br>'.join(paragraph)}</p>")
            paragraph.clear()

    def close_lists(to_level: int = 0) -> None:
        flush_paragraph()
        while len(list_stack) > to_level:
            output.append("</li></ul>")
            list_stack.pop()

    for raw_line in markdown.splitlines():
        if not raw_line.strip():
            flush_paragraph()
            continue

        heading = re.match(r"^(#{1,3})\s+(.+)$", raw_line)
        if heading:
            close_lists()
            level = len(heading.group(1))
            output.append(f"<h{level}>{_inline_markdown(heading.group(2).strip())}</h{level}>")
            continue

        item = re.match(r"^(\s*)(?:[-*+]|\d+\.)\s+(.+)$", raw_line)
        if item:
            flush_paragraph()
            level = len(item.group(1).replace("\t", "  ")) // 2
            text = _inline_markdown(item.group(2).strip())
            while len(list_stack) > level + 1:
                output.append("</li></ul>")
                list_stack.pop()
            if len(list_stack) == level + 1:
                output.append("</li>")
            while len(list_stack) < level + 1:
                output.append("<ul>")
                list_stack.append(len(list_stack))
            output.append(f"<li>{text}")
            continue

        quote_line = re.match(r"^>\s*(.+)$", raw_line)
        if quote_line:
            close_lists()
            output.append(f"<blockquote>{_inline_markdown(quote_line.group(1).strip())}</blockquote>")
            continue

        paragraph.append(_inline_markdown(raw_line.strip()))

    close_lists()
    return "\n".join(output)


def looks_like_html_fragment(text: str) -> bool:
    return bool(re.search(r"</?(?:p|span|br|strong|b|em|i|a|ul|ol|li)\b", text, re.IGNORECASE))


def _is_safe_href(value: str) -> bool:
    return bool(re.match(r"^(https?://|mailto:|#)", value))


class SafeHtmlRenderer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag not in ALLOWED_HTML_TAGS:
            return

        rendered_attrs = []
        for name, value in attrs:
            name = name.lower()
            value = "" if value is None else value
            if name not in ALLOWED_HTML_ATTRS.get(tag, set()):
                continue
            if tag == "a" and name == "href" and not _is_safe_href(value):
                continue
            if tag == "a" and name == "class":
                allowed_classes = [
                    item for item in value.split()
                    if re.fullmatch(r"[A-Za-z0-9_-]+", item)
                ]
                if not allowed_classes:
                    continue
                value = " ".join(allowed_classes)
            rendered_attrs.append(f'{name}="{html.escape(value, quote=True)}"')

        attr_text = f" {' '.join(rendered_attrs)}" if rendered_attrs else ""
        if tag in VOID_HTML_TAGS:
            self.parts.append(f"<{tag}{attr_text}>")
        else:
            self.parts.append(f"<{tag}{attr_text}>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in ALLOWED_HTML_TAGS and tag not in VOID_HTML_TAGS:
            self.parts.append(f"</{tag}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_data(self, data: str) -> None:
        self.parts.append(html.escape(data, quote=False))

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")

    def get_html(self) -> str:
        return "".join(self.parts).strip() or EMPTY_STATE


def sanitize_html_fragment(fragment: str) -> str:
    parser = SafeHtmlRenderer()
    parser.feed(fragment)
    parser.close()
    return parser.get_html()


def render_rich_text(text: str) -> str:
    if not text.strip():
        return EMPTY_STATE
    if looks_like_html_fragment(text):
        return sanitize_html_fragment(text)
    return markdown_to_html(text)


def parse_mindmap_markdown(markdown: str) -> dict:
    title = "Mindmap"
    root = {"title": title, "children": []}
    stack: list[tuple[int, dict]] = [(-1, root)]

    for raw_line in markdown.splitlines():
        heading = re.match(r"^#\s+(.+)$", raw_line)
        if heading and not root["children"]:
            title = heading.group(1).strip()
            root["title"] = title
            continue

        item = re.match(r"^(\s*)[-*+]\s+(.+)$", raw_line)
        if not item:
            continue

        indent = len(item.group(1).replace("\t", "  "))
        level = indent // 2
        node = {"title": item.group(2).strip(), "children": []}
        while stack and stack[-1][0] >= level:
            stack.pop()
        if not stack:
            stack = [(-1, root)]
        stack[-1][1]["children"].append(node)
        stack.append((level, node))

    return root


def _wrap_svg_text(text: str, max_chars: int) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return [text]
    lines = []
    current = ""
    for char in text:
        current += char
        if len(current) >= max_chars:
            lines.append(current)
            current = ""
    if current:
        lines.append(current)
    return lines[:3]


def _svg_text_lines(lines: list[str], x: float, y: float, class_name: str) -> str:
    line_height = 14
    start_y = y - ((len(lines) - 1) * line_height / 2)
    return "\n".join(
        f'<text class="{class_name}" x="{x:.1f}" y="{start_y + idx * line_height:.1f}">{html.escape(line)}</text>'
        for idx, line in enumerate(lines)
    )


def _split_mindmap_title(title: str) -> tuple[str, float | None, str]:
    stripped = re.sub(r"\s+", " ", title).strip()
    match = re.match(
        r"^(?:\[(?P<bracket>(?:\d{1,2}:)?\d{1,2}:\d{2})\]|(?P<plain>(?:\d{1,2}:)?\d{1,2}:\d{2}))\s*(?P<label>.*)$",
        stripped,
    )
    if not match:
        return stripped, None, ""
    timestamp_text = match.group("bracket") or match.group("plain")
    seconds = _parse_ts(timestamp_text)
    if seconds is None:
        return stripped, None, ""
    label = match.group("label").strip() or stripped
    return label, seconds, timestamp_text


def _svg_timestamp(timestamp_text: str, x: float, y: float) -> str:
    if not timestamp_text:
        return ""
    width = max(46, len(timestamp_text) * 7 + 14)
    return f"""
              <rect class="mindmap-svg-timestamp-bg" x="{x:.1f}" y="{y - 12:.1f}" width="{width:.1f}" height="20" rx="10"/>
              <text class="mindmap-svg-timestamp" x="{x + width / 2:.1f}" y="{y - 2:.1f}">{html.escape(timestamp_text)}</text>"""


def _collapse_hotspot(node_id: str, x: float, y: float, has_children: str) -> str:
    if has_children != "true":
        return ""
    return f"""
              <g class="mindmap-collapse-hotspot" data-node-id="{node_id}" tabindex="0" role="button" aria-label="Expand or collapse node">
                <circle class="mindmap-collapse-hit" cx="{x:.1f}" cy="{y:.1f}" r="12"/>
                <text class="mindmap-collapse-icon" x="{x:.1f}" y="{y:.1f}"></text>
              </g>"""


def _mindmap_max_chars(depth: int) -> int:
    del depth
    return 10_000


def _mindmap_timestamp_width(timestamp_text: str) -> int:
    return max(0, len(timestamp_text) * 7 + 24) if timestamp_text else 0


def _mindmap_line_width(text: str) -> int:
    width = 0
    for char in text:
        width += 7 if char.isascii() else 13
    return width


def _mindmap_text_width(lines: list[str], timestamp_text: str) -> int:
    timestamp_width = _mindmap_timestamp_width(timestamp_text)
    max_line_width = max(_mindmap_line_width(line) for line in lines)
    return max(92, max_line_width + timestamp_width + 34)


def render_mindmap_svg(tree: dict) -> tuple[str, int, int]:
    nodes: list[dict] = []
    links: list[tuple[dict, dict]] = []
    leaf_cursor = 0.0
    node_index = 0
    min_leaf_gap = 24
    top_padding = 30
    child_x_gap = 86

    def layout_node(node: dict, depth: int, parent: dict | None, branch_index: int) -> dict:
        nonlocal leaf_cursor, node_index
        node_id = f"node-{node_index}"
        node_index += 1
        raw_title = str(node.get("title", ""))
        label, timestamp, timestamp_text = _split_mindmap_title(raw_title)
        lines = _wrap_svg_text(label, _mindmap_max_chars(depth))
        visual_width = _mindmap_text_width(lines, timestamp_text)
        visual_height = 34 if depth == 0 else 16 + len(lines) * 14
        current = {
            "id": node_id,
            "parent_id": parent["id"] if parent is not None else "",
            "raw_title": raw_title,
            "title": label,
            "timestamp": timestamp,
            "timestamp_text": timestamp_text,
            "visual_width": visual_width,
            "visual_height": visual_height,
            "children": [],
            "depth": depth,
            "x": 0.0,
            "y": 0.0,
            "color": MINDMAP_COLORS[branch_index % len(MINDMAP_COLORS)],
        }
        nodes.append(current)
        if parent is not None:
            links.append((parent, current))

        children = node.get("children", [])
        if children:
            child_layouts = [
                layout_node(child, depth + 1, current, idx if depth == 0 else branch_index)
                for idx, child in enumerate(children)
            ]
            current["children"] = child_layouts
            current["y"] = sum(child["y"] for child in child_layouts) / len(child_layouts)
        else:
            current["y"] = top_padding + leaf_cursor
            leaf_cursor += max(min_leaf_gap, visual_height + 2)
        return current

    root = layout_node(tree, 0, None, 0)

    def assign_x(node: dict, x: float) -> None:
        node["x"] = x
        child_x = x + float(node["visual_width"]) + child_x_gap
        for child in node.get("children", []):
            assign_x(child, child_x)

    assign_x(root, 68.0)

    width = max(860, int(max(node["x"] + node["visual_width"] for node in nodes) + 54))
    height = max(420, int(leaf_cursor + top_padding * 2))

    link_svg = []
    for parent, child in links:
        start_x = parent["x"] + parent["visual_width"] + 18
        start_y = parent["y"]
        end_x = child["x"] - 16
        end_y = child["y"]
        curve = max(36, (end_x - start_x) * 0.45)
        link_svg.append(
            f'<path class="mindmap-branch-line" data-node-id="{child["id"]}" data-parent-id="{parent["id"]}" data-depth="{child["depth"]}" d="M {start_x:.1f} {start_y:.1f} C {start_x + curve:.1f} {start_y:.1f}, {end_x - curve:.1f} {end_y:.1f}, {end_x:.1f} {end_y:.1f}" stroke="{child["color"]}"/>'
        )

    node_svg = []
    for node in nodes:
        depth = int(node["depth"])
        color = str(node["color"])
        node_id = str(node["id"])
        parent_id = str(node["parent_id"])
        timestamp = node.get("timestamp")
        timestamp_text = str(node.get("timestamp_text") or "")
        timestamp_attrs = f' data-timestamp="{float(timestamp):.3f}" data-timestamp-label="{html.escape(timestamp_text, quote=True)}"' if timestamp is not None else ""
        layout_attrs = f' data-x="{float(node["x"]):.1f}" data-y="{float(node["y"]):.1f}" data-visual-width="{float(node["visual_width"]):.1f}" data-visual-height="{float(node["visual_height"]):.1f}"'
        has_children = "true" if node.get("children") else "false"
        interactive_attrs = f' tabindex="0" role="button" aria-label="Seek to {html.escape(timestamp_text, quote=True)}"' if timestamp is not None else ""
        node_classes = "mindmap-svg-node"
        if has_children == "true":
            node_classes += " has-children"
        if timestamp is not None:
            node_classes += " is-seekable"
        if depth == 0:
            lines = _wrap_svg_text(str(node["title"]), _mindmap_max_chars(depth))
            text_x = node["x"]
            text_y = node["y"] - 10
            timestamp_svg = _svg_timestamp(timestamp_text, text_x, text_y - 20)
            label_x = text_x
            if timestamp_text:
                label_x += max(56, len(timestamp_text) * 7 + 24)
            hotspot = _collapse_hotspot(node_id, node["x"] + float(node["visual_width"]) + 18, node["y"], has_children)
            node_svg.append(f"""
            <g class="{node_classes} mindmap-svg-root" data-node-id="{node_id}" data-parent-id="{parent_id}" data-depth="{depth}" data-has-children="{has_children}"{layout_attrs}{timestamp_attrs}{interactive_attrs}>
              <circle cx="{node["x"] - 16:.1f}" cy="{node["y"]:.1f}" r="4.5" fill="{color}"/>
              {timestamp_svg}
              {_svg_text_lines(lines, label_x, text_y, "mindmap-svg-root-text")}
              {hotspot}
            </g>""")
            continue

        max_chars = _mindmap_max_chars(depth)
        lines = _wrap_svg_text(str(node["title"]), max_chars)
        timestamp_width = _mindmap_timestamp_width(timestamp_text)
        text_width = int(node["visual_width"])
        text_height = 16 + len(lines) * 14
        y = float(node["y"])
        x = float(node["x"])
        if depth <= 2:
            timestamp_svg = _svg_timestamp(timestamp_text, x + 10, y + 3)
            label_x = x + 10 + timestamp_width
            hotspot = _collapse_hotspot(node_id, x + text_width + 18, y + 3, has_children)
            node_svg.append(f"""
            <g class="{node_classes}" data-node-id="{node_id}" data-parent-id="{parent_id}" data-depth="{depth}" data-has-children="{has_children}"{layout_attrs}{timestamp_attrs}{interactive_attrs}>
              <circle cx="{x - 16:.1f}" cy="{y:.1f}" r="4.5" fill="{color}"/>
              <rect class="mindmap-svg-label-bg" x="{x:.1f}" y="{y - text_height / 2:.1f}" width="{text_width:.1f}" height="{text_height:.1f}" rx="9"/>
              {timestamp_svg}
              {_svg_text_lines(lines, label_x, y + 3, "mindmap-svg-label")}
              {hotspot}
            </g>""")
        else:
            timestamp_svg = _svg_timestamp(timestamp_text, x, y + 3)
            label_x = x + timestamp_width
            hotspot = _collapse_hotspot(node_id, x + text_width + 18, y + 3, has_children)
            node_svg.append(f"""
            <g class="{node_classes}" data-node-id="{node_id}" data-parent-id="{parent_id}" data-depth="{depth}" data-has-children="{has_children}"{layout_attrs}{timestamp_attrs}{interactive_attrs}>
              <circle cx="{x - 16:.1f}" cy="{y:.1f}" r="4.5" fill="{color}"/>
              {timestamp_svg}
              {_svg_text_lines(lines, label_x, y + 3, "mindmap-svg-leaf")}
              {hotspot}
            </g>""")

    svg = f"""
    <svg class="mindmap-svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" data-width="{width}" data-height="{height}" role="img" aria-label="{html.escape(str(tree.get("title") or "Mindmap"))}">
      <g id="mindmapViewport">
        {''.join(link_svg)}
        {''.join(node_svg)}
      </g>
    </svg>"""
    return svg, width, height


def render_mindmap_component(markdown: str) -> str:
    if not markdown.strip():
        return EMPTY_STATE
    tree = parse_mindmap_markdown(markdown)
    title = str(tree.get("title") or "Mindmap")
    svg, width, height = render_mindmap_svg(tree)
    return f"""
    <div class="mindmap-component" id="mindmapComponent">
      <div class="mindmap-toolbar">
        <div class="mindmap-view-toggle" aria-hidden="true">
          <span class="mindmap-toggle-button">☰</span>
          <span class="mindmap-toggle-button active">⌘</span>
        </div>
        <div class="mindmap-controls" data-width="{width}" data-height="{height}">
          <button class="mindmap-control-button" id="mindmapZoomIn" type="button" aria-label="Zoom in">＋</button>
          <button class="mindmap-control-button" id="mindmapZoomOut" type="button" aria-label="Zoom out">−</button>
          <button class="mindmap-control-button" id="mindmapFit" type="button" aria-label="Fit">Fit</button>
          <button class="mindmap-control-button" id="mindmapZoomButton" type="button" aria-pressed="false" aria-label="Fullscreen">⛶</button>
        </div>
      </div>
      <div class="mindmap-canvas" id="mindmapCanvas" data-title="{html.escape(title, quote=True)}">
        {svg}
      </div>
    </div>"""


def _load_transcript_from_raw(
    episode_dir: Path,
    max_group_seconds: float,
    max_group_chars: int,
) -> tuple[list[dict], str] | None:
    del max_group_seconds, max_group_chars
    raw_path = _pipeline_input_path(episode_dir, "transcript_raw.jsonl")
    if not raw_path.exists():
        return None

    corrections_path = _pipeline_input_path(episode_dir, "corrections.yaml")
    lexicon_path = _pipeline_input_path(episode_dir, "lexicon.yaml")
    segments = render_segments(
        load_segments_jsonl(raw_path),
        corrections=load_corrections(corrections_path if corrections_path.exists() else None),
        lexicon=load_lexicon(lexicon_path if lexicon_path.exists() else None),
    )
    transcript = []
    for segment in segments:
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        start = float(segment.get("start", 0.0))
        end = float(segment.get("end", start))
        transcript.append({
            "start": start,
            "end": end,
            "timestamp": _fmt_ts(start, force_hours=True),
            "speaker": str(segment.get("speaker") or "unknown"),
            "text": text,
        })
    return transcript, str(raw_path)


def _load_transcript_from_txt(episode_dir: Path) -> tuple[list[dict], str]:
    transcript_path = episode_dir / "transcript.txt"
    text = _read_optional_text(transcript_path)
    if not text:
        return [], "missing"

    transcript = []
    blocks = re.split(r"\n\s*\n", text)
    for idx, block in enumerate(blocks):
        block = " ".join(line.strip() for line in block.splitlines() if line.strip())
        if not block:
            continue
        start = _parse_ts(block)
        if start is None:
            start = float(idx)
        body = re.sub(r"^\s*(?:\d{1,2}:)?\d{1,2}:\d{2}\s*:?\s*", "", block)
        speaker = "unknown"
        speaker_match = re.match(r"^([A-Za-z0-9_-]+)\s*[:：]\s*(.+)$", body)
        if speaker_match:
            speaker = speaker_match.group(1)
            body = speaker_match.group(2)
        transcript.append({
            "start": start,
            "end": start,
            "timestamp": _fmt_ts(start, force_hours=True),
            "speaker": speaker,
            "text": body,
        })
    return transcript, str(transcript_path)


def load_transcript(
    episode_dir: Path,
    max_group_seconds: float = DEFAULT_MAX_GROUP_SECONDS,
    max_group_chars: int = DEFAULT_MAX_GROUP_CHARS,
) -> tuple[list[dict], str]:
    from_raw = _load_transcript_from_raw(episode_dir, max_group_seconds, max_group_chars)
    if from_raw is not None:
        return from_raw
    return _load_transcript_from_txt(episode_dir)


def _render_transcript(transcript: list[dict]) -> str:
    if not transcript:
        return EMPTY_STATE

    items = []
    for index, item in enumerate(transcript):
        text = str(item.get("text", "")).strip()
        speaker = str(item.get("speaker", "unknown"))
        start = float(item.get("start", 0.0))
        end = float(item.get("end", start))
        timestamp = str(item.get("timestamp") or _fmt_ts(start, force_hours=True))
        searchable = f"{timestamp} {speaker} {text}".lower()
        items.append(f"""
        <article class="lyric-line transcript-item" data-index="{index}" data-start="{start:.3f}" data-end="{end:.3f}" data-text="{html.escape(searchable, quote=True)}">
          <button class="timestamp" type="button" data-seek="{start:.3f}">{html.escape(timestamp)}</button>
          <div class="transcript-body">
            <div class="speaker">{html.escape(speaker)}</div>
            <p>{html.escape(text)}</p>
          </div>
        </article>""")
    return "\n".join(items)


def _render_header(metadata: dict, cover_src: str) -> str:
    title = str(metadata.get("title") or "Untitled Episode")
    podcast = str(metadata.get("podcast_title") or metadata.get("podcast") or "Podcast")
    published_at = _format_local_date(metadata.get("published_at") or metadata.get("pub_date"))
    duration = _format_duration(metadata.get("duration"))
    parts = [part for part in [podcast, published_at, duration] if part]
    cover = (
        f'<img class="cover" src="{html.escape(cover_src, quote=True)}" alt="Podcast cover">'
        if cover_src else '<div class="cover cover-fallback">Podcast</div>'
    )
    return f"""
    <header class="hero">
      {cover}
      <div class="hero-copy">
        <p class="eyebrow">Podcast Episode</p>
        <h1>{html.escape(title)}</h1>
        <p class="meta">{html.escape(" · ".join(parts))}</p>
      </div>
      <div class="hero-actions">
        <button class="theme-toggle" id="themeToggle" type="button" aria-pressed="false" aria-label="Toggle light or dark mode">
          <span class="theme-toggle-icon" aria-hidden="true">◐</span>
          <span class="theme-toggle-text">System</span>
        </button>
      </div>
    </header>"""


def render_html_document(
    *,
    metadata: dict,
    audio_src: str,
    cover_src: str,
    transcript_html: str,
    shownotes_html: str,
    mindmap_html: str,
    insights_html: str,
) -> str:
    title = html.escape(str(metadata.get("title") or "Podcast Episode"))
    player = (
        f"""
        <div class="player-shell">
          <audio id="audio" preload="metadata" src="{html.escape(audio_src, quote=True)}"></audio>
          <button class="player-play-button" id="playerPlay" type="button" aria-label="Play">▶</button>
          <span class="player-time" id="playerCurrent">00:00</span>
          <input class="player-progress" id="playerProgress" type="range" min="0" max="1000" value="0" step="1" aria-label="Playback progress">
          <span class="player-time" id="playerDuration">--:--</span>
          <div class="volume-control">
            <button class="volume-button" id="playerVolumeButton" type="button" aria-label="Volume">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M4 9v6h4l5 4V5L8 9H4z"></path>
                <path d="M16 8.5c1.1 1.1 1.7 2.2 1.7 3.5s-.6 2.4-1.7 3.5"></path>
              </svg>
            </button>
            <div class="volume-popover">
              <input class="player-volume" id="playerVolume" type="range" min="0" max="100" value="50" step="1" aria-label="Volume">
            </div>
          </div>
          <div class="playback-rate-control" id="playbackRateControl">
            <button class="playback-rate-button" id="playbackRateButton" type="button" aria-haspopup="listbox" aria-expanded="false">
              <span>Speed</span>
              <strong id="playbackRateLabel">1x</strong>
            </button>
            <div class="playback-rate-popover" id="playbackRatePopover" role="listbox" aria-label="Playback speed">
              <button class="playback-rate-option" type="button" role="option" data-rate="2">2x</button>
              <button class="playback-rate-option" type="button" role="option" data-rate="1.75">1.75x</button>
              <button class="playback-rate-option" type="button" role="option" data-rate="1.5">1.5x</button>
              <button class="playback-rate-option" type="button" role="option" data-rate="1.25">1.25x</button>
              <button class="playback-rate-option active" type="button" role="option" data-rate="1" aria-selected="true">1x</button>
              <button class="playback-rate-option" type="button" role="option" data-rate="0.75">0.75x</button>
            </div>
          </div>
        </div>"""
        if audio_src else '<div class="missing-audio">No local audio file found. The transcript remains available.</div>'
    )
    header = _render_header(metadata, cover_src)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <script>
    (() => {{
      try {{
        const savedTheme = localStorage.getItem('podcast-html-theme');
        if (savedTheme === 'light' || savedTheme === 'dark') {{
          document.documentElement.dataset.theme = savedTheme;
        }}
      }} catch (error) {{}}
    }})();
  </script>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f6fb;
      --panel: #ffffff;
      --panel-muted: #f8fafc;
      --text: #172033;
      --muted: #667085;
      --border: #e2e8f0;
      --accent: #2563eb;
      --accent-soft: #dbeafe;
      --shadow: 0 18px 55px rgba(15, 23, 42, 0.08);
      --hero-bg: rgba(244, 246, 251, 0.92);
      --player-bg: rgba(255, 255, 255, 0.92);
      --panel-header-bg: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
      --input-bg: #ffffff;
      --hover-bg: #f8fafc;
      --timestamp-bg: #eff6ff;
      --active-border: #93c5fd;
      --button-bg: #ffffff;
      --tab-active-bg: #0f172a;
      --tab-active-text: #ffffff;
      --code-bg: #f1f5f9;
      --mindmap-bg: #ffffff;
      --mindmap-toolbar-bg: rgba(248, 250, 252, 0.92);
      --mindmap-canvas-bg: #f8fafc;
      --mindmap-control-bg: rgba(255, 255, 255, 0.86);
      --mindmap-control-hover-bg: #e0ecff;
      --mindmap-control-text: #334155;
      --mindmap-label-bg: rgba(255, 255, 255, 0.9);
      --mindmap-label-border: rgba(148, 163, 184, 0.36);
      --mindmap-label-text: #1e293b;
      --mindmap-leaf-text: #334155;
      --mindmap-root-text: #0f172a;
    }}
    @media (prefers-color-scheme: dark) {{
      :root:not([data-theme="light"]) {{
        color-scheme: dark;
        --bg: #0f172a;
        --panel: #111827;
        --panel-muted: #1e293b;
        --text: #e5e7eb;
        --muted: #94a3b8;
        --border: #334155;
        --accent: #60a5fa;
        --accent-soft: rgba(37, 99, 235, 0.24);
        --shadow: 0 18px 55px rgba(0, 0, 0, 0.28);
        --hero-bg: rgba(15, 23, 42, 0.88);
        --player-bg: rgba(15, 23, 42, 0.9);
        --panel-header-bg: linear-gradient(180deg, #111827 0%, #1e293b 100%);
        --input-bg: #0f172a;
        --hover-bg: rgba(30, 41, 59, 0.72);
        --timestamp-bg: rgba(37, 99, 235, 0.18);
        --active-border: #3b82f6;
        --button-bg: #1e293b;
        --tab-active-bg: #dbeafe;
        --tab-active-text: #0f172a;
        --code-bg: #1e293b;
        --mindmap-bg: #111827;
        --mindmap-toolbar-bg: rgba(15, 23, 42, 0.78);
        --mindmap-canvas-bg: #0f172a;
        --mindmap-control-bg: rgba(30, 41, 59, 0.78);
        --mindmap-control-hover-bg: rgba(96, 165, 250, 0.22);
        --mindmap-control-text: #cbd5e1;
        --mindmap-label-bg: rgba(15, 23, 42, 0.68);
        --mindmap-label-border: rgba(148, 163, 184, 0.24);
        --mindmap-label-text: #dbeafe;
        --mindmap-leaf-text: #cbd5e1;
        --mindmap-root-text: #f8fafc;
      }}
    }}
    :root[data-theme="dark"] {{
      color-scheme: dark;
      --bg: #0f172a;
      --panel: #111827;
      --panel-muted: #1e293b;
      --text: #e5e7eb;
      --muted: #94a3b8;
      --border: #334155;
      --accent: #60a5fa;
      --accent-soft: rgba(37, 99, 235, 0.24);
      --shadow: 0 18px 55px rgba(0, 0, 0, 0.28);
      --hero-bg: rgba(15, 23, 42, 0.88);
      --player-bg: rgba(15, 23, 42, 0.9);
      --panel-header-bg: linear-gradient(180deg, #111827 0%, #1e293b 100%);
      --input-bg: #0f172a;
      --hover-bg: rgba(30, 41, 59, 0.72);
      --timestamp-bg: rgba(37, 99, 235, 0.18);
      --active-border: #3b82f6;
      --button-bg: #1e293b;
      --tab-active-bg: #dbeafe;
      --tab-active-text: #0f172a;
      --code-bg: #1e293b;
      --mindmap-bg: #111827;
      --mindmap-toolbar-bg: rgba(15, 23, 42, 0.78);
      --mindmap-canvas-bg: #0f172a;
      --mindmap-control-bg: rgba(30, 41, 59, 0.78);
      --mindmap-control-hover-bg: rgba(96, 165, 250, 0.22);
      --mindmap-control-text: #cbd5e1;
      --mindmap-label-bg: rgba(15, 23, 42, 0.68);
      --mindmap-label-border: rgba(148, 163, 184, 0.24);
      --mindmap-label-text: #dbeafe;
      --mindmap-leaf-text: #cbd5e1;
      --mindmap-root-text: #f8fafc;
    }}
    :root[data-theme="light"] {{
      color-scheme: light;
    }}
    * {{ box-sizing: border-box; }}
    html {{
      height: 100%;
      overflow: hidden;
    }}
    body {{
      height: 100%;
      margin: 0;
      overflow: hidden;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", sans-serif;
      line-height: 1.65;
    }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .page {{
      width: 100%;
      max-width: none;
      height: 100vh;
      margin: 0;
      padding: 20px 24px 118px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}
    .hero {{
      --cover-size: 54px;
      flex: 0 0 auto;
      z-index: 25;
      display: grid;
      grid-template-columns: var(--cover-size) minmax(0, 1fr) auto;
      gap: 14px;
      align-items: center;
      margin: 0 0 18px;
      padding: 4px 0;
      background: transparent;
      border: 0;
      border-radius: 0;
      box-shadow: none;
      backdrop-filter: none;
    }}
    .cover {{
      width: var(--cover-size);
      height: var(--cover-size);
      border-radius: 14px;
      object-fit: cover;
      box-shadow: var(--shadow);
      background: #111827;
      color: white;
    }}
    .cover-fallback {{
      display: grid;
      place-items: center;
      padding: 16px;
      font-weight: 700;
      text-align: center;
    }}
    .hero-copy {{
      min-width: 0;
      height: var(--cover-size);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}
    .hero-actions {{
      display: flex;
      justify-content: flex-end;
      align-items: center;
    }}
    .theme-toggle {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 8px 12px;
      background: var(--button-bg);
      color: var(--text);
      font: inherit;
      font-size: 13px;
      cursor: pointer;
      box-shadow: 0 8px 22px rgba(15, 23, 42, 0.08);
    }}
    .theme-toggle:hover {{ border-color: var(--accent); }}
    .theme-toggle-icon {{ font-size: 15px; line-height: 1; }}
    .eyebrow {{
      display: none;
      margin: 0 0 8px;
      color: var(--accent);
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    h1 {{
      margin: 0;
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: clamp(26px, 2.9vw, 34px);
      line-height: 1;
    }}
    .meta {{
      color: var(--muted);
      margin: 0;
      font-size: 16px;
      line-height: 1;
    }}
    .player-card {{
      position: fixed;
      left: 24px;
      right: 24px;
      bottom: 18px;
      z-index: 40;
      padding: 12px 16px;
      margin: 0;
      background: var(--player-bg);
      border: 1px solid var(--border);
      border-radius: 20px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(12px);
    }}
    .player-shell {{
      display: grid;
      grid-template-columns: auto auto minmax(160px, 1fr) auto auto auto;
      gap: 12px;
      align-items: center;
    }}
    audio {{ display: none; }}
    .player-play-button {{
      display: inline-grid;
      place-items: center;
      width: 38px;
      height: 38px;
      border: 1px solid var(--border);
      border-radius: 999px;
      background: var(--tab-active-bg);
      color: var(--tab-active-text);
      font: inherit;
      font-size: 15px;
      font-weight: 750;
      line-height: 1;
      cursor: pointer;
      box-shadow: 0 10px 28px rgba(15, 23, 42, 0.16);
    }}
    .player-play-button:hover {{
      transform: translateY(-1px);
    }}
    .player-time {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }}
    .player-progress {{
      --progress-percent: 0%;
      width: 100%;
      height: 34px;
      margin: 0;
      appearance: none;
      background: transparent;
      cursor: pointer;
    }}
    .player-progress::-webkit-slider-runnable-track {{
      height: 8px;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--accent) 0 var(--progress-percent), var(--panel-muted) var(--progress-percent) 100%);
      border: 1px solid var(--border);
    }}
    .player-progress::-webkit-slider-thumb {{
      appearance: none;
      width: 18px;
      height: 18px;
      margin-top: -6px;
      border: 3px solid var(--player-bg);
      border-radius: 999px;
      background: var(--accent);
      box-shadow: 0 6px 16px rgba(37, 99, 235, 0.24);
    }}
    .player-progress::-moz-range-track {{
      height: 8px;
      border-radius: 999px;
      background: var(--panel-muted);
      border: 1px solid var(--border);
    }}
    .player-progress::-moz-range-progress {{
      height: 8px;
      border-radius: 999px;
      background: var(--accent);
    }}
    .player-progress::-moz-range-thumb {{
      width: 14px;
      height: 14px;
      border: 3px solid var(--player-bg);
      border-radius: 999px;
      background: var(--accent);
      box-shadow: 0 6px 16px rgba(37, 99, 235, 0.24);
    }}
    .player-progress:focus-visible {{
      outline: none;
    }}
    .player-progress:focus-visible::-webkit-slider-runnable-track {{
      box-shadow: 0 0 0 3px var(--accent-soft);
    }}
    .volume-control {{
      position: relative;
      display: inline-grid;
      place-items: center;
      width: 38px;
      height: 38px;
    }}
    .volume-control::before {{
      content: "";
      position: absolute;
      left: 50%;
      bottom: 100%;
      width: 58px;
      height: 18px;
      transform: translateX(-50%);
    }}
    .volume-button {{
      display: inline-grid;
      place-items: center;
      width: 34px;
      height: 34px;
      border: 1px solid var(--border);
      border-radius: 999px;
      background: var(--button-bg);
      color: var(--muted);
      cursor: pointer;
    }}
    .volume-button:hover,
    .volume-control:focus-within .volume-button {{
      color: var(--text);
      border-color: var(--accent);
    }}
    .volume-button svg {{
      width: 18px;
      height: 18px;
      fill: currentColor;
    }}
    .volume-button svg path + path {{
      fill: none;
      stroke: currentColor;
      stroke-width: 1.8;
      stroke-linecap: round;
    }}
    .volume-button.is-muted svg path + path {{
      display: none;
    }}
    .volume-popover {{
      position: absolute;
      left: 50%;
      bottom: calc(100% + 8px);
      z-index: 55;
      display: grid;
      place-items: center;
      width: 46px;
      height: 144px;
      padding: 12px 6px;
      border: 1px solid var(--border);
      border-radius: 18px;
      background: var(--player-bg);
      box-shadow: var(--shadow);
      opacity: 0;
      pointer-events: none;
      transform: translate(-50%, 8px);
      transition: opacity 140ms ease, transform 140ms ease;
      backdrop-filter: blur(12px);
    }}
    .volume-control:hover .volume-popover,
    .volume-control:focus-within .volume-popover {{
      opacity: 1;
      pointer-events: auto;
      transform: translate(-50%, 0);
    }}
    .player-volume {{
      --progress-percent: 50%;
      width: 34px;
      height: 112px;
      margin: 0;
      appearance: auto;
      accent-color: var(--accent);
      cursor: pointer;
      direction: rtl;
      writing-mode: vertical-lr;
    }}
    .player-volume:focus-visible {{
      outline: none;
    }}
    .playback-rate-control {{
      position: relative;
      display: inline-flex;
      white-space: nowrap;
    }}
    .playback-rate-control::before {{
      content: "";
      position: absolute;
      right: 0;
      bottom: 100%;
      width: 100%;
      height: 14px;
    }}
    .playback-rate-button {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      height: 34px;
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 0 12px;
      background: var(--button-bg);
      color: var(--text);
      font: inherit;
      font-size: 13px;
      font-weight: 650;
      cursor: pointer;
      outline: none;
    }}
    .playback-rate-button span {{
      color: var(--muted);
      font-size: 12px;
    }}
    .playback-rate-button strong {{
      min-width: 40px;
      font-weight: 750;
      text-align: right;
    }}
    .playback-rate-button:hover,
    .playback-rate-control.is-open .playback-rate-button,
    .playback-rate-button:focus-visible {{
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-soft);
    }}
    .playback-rate-popover {{
      position: absolute;
      right: 0;
      bottom: calc(100% + 8px);
      z-index: 56;
      display: grid;
      min-width: 108px;
      padding: 8px;
      border: 1px solid var(--border);
      border-radius: 18px;
      background: var(--player-bg);
      box-shadow: var(--shadow);
      opacity: 0;
      pointer-events: none;
      transform: translateY(8px);
      transition: opacity 140ms ease, transform 140ms ease;
      backdrop-filter: blur(12px);
    }}
    .playback-rate-control.is-open .playback-rate-popover {{
      opacity: 1;
      pointer-events: auto;
      transform: translateY(0);
    }}
    .playback-rate-option {{
      border: 0;
      border-radius: 12px;
      padding: 8px 12px;
      background: transparent;
      color: var(--text);
      font: inherit;
      font-size: 14px;
      font-weight: 650;
      text-align: left;
      cursor: pointer;
    }}
    .playback-rate-option:hover,
    .playback-rate-option.active {{
      background: var(--accent);
      color: #ffffff;
    }}
    .keyboard-toast {{
      position: fixed;
      left: 50%;
      top: 50%;
      z-index: 120;
      display: grid;
      place-items: center;
      min-width: 88px;
      height: 88px;
      padding: 0 20px;
      border-radius: 26px;
      background: rgba(15, 23, 42, 0.78);
      color: #ffffff;
      font-size: 34px;
      font-weight: 750;
      line-height: 1;
      box-shadow: 0 24px 80px rgba(15, 23, 42, 0.28);
      opacity: 0;
      pointer-events: none;
      transform: translate(-50%, -50%) scale(0.94);
      transition: opacity 130ms ease, transform 130ms ease;
      backdrop-filter: blur(14px);
    }}
    .keyboard-toast.visible {{
      opacity: 1;
      transform: translate(-50%, -50%) scale(1);
    }}
    .missing-audio {{
      padding: 14px 16px;
      color: var(--muted);
      background: var(--panel-muted);
      border-radius: 14px;
    }}
    .layout {{
      flex: 1 1 auto;
      min-height: 0;
      display: grid;
      grid-template-columns: minmax(340px, 1fr) minmax(0, 2fr);
      gap: 20px;
      align-items: start;
      overflow: hidden;
    }}
    .panel {{
      min-height: 0;
      height: 100%;
      display: flex;
      flex-direction: column;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 24px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .panel-header {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      min-height: 60.45px;
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      background: var(--panel-header-bg);
      flex: 0 0 auto;
    }}
    .panel-header h2 {{
      margin: 0;
      color: var(--text);
      font-size: 13px;
      font-weight: 600;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    .search-input {{
      width: min(320px, 100%);
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 6px 12px;
      background: var(--input-bg);
      color: var(--text);
      font: inherit;
      font-size: 13px;
      line-height: 1.35;
      outline: none;
    }}
    .search-input:focus {{ border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }}
    .transcript-list {{
      flex: 1 1 auto;
      min-height: 0;
      overflow: auto;
      padding: 12px 12px 42vh;
      scroll-behavior: smooth;
      scroll-padding: 12px 0 42%;
    }}
    .transcript-item {{
      display: grid;
      grid-template-columns: 74px 1fr;
      gap: 16px;
      align-items: baseline;
      padding: 10px 14px;
      border-radius: 16px;
      border: 1px solid transparent;
      cursor: pointer;
      opacity: 0.52;
      transition: opacity 160ms ease, background 160ms ease, border-color 160ms ease, transform 160ms ease;
      user-select: text;
    }}
    .transcript-item + .transcript-item {{ margin-top: 2px; }}
    .transcript-item:hover {{
      opacity: 0.88;
      background: var(--hover-bg);
    }}
    .transcript-item.active {{
      background: var(--accent-soft);
      border-color: var(--active-border);
      opacity: 1;
      transform: scale(1.012);
    }}
    .transcript-item.hidden {{ display: none; }}
    .timestamp {{
      align-self: start;
      border: 0;
      border-radius: 999px;
      padding: 7px 9px;
      color: var(--accent);
      background: var(--timestamp-bg);
      font: inherit;
      font-size: 12px;
      font-variant-numeric: tabular-nums;
      cursor: pointer;
    }}
    .speaker {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      margin-bottom: 2px;
      letter-spacing: 0.02em;
    }}
    .transcript-body p {{
      margin: 0;
      font-size: 16px;
      line-height: 1.6;
      transition: font-size 160ms ease, font-weight 160ms ease;
    }}
    .transcript-item.active .transcript-body p {{
      font-size: 19px;
      font-weight: 650;
      line-height: 1.55;
    }}
    .tabs {{
      display: flex;
      gap: 8px;
      min-height: 60.45px;
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      background: var(--panel-header-bg);
      flex: 0 0 auto;
      align-items: center;
    }}
    .tab {{
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 8px 12px;
      background: var(--button-bg);
      color: var(--muted);
      font: inherit;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
    }}
    .tab.active {{ color: var(--tab-active-text); background: var(--tab-active-bg); border-color: var(--tab-active-bg); box-shadow: 0 8px 24px rgba(15, 23, 42, 0.16); }}
    .tab-panel {{ display: none; flex: 1 1 auto; min-height: 0; padding: 22px; overflow: auto; }}
    .tab-panel.active {{ display: block; }}
    #mindmap.tab-panel {{ padding: 0; }}
    #mindmap.tab-panel.active {{ display: flex; }}
    .content h1, .content h2, .content h3 {{ line-height: 1.3; margin: 1.2em 0 0.5em; }}
    .content h1:first-child, .content h2:first-child, .content h3:first-child {{ margin-top: 0; }}
    .content p {{ margin: 0.7em 0; }}
    .content ul {{ padding-left: 1.35em; }}
    .content li {{ margin: 0.36em 0; }}
    .content code {{ background: var(--code-bg); padding: 0.1em 0.35em; border-radius: 6px; }}
    .empty-state {{ color: var(--muted); padding: 18px; background: var(--panel-muted); border-radius: 16px; }}
    .mindmap-component {{
      position: relative;
      display: flex;
      flex: 1 1 auto;
      min-height: 0;
      width: 100%;
      flex-direction: column;
      background: var(--mindmap-bg);
      color: var(--text);
    }}
    .mindmap-component.is-expanded {{
      position: fixed;
      inset: 20px 24px 100px;
      z-index: 70;
      border: 1px solid var(--border);
      border-radius: 24px;
      box-shadow: 0 30px 90px rgba(15, 23, 42, 0.22);
      overflow: hidden;
    }}
    .mindmap-toolbar {{
      position: absolute;
      top: 12px;
      right: 14px;
      z-index: 5;
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      pointer-events: none;
    }}
    .mindmap-view-toggle {{
      display: none;
    }}
    .mindmap-controls {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 4px;
      background: var(--mindmap-control-bg);
      box-shadow: 0 12px 26px rgba(15, 23, 42, 0.12);
      backdrop-filter: blur(12px);
      pointer-events: auto;
    }}
    .mindmap-toggle-button,
    .mindmap-control-button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 34px;
      height: 32px;
      border: 0;
      border-radius: 10px;
      padding: 0 10px;
      background: transparent;
      color: var(--mindmap-control-text);
      font: inherit;
      font-size: 14px;
      cursor: pointer;
    }}
    .mindmap-toggle-button.active,
    .mindmap-control-button:hover {{
      background: var(--mindmap-control-hover-bg);
      color: var(--text);
    }}
    .mindmap-canvas {{
      position: relative;
      flex: 1 1 auto;
      min-height: 0;
      overflow: hidden;
      padding: 0;
      cursor: grab;
      touch-action: none;
      background:
        radial-gradient(circle at 52% 46%, rgba(37, 99, 235, 0.08), transparent 32%),
        var(--mindmap-canvas-bg);
    }}
    .mindmap-canvas.is-panning {{
      cursor: grabbing;
      user-select: none;
    }}
    .mindmap-svg {{
      display: block;
      transform-origin: 0 0;
      will-change: transform;
      user-select: none;
    }}
    .mindmap-branch-line {{
      fill: none;
      stroke-width: 2.2;
      stroke-linecap: round;
      opacity: 0.9;
    }}
    .mindmap-hidden {{ display: none; }}
    .mindmap-svg-node.has-children {{
      outline: none;
    }}
    .mindmap-svg-node.is-seekable {{ cursor: pointer; }}
    .mindmap-svg-node.has-children:focus-visible .mindmap-svg-label-bg {{
      stroke: var(--accent);
      stroke-width: 2;
    }}
    .mindmap-svg-node.is-seekable:hover .mindmap-svg-label-bg {{
      stroke: var(--accent);
    }}
    .mindmap-svg-label-bg {{
      fill: var(--mindmap-label-bg);
      stroke: var(--mindmap-label-border);
      stroke-width: 1;
    }}
    .mindmap-svg-timestamp-bg {{
      fill: var(--timestamp-bg);
      stroke: var(--mindmap-label-border);
      stroke-width: 1;
    }}
    .mindmap-svg-timestamp {{
      fill: var(--accent);
      dominant-baseline: middle;
      text-anchor: middle;
      font-size: 11px;
      font-weight: 650;
      font-variant-numeric: tabular-nums;
      pointer-events: none;
    }}
    .mindmap-svg-label,
    .mindmap-svg-leaf,
    .mindmap-svg-root-text {{
      fill: var(--mindmap-label-text);
      dominant-baseline: middle;
      font-size: 13px;
      letter-spacing: 0.01em;
    }}
    .mindmap-svg-leaf {{
      fill: var(--mindmap-leaf-text);
      font-size: 12px;
    }}
    .mindmap-svg-root-text {{
      fill: var(--mindmap-root-text);
      font-size: 14px;
      font-weight: 650;
    }}
    .mindmap-collapse-icon {{
      fill: var(--muted);
      dominant-baseline: middle;
      text-anchor: middle;
      font-size: 16px;
      font-weight: 700;
      pointer-events: none;
    }}
    .mindmap-collapse-hotspot {{
      cursor: pointer;
      outline: none;
    }}
    .mindmap-collapse-hit {{
      fill: transparent;
      stroke: transparent;
      stroke-width: 1;
    }}
    .mindmap-collapse-hotspot:hover .mindmap-collapse-hit,
    .mindmap-collapse-hotspot:focus-visible .mindmap-collapse-hit {{
      fill: var(--mindmap-control-hover-bg);
      stroke: var(--border);
    }}
    @media (max-width: 900px) {{
      .page {{ padding: 12px 12px 110px; }}
      .hero {{ --cover-size: 48px; padding: 8px 10px; }}
      .cover {{ border-radius: 12px; }}
      .theme-toggle {{ padding: 8px 10px; }}
      .theme-toggle-text {{ display: none; }}
      .layout {{ grid-template-columns: 1fr; }}
      .player-card {{ left: 12px; right: 12px; bottom: 10px; }}
      .player-shell {{ grid-template-columns: auto auto minmax(0, 1fr) auto auto auto; gap: 8px; }}
      .playback-rate-button span {{ display: none; }}
      .transcript-list, .tab-panel {{ max-height: none; }}
      .transcript-list {{ padding: 24px 10px; }}
      .panel-header {{ display: block; }}
      .search-input {{ width: 100%; margin-top: 12px; }}
      .transcript-item {{ grid-template-columns: 68px 1fr; }}
      .mindmap-component.is-expanded {{ inset: 12px 12px 96px; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    {header}
    <section class="player-card" aria-label="Podcast player">
      {player}
    </section>
    <section class="layout">
      <section class="panel transcript-panel" id="transcript">
        <div class="panel-header">
          <h2>Transcript</h2>
          <input id="transcriptSearch" class="search-input" type="search" placeholder="Search transcript">
        </div>
        <div class="transcript-list">
          {transcript_html}
        </div>
      </section>
      <aside class="panel knowledge-panel">
        <div class="tabs" role="tablist" aria-label="Knowledge panel">
          <button class="tab active" type="button" data-tab="shownotes">Shownotes</button>
          <button class="tab" type="button" data-tab="mindmap">Mindmap</button>
          <button class="tab" type="button" data-tab="insights">Insight</button>
        </div>
        <section id="shownotes" class="tab-panel content active">{shownotes_html}</section>
        <section id="mindmap" class="tab-panel content">{mindmap_html}</section>
        <section id="insights" class="tab-panel content">{insights_html}</section>
      </aside>
    </section>
  </main>
  <div class="keyboard-toast" id="keyboardToast" aria-hidden="true"></div>
  <script>
    const audio = document.getElementById('audio');
    const keyboardToast = document.getElementById('keyboardToast');
    const playerPlayButton = document.getElementById('playerPlay');
    const playerCurrent = document.getElementById('playerCurrent');
    const playerDuration = document.getElementById('playerDuration');
    const playerProgress = document.getElementById('playerProgress');
    const playerVolumeButton = document.getElementById('playerVolumeButton');
    const playerVolume = document.getElementById('playerVolume');
    const playbackRateControl = document.getElementById('playbackRateControl');
    const playbackRateButton = document.getElementById('playbackRateButton');
    const playbackRateLabel = document.getElementById('playbackRateLabel');
    const playbackRateOptions = Array.from(document.querySelectorAll('.playback-rate-option[data-rate]'));
    const transcriptList = document.querySelector('.transcript-list');
    const transcriptItems = Array.from(document.querySelectorAll('.transcript-item'));
    const search = document.getElementById('transcriptSearch');
    const mindmapComponent = document.getElementById('mindmapComponent');
    const mindmapZoomButton = document.getElementById('mindmapZoomButton');
    const mindmapCanvas = document.getElementById('mindmapCanvas');
    const mindmapSvg = document.querySelector('.mindmap-svg');
    const mindmapZoomIn = document.getElementById('mindmapZoomIn');
    const mindmapZoomOut = document.getElementById('mindmapZoomOut');
    const mindmapFit = document.getElementById('mindmapFit');
    const themeToggle = document.getElementById('themeToggle');
    const themeStorageKey = 'podcast-html-theme';
    const playbackRateStorageKey = 'podcast-html-playback-rate';
    const volumeStorageKey = 'podcast-html-volume';
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)');
    const DEFAULT_MINDMAP_VISIBLE_DEPTH = 2;
    const mindmapNodes = Array.from(document.querySelectorAll('.mindmap-svg-node[data-node-id]'));
    const mindmapLinks = Array.from(document.querySelectorAll('.mindmap-branch-line[data-node-id]'));
    const mindmapHotspots = Array.from(document.querySelectorAll('.mindmap-collapse-hotspot[data-node-id]'));
    const mindmapNodeById = new Map(mindmapNodes.map(node => [node.dataset.nodeId, node]));
    const mindmapChildrenByParent = new Map();
    mindmapNodes.forEach(node => {{
      const parentId = node.dataset.parentId || '';
      if (!mindmapChildrenByParent.has(parentId)) mindmapChildrenByParent.set(parentId, []);
      mindmapChildrenByParent.get(parentId).push(node);
    }});
    const collapsedMindmapNodes = new Set();
    const MINDMAP_LAYOUT_TOP_PADDING = 30;
    const MINDMAP_LAYOUT_MIN_GAP = 24;
    const MINDMAP_FIT_PADDING = 28;
    let mindmapScale = 1;
    let mindmapPanX = 0;
    let mindmapPanY = 0;
    let mindmapHasAutoFit = false;
    let isMindmapPanning = false;
    let mindmapPanStartX = 0;
    let mindmapPanStartY = 0;
    let mindmapPanStartOffsetX = 0;
    let mindmapPanStartOffsetY = 0;
    let mindmapGestureStartScale = 1;
    let mindmapPointerInside = false;
    let mindmapLastClientX = 0;
    let mindmapLastClientY = 0;
    const transcriptTimeline = transcriptItems.map((item, index) => {{
      const start = Number(item.dataset.start || 0);
      const rawEnd = Number(item.dataset.end || start);
      const next = transcriptItems[index + 1];
      const nextStart = next ? Number(next.dataset.start || rawEnd) : Number.POSITIVE_INFINITY;
      return {{
        item,
        start,
        end: Math.max(rawEnd, nextStart, start + 0.2),
      }};
    }});
    let activeItem = null;
    let keyboardToastTimer = null;

    function readStoredTheme() {{
      try {{
        const stored = localStorage.getItem(themeStorageKey);
        return stored === 'light' || stored === 'dark' ? stored : null;
      }} catch (error) {{
        return null;
      }}
    }}

    function writeStoredTheme(theme) {{
      try {{
        localStorage.setItem(themeStorageKey, theme);
      }} catch (error) {{}}
    }}

    function readStoredPlaybackRate() {{
      try {{
        const stored = Number(localStorage.getItem(playbackRateStorageKey));
        return Number.isFinite(stored) && stored > 0 ? stored : null;
      }} catch (error) {{
        return null;
      }}
    }}

    function writeStoredPlaybackRate(rate) {{
      try {{
        localStorage.setItem(playbackRateStorageKey, String(rate));
      }} catch (error) {{}}
    }}

    function readStoredVolume() {{
      try {{
        const stored = Number(localStorage.getItem(volumeStorageKey));
        return Number.isFinite(stored) ? Math.min(1, Math.max(0, stored)) : null;
      }} catch (error) {{
        return null;
      }}
    }}

    function writeStoredVolume(volume) {{
      try {{
        localStorage.setItem(volumeStorageKey, String(volume));
      }} catch (error) {{}}
    }}

    function setPlaybackRate(rate, persist) {{
      if (!audio) return;
      const nextRate = Number(rate);
      if (!Number.isFinite(nextRate) || nextRate <= 0) return;
      audio.playbackRate = nextRate;
      audio.defaultPlaybackRate = nextRate;
      if ('preservesPitch' in audio) audio.preservesPitch = true;
      if ('webkitPreservesPitch' in audio) audio.webkitPreservesPitch = true;
      if (playbackRateLabel) {{
        playbackRateLabel.textContent = `${{nextRate}}x`;
      }}
      playbackRateOptions.forEach(option => {{
        const selected = Number(option.dataset.rate) === nextRate;
        option.classList.toggle('active', selected);
        option.setAttribute('aria-selected', String(selected));
      }});
      if (persist) writeStoredPlaybackRate(nextRate);
    }}

    function updateVolumeControl() {{
      if (!audio || !playerVolume) return;
      const volume = audio.muted ? 0 : audio.volume;
      const percent = Math.round(volume * 100);
      playerVolume.value = String(percent);
      playerVolume.style.setProperty('--progress-percent', `${{percent}}%`);
      if (playerVolumeButton) {{
        playerVolumeButton.setAttribute('aria-label', `Volume ${{percent}}%`);
        playerVolumeButton.classList.toggle('is-muted', percent === 0);
      }}
    }}

    function setVolume(volume, persist) {{
      if (!audio) return;
      const nextVolume = Math.min(1, Math.max(0, Number(volume)));
      if (!Number.isFinite(nextVolume)) return;
      audio.volume = nextVolume;
      audio.muted = nextVolume === 0;
      updateVolumeControl();
      if (persist) writeStoredVolume(nextVolume);
    }}

    function setPlaybackRateMenuOpen(open) {{
      if (!playbackRateControl || !playbackRateButton) return;
      playbackRateControl.classList.toggle('is-open', open);
      playbackRateButton.setAttribute('aria-expanded', String(open));
    }}

    function togglePlaybackRateMenu() {{
      if (!playbackRateControl) return;
      setPlaybackRateMenuOpen(!playbackRateControl.classList.contains('is-open'));
    }}

    function formatPlayerTime(seconds) {{
      if (!Number.isFinite(seconds) || seconds < 0) return '--:--';
      const total = Math.floor(seconds);
      const hours = Math.floor(total / 3600);
      const minutes = Math.floor((total % 3600) / 60);
      const rest = total % 60;
      if (hours) {{
        return `${{hours}}:${{String(minutes).padStart(2, '0')}}:${{String(rest).padStart(2, '0')}}`;
      }}
      return `${{minutes}}:${{String(rest).padStart(2, '0')}}`;
    }}

    function updatePlayerButton() {{
      if (!audio || !playerPlayButton) return;
      const isPlaying = !audio.paused;
      playerPlayButton.textContent = isPlaying ? 'Ⅱ' : '▶';
      playerPlayButton.setAttribute('aria-label', isPlaying ? 'Pause' : 'Play');
    }}

    function updatePlayerProgress() {{
      if (!audio) return;
      const duration = Number.isFinite(audio.duration) ? audio.duration : 0;
      const current = Number.isFinite(audio.currentTime) ? audio.currentTime : 0;
      const percent = duration > 0 ? Math.min(100, Math.max(0, (current / duration) * 100)) : 0;
      if (playerCurrent) playerCurrent.textContent = formatPlayerTime(current);
      if (playerDuration) playerDuration.textContent = duration > 0 ? formatPlayerTime(duration) : '--:--';
      if (playerProgress) {{
        playerProgress.value = String(Math.round(percent * 10));
        playerProgress.style.setProperty('--progress-percent', `${{percent}}%`);
      }}
    }}

    function resolvedSystemTheme() {{
      return prefersDark.matches ? 'dark' : 'light';
    }}

    function applyTheme(theme, persist) {{
      const resolved = theme === 'dark' ? 'dark' : 'light';
      document.documentElement.dataset.theme = resolved;
      if (persist) writeStoredTheme(resolved);
      if (!themeToggle) return;
      const isDark = resolved === 'dark';
      themeToggle.setAttribute('aria-pressed', String(isDark));
      const icon = themeToggle.querySelector('.theme-toggle-icon');
      const text = themeToggle.querySelector('.theme-toggle-text');
      if (icon) icon.textContent = isDark ? '☾' : '☀';
      if (text) text.textContent = isDark ? 'Dark' : 'Light';
    }}

    applyTheme(readStoredTheme() || resolvedSystemTheme(), false);

    if (themeToggle) {{
      themeToggle.addEventListener('click', () => {{
        const current = document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
        applyTheme(current === 'dark' ? 'light' : 'dark', true);
      }});
    }}

    if (prefersDark.addEventListener) {{
      prefersDark.addEventListener('change', event => {{
        if (!readStoredTheme()) applyTheme(event.matches ? 'dark' : 'light', false);
      }});
    }}

    if (audio) {{
      setPlaybackRate(readStoredPlaybackRate() || 1, false);
      setVolume(readStoredVolume() ?? 0.5, false);
      updatePlayerButton();
      updatePlayerProgress();
      if (playerPlayButton) {{
        playerPlayButton.addEventListener('click', async () => {{
          if (audio.paused) {{
            try {{
              await audio.play();
            }} catch (error) {{}}
          }} else {{
            audio.pause();
          }}
        }});
      }}
      if (playerProgress) {{
        playerProgress.addEventListener('input', () => {{
          const duration = Number.isFinite(audio.duration) ? audio.duration : 0;
          if (!duration) return;
          const nextTime = (Number(playerProgress.value || 0) / 1000) * duration;
          audio.currentTime = nextTime;
          setActiveByTime(nextTime);
          updatePlayerProgress();
        }});
      }}
      if (playerVolume) {{
        playerVolume.addEventListener('input', () => {{
          setVolume(Number(playerVolume.value || 0) / 100, true);
        }});
      }}
      if (playbackRateButton) {{
        playbackRateButton.addEventListener('click', event => {{
          event.stopPropagation();
          togglePlaybackRateMenu();
        }});
      }}
      playbackRateOptions.forEach(option => {{
        option.addEventListener('click', event => {{
          event.stopPropagation();
          setPlaybackRate(option.dataset.rate, true);
          setPlaybackRateMenuOpen(false);
        }});
      }});
      if (playbackRateControl) {{
        document.addEventListener('click', event => {{
          if (!playbackRateControl.contains(event.target)) {{
            setPlaybackRateMenuOpen(false);
          }}
        }});
        document.addEventListener('keydown', event => {{
          if (event.key === 'Escape') setPlaybackRateMenuOpen(false);
        }});
      }}
      audio.addEventListener('ratechange', () => {{
        setPlaybackRate(audio.playbackRate, false);
      }});
      audio.addEventListener('play', updatePlayerButton);
      audio.addEventListener('pause', updatePlayerButton);
      audio.addEventListener('ended', updatePlayerButton);
      audio.addEventListener('loadedmetadata', updatePlayerProgress);
      audio.addEventListener('durationchange', updatePlayerProgress);
      audio.addEventListener('timeupdate', updatePlayerProgress);
      audio.addEventListener('seeked', updatePlayerProgress);
      audio.addEventListener('volumechange', updateVolumeControl);
    }}

    function findActiveItem(time) {{
      let low = 0;
      let high = transcriptTimeline.length - 1;
      let candidate = -1;
      while (low <= high) {{
        const mid = Math.floor((low + high) / 2);
        if (transcriptTimeline[mid].start <= time) {{
          candidate = mid;
          low = mid + 1;
        }} else {{
          high = mid - 1;
        }}
      }}
      if (candidate < 0) return null;
      const row = transcriptTimeline[candidate];
      return time < row.end ? row.item : null;
    }}

    function hasTextSelection() {{
      const selection = window.getSelection && window.getSelection();
      return Boolean(selection && selection.toString().trim());
    }}

    function seekTo(time) {{
      if (!audio) return;
      const wasPaused = audio.paused;
      const nextTime = Math.max(0, Math.min(time, Number.isFinite(audio.duration) ? audio.duration : time));
      audio.currentTime = nextTime;
      setActiveByTime(nextTime);
      updatePlayerProgress();
      if (!wasPaused) {{
        audio.play();
      }}
    }}

    function showKeyboardToast(icon) {{
      if (!keyboardToast) return;
      keyboardToast.textContent = icon;
      keyboardToast.classList.add('visible');
      window.clearTimeout(keyboardToastTimer);
      keyboardToastTimer = window.setTimeout(() => {{
        keyboardToast.classList.remove('visible');
      }}, 520);
    }}

    function shouldIgnoreKeyboardShortcut(event) {{
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return true;
      const target = event.target;
      if (!target || !(target instanceof Element)) return false;
      return Boolean(target.closest('input, textarea, select, button, [contenteditable="true"]'));
    }}

    async function togglePlaybackFromKeyboard() {{
      if (!audio) return;
      if (audio.paused) {{
        try {{
          await audio.play();
          showKeyboardToast('▶');
        }} catch (error) {{
          showKeyboardToast('!');
        }}
      }} else {{
        audio.pause();
        showKeyboardToast('Ⅱ');
      }}
    }}

    function jumpFromKeyboard(delta) {{
      if (!audio) return;
      const duration = Number.isFinite(audio.duration) ? audio.duration : Number.POSITIVE_INFINITY;
      const nextTime = Math.max(0, Math.min(duration, audio.currentTime + delta));
      audio.currentTime = nextTime;
      setActiveByTime(nextTime);
      updatePlayerProgress();
      showKeyboardToast(delta < 0 ? '⟲ 15' : '⟳ 15');
    }}

    function changeVolumeFromKeyboard(delta) {{
      if (!audio) return;
      const baseVolume = audio.muted ? 0 : audio.volume;
      const nextVolume = Math.min(1, Math.max(0, baseVolume + delta));
      setVolume(nextVolume, true);
      showKeyboardToast(`Vol ${{Math.round(nextVolume * 100)}}%`);
    }}

    document.addEventListener('keydown', event => {{
      if (!audio || shouldIgnoreKeyboardShortcut(event)) return;
      if (event.code === 'Space') {{
        event.preventDefault();
        togglePlaybackFromKeyboard();
      }} else if (event.key === 'ArrowLeft') {{
        event.preventDefault();
        jumpFromKeyboard(-15);
      }} else if (event.key === 'ArrowRight') {{
        event.preventDefault();
        jumpFromKeyboard(15);
      }} else if (event.key === 'ArrowUp') {{
        event.preventDefault();
        changeVolumeFromKeyboard(0.05);
      }} else if (event.key === 'ArrowDown') {{
        event.preventDefault();
        changeVolumeFromKeyboard(-0.05);
      }}
    }});

    function setActiveByTime(time) {{
      const active = findActiveItem(time);
      if (active === activeItem) return;
      if (activeItem) activeItem.classList.remove('active');
      activeItem = active;
      if (activeItem) {{
        activeItem.classList.add('active');
      }}
      if (activeItem && transcriptList && !activeItem.classList.contains('hidden')) {{
        const activeCenter = activeItem.offsetTop + activeItem.clientHeight / 2;
        const viewportCenter = transcriptList.scrollTop + transcriptList.clientHeight / 2;
        if (activeCenter > viewportCenter) {{
          const targetTop = activeCenter - transcriptList.clientHeight / 2;
          transcriptList.scrollTo({{ top: Math.max(0, targetTop), behavior: 'smooth' }});
        }} else if (activeItem.offsetTop < transcriptList.scrollTop) {{
          transcriptList.scrollTo({{ top: Math.max(0, activeItem.offsetTop - 12), behavior: 'smooth' }});
        }}
      }}
    }}

    document.querySelectorAll('[data-seek]').forEach(button => {{
      button.addEventListener('click', event => {{
        event.stopPropagation();
        seekTo(Number(button.dataset.seek || 0));
      }});
    }});

    document.querySelectorAll('a.timestamp[data-timestamp]').forEach(link => {{
      link.addEventListener('click', event => {{
        event.preventDefault();
        seekTo(Number(link.dataset.timestamp || 0));
      }});
    }});

    transcriptItems.forEach(item => {{
      item.addEventListener('click', () => {{
        if (hasTextSelection()) return;
        seekTo(Number(item.dataset.start || 0));
      }});
    }});

    if (audio) {{
      audio.addEventListener('timeupdate', () => setActiveByTime(audio.currentTime));
    }}

    if (search) {{
      search.addEventListener('input', () => {{
        const query = search.value.trim().toLowerCase();
        transcriptItems.forEach(item => {{
          item.classList.toggle('hidden', query && !(item.dataset.text || '').includes(query));
        }});
      }});
    }}

    document.querySelectorAll('.tab').forEach(tab => {{
      tab.addEventListener('click', () => {{
        const target = tab.dataset.tab;
        document.querySelectorAll('.tab').forEach(item => item.classList.toggle('active', item === tab));
        document.querySelectorAll('.tab-panel').forEach(panel => {{
          panel.classList.toggle('active', panel.id === target);
        }});
        if (target === 'mindmap') {{
          scheduleMindmapFit(false);
        }}
      }});
    }});

    function mindmapNodeDepth(node) {{
      return Number(node.dataset.depth || 0);
    }}

    mindmapNodes.forEach(node => {{
      if (node.dataset.hasChildren === 'true' && mindmapNodeDepth(node) >= DEFAULT_MINDMAP_VISIBLE_DEPTH) {{
        collapsedMindmapNodes.add(node.dataset.nodeId);
      }}
    }});

    function mindmapHasCollapsedAncestor(node) {{
      let parentId = node.dataset.parentId || '';
      while (parentId) {{
        if (collapsedMindmapNodes.has(parentId)) return true;
        const parent = mindmapNodeById.get(parentId);
        parentId = parent ? (parent.dataset.parentId || '') : '';
      }}
      return false;
    }}

    function applyMindmapVisibility() {{
      mindmapNodes.forEach(node => {{
        const hasChildren = node.dataset.hasChildren === 'true';
        const nodeId = node.dataset.nodeId;
        const isCollapsed = collapsedMindmapNodes.has(nodeId);
        const isHidden = mindmapHasCollapsedAncestor(node);
        node.classList.toggle('mindmap-hidden', isHidden);
        node.classList.toggle('is-collapsed', hasChildren && isCollapsed);
        if (hasChildren) {{
          node.setAttribute('aria-expanded', String(!isCollapsed));
          const icon = node.querySelector('.mindmap-collapse-icon');
          if (icon) icon.textContent = isCollapsed ? '+' : '−';
        }}
      }});

      mindmapLinks.forEach(link => {{
        const child = mindmapNodeById.get(link.dataset.nodeId);
        link.classList.toggle('mindmap-hidden', !child || mindmapHasCollapsedAncestor(child));
      }});
      applyMindmapLayout();
    }}

    function mindmapNodeX(node) {{
      return Number(node.dataset.x || 0);
    }}

    function mindmapNodeBaseY(node) {{
      return Number(node.dataset.y || 0);
    }}

    function mindmapNodeVisualWidth(node) {{
      return Number(node.dataset.visualWidth || 0);
    }}

    function mindmapNodeVisualHeight(node) {{
      return Number(node.dataset.visualHeight || 24);
    }}

    function drawMindmapLink(link, positions) {{
      const parent = mindmapNodeById.get(link.dataset.parentId);
      const child = mindmapNodeById.get(link.dataset.nodeId);
      if (!parent || !child || !positions.has(parent.dataset.nodeId) || !positions.has(child.dataset.nodeId)) return;
      const startX = mindmapNodeX(parent) + mindmapNodeVisualWidth(parent) + 18;
      const startY = positions.get(parent.dataset.nodeId);
      const endX = mindmapNodeX(child) - 16;
      const endY = positions.get(child.dataset.nodeId);
      const curve = Math.max(36, (endX - startX) * 0.45);
      link.setAttribute('d', `M ${{startX.toFixed(1)}} ${{startY.toFixed(1)}} C ${{(startX + curve).toFixed(1)}} ${{startY.toFixed(1)}}, ${{(endX - curve).toFixed(1)}} ${{endY.toFixed(1)}}, ${{endX.toFixed(1)}} ${{endY.toFixed(1)}}`);
    }}

    function applyMindmapLayout() {{
      if (!mindmapSvg) return;
      const roots = mindmapChildrenByParent.get('') || [];
      if (!roots.length) return;
      const positions = new Map();
      let leafCursor = 0;

      function layoutNode(node) {{
        const nodeId = node.dataset.nodeId;
        const children = collapsedMindmapNodes.has(nodeId)
          ? []
          : (mindmapChildrenByParent.get(nodeId) || []);
        if (children.length) {{
          const childYs = children.map(layoutNode);
          const y = childYs.reduce((sum, value) => sum + value, 0) / childYs.length;
          positions.set(nodeId, y);
          return y;
        }}
        const y = MINDMAP_LAYOUT_TOP_PADDING + leafCursor;
        leafCursor += Math.max(MINDMAP_LAYOUT_MIN_GAP, mindmapNodeVisualHeight(node) + 2);
        positions.set(nodeId, y);
        return y;
      }}

      roots.forEach(layoutNode);
      const height = Math.max(420, Math.ceil(leafCursor + MINDMAP_LAYOUT_TOP_PADDING * 2));
      const width = Number(mindmapSvg.dataset.width || mindmapSvg.getAttribute('width') || 0);
      if (width) {{
        mindmapSvg.dataset.height = String(height);
        mindmapSvg.setAttribute('height', String(height));
        mindmapSvg.setAttribute('viewBox', `0 0 ${{width}} ${{height}}`);
        const controls = document.querySelector('.mindmap-controls');
        if (controls) controls.dataset.height = String(height);
      }}

      mindmapNodes.forEach(node => {{
        const nodeId = node.dataset.nodeId;
        if (!positions.has(nodeId)) return;
        const currentY = positions.get(nodeId);
        const deltaY = currentY - mindmapNodeBaseY(node);
        node.dataset.currentY = String(currentY);
        node.setAttribute('transform', `translate(0 ${{deltaY.toFixed(1)}})`);
      }});
      mindmapLinks.forEach(link => drawMindmapLink(link, positions));
    }}

    mindmapHotspots.forEach(hotspot => {{
      const toggleNode = event => {{
        event.preventDefault();
        event.stopPropagation();
        const nodeId = hotspot.dataset.nodeId;
        if (collapsedMindmapNodes.has(nodeId)) {{
          collapsedMindmapNodes.delete(nodeId);
        }} else {{
          collapsedMindmapNodes.add(nodeId);
        }}
        applyMindmapVisibility();
        mindmapHasAutoFit = false;
        scheduleMindmapFit(true);
      }};
      hotspot.addEventListener('click', toggleNode);
      hotspot.addEventListener('keydown', event => {{
        if (event.key === 'Enter' || event.key === ' ') {{
          toggleNode(event);
        }}
      }});
    }});

    mindmapNodes.forEach(node => {{
      if (!node.dataset.timestamp) return;
      node.addEventListener('click', event => {{
        if (event.target.closest && event.target.closest('.mindmap-collapse-hotspot')) return;
        seekTo(Number(node.dataset.timestamp || 0));
      }});
      node.addEventListener('keydown', event => {{
        if (event.key === 'Enter' || event.key === ' ') {{
          event.preventDefault();
          seekTo(Number(node.dataset.timestamp || 0));
        }}
      }});
    }});

    applyMindmapVisibility();
    scheduleMindmapFit(false);

    function applyMindmapScale() {{
      if (!mindmapSvg) return;
      const svgWidth = Number(mindmapSvg.dataset.width || mindmapSvg.getAttribute('width') || 0);
      const svgHeight = Number(mindmapSvg.dataset.height || mindmapSvg.getAttribute('height') || 0);
      if (!svgWidth || !svgHeight) return;
      mindmapSvg.style.width = `${{Math.max(1, svgWidth)}}px`;
      mindmapSvg.style.height = `${{Math.max(1, svgHeight)}}px`;
      mindmapSvg.style.transform = `translate(${{mindmapPanX.toFixed(1)}}px, ${{mindmapPanY.toFixed(1)}}px) scale(${{mindmapScale}})`;
    }}

    function clampMindmapScale(scale) {{
      return Math.min(3.2, Math.max(0.03, Math.round(scale * 10000) / 10000));
    }}

    function mindmapVisibleBounds() {{
      const visibleNodes = mindmapNodes.filter(node => !node.classList.contains('mindmap-hidden'));
      if (!visibleNodes.length) return null;
      const bounds = {{
        left: Number.POSITIVE_INFINITY,
        top: Number.POSITIVE_INFINITY,
        right: Number.NEGATIVE_INFINITY,
        bottom: Number.NEGATIVE_INFINITY,
      }};
      visibleNodes.forEach(node => {{
        const x = mindmapNodeX(node);
        const y = Number(node.dataset.currentY || node.dataset.y || 0);
        const width = mindmapNodeVisualWidth(node);
        const height = mindmapNodeVisualHeight(node);
        bounds.left = Math.min(bounds.left, x - 28);
        bounds.top = Math.min(bounds.top, y - height / 2 - 18);
        bounds.right = Math.max(bounds.right, x + width + 34);
        bounds.bottom = Math.max(bounds.bottom, y + height / 2 + 18);
      }});
      bounds.width = Math.max(1, bounds.right - bounds.left);
      bounds.height = Math.max(1, bounds.bottom - bounds.top);
      return bounds;
    }}

    function zoomMindmapTo(nextScale, originX, originY) {{
      if (!mindmapSvg || !mindmapCanvas) return;
      const previousScale = mindmapScale;
      const scale = clampMindmapScale(nextScale);
      if (scale === previousScale) return;

      const rect = mindmapCanvas.getBoundingClientRect();
      const viewportX = typeof originX === 'number' ? originX - rect.left : mindmapCanvas.clientWidth / 2;
      const viewportY = typeof originY === 'number' ? originY - rect.top : mindmapCanvas.clientHeight / 2;
      const contentX = (viewportX - mindmapPanX) / previousScale;
      const contentY = (viewportY - mindmapPanY) / previousScale;

      mindmapScale = scale;
      mindmapPanX = viewportX - contentX * scale;
      mindmapPanY = viewportY - contentY * scale;
      applyMindmapScale();
    }}

    function fitMindmapToCanvas() {{
      if (!mindmapSvg || !mindmapCanvas) return false;
      const svgWidth = Number(mindmapSvg.dataset.width || 0);
      const svgHeight = Number(mindmapSvg.dataset.height || 0);
      if (!svgWidth || !svgHeight || !mindmapCanvas.clientWidth || !mindmapCanvas.clientHeight) return false;
      const bounds = mindmapVisibleBounds();
      if (!bounds) return false;
      const fitWidth = Math.max(1, mindmapCanvas.clientWidth - MINDMAP_FIT_PADDING * 2);
      const fitHeight = Math.max(1, mindmapCanvas.clientHeight - MINDMAP_FIT_PADDING * 2);
      mindmapScale = clampMindmapScale(Math.min(fitWidth / bounds.width, fitHeight / bounds.height));
      mindmapPanX = (mindmapCanvas.clientWidth - bounds.width * mindmapScale) / 2 - bounds.left * mindmapScale;
      mindmapPanY = (mindmapCanvas.clientHeight - bounds.height * mindmapScale) / 2 - bounds.top * mindmapScale;
      applyMindmapScale();
      return true;
    }}

    function scheduleMindmapFit(force) {{
      if (!force && mindmapHasAutoFit) return;
      requestAnimationFrame(() => {{
        if (fitMindmapToCanvas()) {{
          mindmapHasAutoFit = true;
        }}
      }});
    }}

    if (mindmapComponent && mindmapZoomButton) {{
      if (mindmapZoomIn) {{
        mindmapZoomIn.addEventListener('click', () => {{
          zoomMindmapTo(mindmapScale * 1.18);
        }});
      }}
      if (mindmapZoomOut) {{
        mindmapZoomOut.addEventListener('click', () => {{
          zoomMindmapTo(mindmapScale / 1.18);
        }});
      }}
      if (mindmapFit) {{
        mindmapFit.addEventListener('click', () => {{
          mindmapHasAutoFit = false;
          scheduleMindmapFit(true);
        }});
      }}
      mindmapZoomButton.addEventListener('click', () => {{
        const expanded = mindmapComponent.classList.toggle('is-expanded');
        mindmapZoomButton.textContent = expanded ? '↙' : '⛶';
        mindmapZoomButton.setAttribute('aria-pressed', String(expanded));
        if (expanded) scheduleMindmapFit(true);
      }});
      document.addEventListener('keydown', event => {{
        if (event.key === 'Escape' && mindmapComponent.classList.contains('is-expanded')) {{
          mindmapComponent.classList.remove('is-expanded');
          mindmapZoomButton.textContent = '⛶';
          mindmapZoomButton.setAttribute('aria-pressed', 'false');
        }}
      }});
    }}

    if (mindmapCanvas) {{
      function isMindmapCanvasEvent(event) {{
        if (!mindmapCanvas) return false;
        const path = event.composedPath ? event.composedPath() : [];
        if (path.includes(mindmapCanvas)) return true;
        if (typeof event.clientX !== 'number' || typeof event.clientY !== 'number') return mindmapPointerInside;
        const rect = mindmapCanvas.getBoundingClientRect();
        const isInside = event.clientX >= rect.left
          && event.clientX <= rect.right
          && event.clientY >= rect.top
          && event.clientY <= rect.bottom;
        return isInside || (String(event.type || '').startsWith('gesture') && mindmapPointerInside);
      }}

      function handleMindmapWheel(event) {{
        if (!isMindmapCanvasEvent(event)) return;
        event.preventDefault();
        if (event.ctrlKey || event.metaKey || Math.abs(event.deltaZ || 0) > 0) {{
          const delta = event.deltaY === 0 ? event.deltaZ : event.deltaY;
          const factor = Math.exp(-delta * 0.006);
          const originX = typeof event.clientX === 'number' ? event.clientX : mindmapLastClientX;
          const originY = typeof event.clientY === 'number' ? event.clientY : mindmapLastClientY;
          zoomMindmapTo(mindmapScale * factor, originX, originY);
        }} else {{
          mindmapPanX -= event.deltaX;
          mindmapPanY -= event.deltaY;
          applyMindmapScale();
        }}
      }}

      function handleMindmapGestureStart(event) {{
        if (!isMindmapCanvasEvent(event)) return;
        event.preventDefault();
        mindmapGestureStartScale = mindmapScale;
      }}

      function handleMindmapGestureChange(event) {{
        if (!isMindmapCanvasEvent(event)) return;
        event.preventDefault();
        const scale = Number(event.scale || 1);
        const originX = typeof event.clientX === 'number' ? event.clientX : mindmapLastClientX;
        const originY = typeof event.clientY === 'number' ? event.clientY : mindmapLastClientY;
        zoomMindmapTo(mindmapGestureStartScale * scale, originX, originY);
      }}

      window.addEventListener('wheel', handleMindmapWheel, {{ passive: false, capture: true }});
      window.addEventListener('gesturestart', handleMindmapGestureStart, {{ passive: false, capture: true }});
      window.addEventListener('gesturechange', handleMindmapGestureChange, {{ passive: false, capture: true }});

      mindmapCanvas.addEventListener('pointerenter', event => {{
        mindmapPointerInside = true;
        mindmapLastClientX = event.clientX;
        mindmapLastClientY = event.clientY;
      }});
      mindmapCanvas.addEventListener('pointermove', event => {{
        mindmapPointerInside = true;
        mindmapLastClientX = event.clientX;
        mindmapLastClientY = event.clientY;
      }});
      mindmapCanvas.addEventListener('pointerleave', () => {{
        mindmapPointerInside = false;
      }});

      mindmapCanvas.addEventListener('pointerdown', event => {{
        if (event.button !== 0) return;
        const target = event.target;
        if (target.closest && target.closest('.mindmap-svg-node, .mindmap-collapse-hotspot, .mindmap-toolbar, button')) return;
        isMindmapPanning = true;
        mindmapPanStartX = event.clientX;
        mindmapPanStartY = event.clientY;
        mindmapPanStartOffsetX = mindmapPanX;
        mindmapPanStartOffsetY = mindmapPanY;
        mindmapCanvas.classList.add('is-panning');
        mindmapCanvas.setPointerCapture(event.pointerId);
      }});

      mindmapCanvas.addEventListener('pointermove', event => {{
        if (!isMindmapPanning) return;
        event.preventDefault();
        mindmapPanX = mindmapPanStartOffsetX + (event.clientX - mindmapPanStartX);
        mindmapPanY = mindmapPanStartOffsetY + (event.clientY - mindmapPanStartY);
        applyMindmapScale();
      }});

      function stopMindmapPan(event) {{
        if (!isMindmapPanning) return;
        isMindmapPanning = false;
        mindmapCanvas.classList.remove('is-panning');
        if (event.pointerId !== undefined && mindmapCanvas.hasPointerCapture(event.pointerId)) {{
          mindmapCanvas.releasePointerCapture(event.pointerId);
        }}
      }}

      mindmapCanvas.addEventListener('pointerup', stopMindmapPan);
      mindmapCanvas.addEventListener('pointercancel', stopMindmapPan);
      mindmapCanvas.addEventListener('pointerleave', stopMindmapPan);
    }}
  </script>
</body>
</html>
"""


def render_podcast_html(
    episode_dir: Path,
    output: Path | None = None,
    max_group_seconds: float = DEFAULT_MAX_GROUP_SECONDS,
    max_group_chars: int = DEFAULT_MAX_GROUP_CHARS,
) -> PodcastHtmlResult:
    episode_dir = episode_dir.resolve()
    metadata = _load_metadata(episode_dir)
    if not metadata.get("title"):
        metadata["title"] = episode_dir.name
    audio_path = _find_audio(episode_dir, metadata)
    audio_src = _asset_src(audio_path, episode_dir)
    cover_src = str(metadata.get("cover_url") or metadata.get("image") or "")

    transcript, transcript_source = load_transcript(episode_dir, max_group_seconds, max_group_chars)
    shownotes = str(metadata.get("shownotes") or metadata.get("description") or "")
    mindmap = _read_optional_text(episode_dir / "mindmap.md")
    insights = _read_optional_text(episode_dir / "insights.md")

    html_doc = render_html_document(
        metadata=metadata,
        audio_src=audio_src,
        cover_src=cover_src,
        transcript_html=_render_transcript(transcript),
        shownotes_html=render_rich_text(shownotes),
        mindmap_html=render_mindmap_component(mindmap),
        insights_html=markdown_to_html(insights),
    )

    output_path = output.resolve() if output else episode_dir / "episode.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_doc, encoding="utf-8")
    return PodcastHtmlResult(
        episode_dir=str(episode_dir),
        html=str(output_path),
        transcript_source=transcript_source,
        has_audio=audio_path is not None,
        has_mindmap=bool(mindmap),
        has_insights=bool(insights),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a podcast episode.html page")
    parser.add_argument("episode_dir", help="Episode directory")
    parser.add_argument("--output", help="Output HTML path, defaults to episode_dir/episode.html")
    parser.add_argument("--max-group-seconds", type=float, default=DEFAULT_MAX_GROUP_SECONDS)
    parser.add_argument("--max-group-chars", type=int, default=DEFAULT_MAX_GROUP_CHARS)
    args = parser.parse_args()

    result = render_podcast_html(
        Path(args.episode_dir),
        output=Path(args.output) if args.output else None,
        max_group_seconds=args.max_group_seconds,
        max_group_chars=args.max_group_chars,
    )
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
