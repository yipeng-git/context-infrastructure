"""音频转写工具（Apple Silicon 加速，支持说话人分离）

全程使用 MLX 加速，无需 GPU / CUDA / HF_TOKEN：
  - 转写：mlx-whisper（Apple Silicon 优化）
  - 说话人分离：mlx-audio Sortformer（Apple Silicon 优化）

两种模式：
  - 默认：转写 + 说话人分离，输出带 SPEAKER 标签
  - --no-diarize：仅转写，跳过说话人分离

用法:
    python tools/transcribe_audio.py audio.mp3
    python tools/transcribe_audio.py audio.mp3 --num-speakers 2
    python tools/transcribe_audio.py audio.mp3 --no-diarize
    python tools/transcribe_audio.py audio.mp3 --threshold 0.4

依赖: mlx-whisper, mlx-audio
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path


DEFAULT_MAX_GROUP_SECONDS = 90.0
DEFAULT_MAX_GROUP_CHARS = 1500


def transcribe_mlx(audio_path: Path, model_name: str) -> list[dict]:
    """mlx-whisper 转写，返回带时间戳的 segments"""
    from mlx_whisper import transcribe

    print(f"[1/3] 转写中 (mlx-whisper: {model_name})...", file=sys.stderr)
    result = transcribe(str(audio_path), path_or_hf_repo=model_name, verbose=False)
    segments = result.get("segments", [])
    print(f"  转写完成: {len(segments)} 段", file=sys.stderr)
    return segments


def diarize_sortformer(audio_path: Path, threshold: float,
                       diar_model_name: str) -> list:
    """Sortformer 说话人分离（流式处理，避免长音频 OOM）"""
    from mlx_audio.vad import load

    print(f"[2/3] 说话人分离 (Sortformer streaming)...", file=sys.stderr)
    model = load(diar_model_name)

    all_segments = []
    for chunk_result in model.generate_stream(
        str(audio_path), chunk_duration=10.0,
        threshold=threshold, verbose=True,
    ):
        all_segments.extend(chunk_result.segments)

    speakers = set(seg.speaker for seg in all_segments)
    print(f"  分离完成: {len(all_segments)} 段, {len(speakers)} 位说话人", file=sys.stderr)
    return all_segments


def collapse_speakers(diar_segments: list, num_speakers: int) -> list:
    """将多余的说话人合并到出现次数最多的 N 个说话人上。

    对每个被合并的 segment，找时间上最近的主说话人 segment 来继承 ID。
    """
    counts = Counter(seg.speaker for seg in diar_segments)
    top_speakers = {spk for spk, _ in counts.most_common(num_speakers)}

    minor_segments = [s for s in diar_segments if s.speaker not in top_speakers]
    major_segments = [s for s in diar_segments if s.speaker in top_speakers]

    if not minor_segments or not major_segments:
        return diar_segments

    merged = []
    for seg in diar_segments:
        if seg.speaker in top_speakers:
            merged.append(seg)
        else:
            seg_mid = (seg.start + seg.end) / 2
            nearest = min(major_segments, key=lambda m: abs((m.start + m.end) / 2 - seg_mid))
            from dataclasses import replace
            merged.append(replace(seg, speaker=nearest.speaker))

    old_ids = sorted(counts.keys())
    new_ids = sorted(set(s.speaker for s in merged))
    remap = {old: i for i, old in enumerate(new_ids)}
    for seg in merged:
        seg_obj = seg
        # replace returns a new object, need to update in list
    result = []
    for seg in merged:
        from dataclasses import replace as dc_replace
        result.append(dc_replace(seg, speaker=remap.get(seg.speaker, seg.speaker)))

    merged_from = len(counts) - num_speakers
    print(f"  合并说话人: {len(counts)} → {num_speakers} (合并了 {merged_from} 个次要说话人)", file=sys.stderr)
    return result


def merge_transcript_and_diarization(
    transcript_segments: list[dict],
    diarize_segments: list,
) -> list[dict]:
    """按时间戳重叠度将说话人标签分配给转写文本"""
    for seg in transcript_segments:
        seg_start = seg.get("start", 0.0)
        seg_end = seg.get("end", 0.0)

        best_speaker = None
        best_overlap = 0.0

        for dseg in diarize_segments:
            overlap = min(seg_end, dseg.end) - max(seg_start, dseg.start)
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = dseg.speaker

        seg["speaker"] = f"speaker_{best_speaker:02d}" if best_speaker is not None else "unknown"

    return transcript_segments


def _fmt_ts(seconds: float, force_hours: bool = False) -> str:
    """秒数 → HH:MM:SS 或 MM:SS"""
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h or force_hours else f"{m:02d}:{s:02d}"


def parse_ts(value: str | int | float | None) -> float | None:
    """HH:MM:SS / MM:SS / 秒数 → 秒。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().strip("\"'")
    if not text:
        return None
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return float(text)

    parts = [int(part) for part in text.split(":")]
    if len(parts) == 2:
        m, s = parts
        return float(m * 60 + s)
    if len(parts) == 3:
        h, m, s = parts
        return float(h * 3600 + m * 60 + s)
    raise ValueError(f"无法解析时间戳: {value}")


_END_PUNCTUATION = set("。！？!?；;，,、：:\"'）)]}》」』")


def _join_fragments(fragments: list[str]) -> str:
    """合并同一说话人的连续 ASR fragments。"""
    text = ""
    for fragment in fragments:
        fragment = fragment.strip()
        if not fragment:
            continue
        if not text:
            text = fragment
        elif text[-1] in _END_PUNCTUATION:
            text += fragment
        else:
            text += f"，{fragment}"
    return text


def _speaker_label(speaker: object) -> str:
    if not speaker:
        return "unknown"
    return str(speaker).lower()


def normalize_segments(segments: list[dict], source: str) -> list[dict]:
    """将 ASR segments 归一化为稳定的事实层 schema。"""
    normalized = []
    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            continue
        normalized.append({
            "start": float(seg.get("start", 0.0)),
            "end": float(seg.get("end", seg.get("start", 0.0))),
            "speaker": _speaker_label(seg.get("speaker", "unknown")),
            "text": text,
            "confidence": seg.get("confidence"),
            "source": source,
        })
    return normalized


def load_segments_jsonl(path: Path) -> list[dict]:
    segments = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            segments.append(json.loads(line))
    return segments


def write_segments_jsonl(segments: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(seg, ensure_ascii=False) for seg in segments)
    path.write_text(text + ("\n" if text else ""), encoding="utf-8")


def format_raw_output(segments: list[dict], with_speakers: bool) -> str:
    """逐 segment 输出，便于定位和人工校对。"""
    lines = []
    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            continue
        ts = _fmt_ts(seg.get("start", 0.0))
        if with_speakers:
            speaker = _speaker_label(seg.get("speaker", "unknown"))
            lines.append(f"[{ts}] [{speaker}] {text}")
        else:
            lines.append(f"[{ts}] {text}")
    return "\n".join(lines)


def write_raw_txt(segments: list[dict], path: Path, with_speakers: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_raw_output(segments, with_speakers), encoding="utf-8")


def _parse_scalar(value: str) -> object:
    value = value.strip().strip("\"'")
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.lower() in {"null", "none"}:
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def _load_minimal_yaml(path: Path) -> object:
    """读取当前 workflow 需要的简单 YAML 子集。"""
    lines = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if line.strip():
            lines.append(line)

    if not lines:
        return None

    if any(line.lstrip().startswith("- ") for line in lines):
        items: list[dict] = []
        current: dict | None = None
        for line in lines:
            stripped = line.strip()
            if stripped.endswith(":") and not stripped.startswith("- "):
                continue
            if stripped.startswith("- "):
                if current:
                    items.append(current)
                current = {}
                stripped = stripped[2:].strip()
                if stripped and ":" in stripped:
                    key, value = stripped.split(":", 1)
                    current[key.strip()] = _parse_scalar(value)
            elif current is not None and ":" in stripped:
                key, value = stripped.split(":", 1)
                current[key.strip()] = _parse_scalar(value)
        if current:
            items.append(current)
        return items

    data: dict[str, object] = {}
    active_map: dict[str, object] | None = None
    for line in lines:
        if not line.startswith(" ") and line.strip().endswith(":"):
            key = line.strip()[:-1]
            data[key] = {}
            active_map = data[key]  # type: ignore[assignment]
        elif ":" in line:
            key, value = line.strip().split(":", 1)
            target = active_map if line.startswith(" ") and active_map is not None else data
            target[key.strip()] = _parse_scalar(value)  # type: ignore[index]
    return data


def load_yaml_data(path: Path | None) -> object:
    if not path or not path.exists():
        return None
    try:
        import yaml  # type: ignore[import-not-found]
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return _load_minimal_yaml(path)


def load_lexicon(path: Path | None) -> dict[str, str]:
    data = load_yaml_data(path)
    if not data:
        return {}
    if isinstance(data, dict):
        replacements = data.get("replacements", data)
        if isinstance(replacements, dict):
            return {str(k): str(v) for k, v in replacements.items()}
        if isinstance(replacements, list):
            return {
                str(item.get("old")): str(item.get("new"))
                for item in replacements
                if isinstance(item, dict) and item.get("old") and item.get("new")
            }
    if isinstance(data, list):
        return {
            str(item.get("old")): str(item.get("new"))
            for item in data
            if isinstance(item, dict) and item.get("old") and item.get("new")
        }
    return {}


def load_corrections(path: Path | None) -> list[dict]:
    data = load_yaml_data(path)
    if not data:
        return []
    if isinstance(data, dict):
        corrections = data.get("corrections", [])
        return corrections if isinstance(corrections, list) else []
    return data if isinstance(data, list) else []


def _segment_overlaps(seg: dict, start: float | None, end: float | None) -> bool:
    seg_start = float(seg.get("start", 0.0))
    seg_end = float(seg.get("end", seg_start))
    if start is not None and seg_end < start:
        return False
    if end is not None and seg_start > end:
        return False
    return True


def apply_lexicon(segments: list[dict], replacements: dict[str, str]) -> list[dict]:
    if not replacements:
        return deepcopy(segments)
    result = deepcopy(segments)
    for seg in result:
        text = seg.get("text", "")
        for old, new in replacements.items():
            text = text.replace(old, new)
        seg["text"] = text
    return result


def apply_corrections(segments: list[dict], corrections: list[dict]) -> list[dict]:
    """应用结构化修正，只修改派生层，不改 raw JSONL。"""
    result = deepcopy(segments)
    for correction in corrections:
        if not isinstance(correction, dict):
            continue

        ctype = str(correction.get("type") or correction.get("action") or "").strip()
        start = parse_ts(correction.get("start") or correction.get("from_ts") or correction.get("range_start"))
        end = parse_ts(correction.get("end") or correction.get("to_ts") or correction.get("range_end"))

        if ctype in {"force_break", "break"}:
            for seg in result:
                seg_start = float(seg.get("start", 0.0))
                if start is None or seg_start >= start:
                    seg["force_break_before"] = True
                    break
            continue

        if ctype in {"drop_range", "delete_range", "omit"}:
            result = [seg for seg in result if not _segment_overlaps(seg, start, end)]
            continue

        for seg in result:
            if not _segment_overlaps(seg, start, end):
                continue

            if ctype in {"speaker_remap", "remap_speaker", "set_speaker"}:
                old = correction.get("from") or correction.get("old") or correction.get("speaker")
                new = correction.get("to") or correction.get("new")
                if new and (not old or _speaker_label(seg.get("speaker")) == _speaker_label(str(old))):
                    seg["speaker"] = _speaker_label(str(new))

            if ctype in {"replace_text", "term_replace"}:
                old_text = correction.get("old")
                new_text = correction.get("new")
                if old_text and new_text:
                    seg["text"] = seg.get("text", "").replace(str(old_text), str(new_text))
    return result


def render_segments(
    raw_segments: list[dict],
    corrections: list[dict] | None = None,
    lexicon: dict[str, str] | None = None,
) -> list[dict]:
    segments = apply_corrections(raw_segments, corrections or [])
    return apply_lexicon(segments, lexicon or {})


def build_readable_groups(
    segments: list[dict],
    max_group_seconds: float = DEFAULT_MAX_GROUP_SECONDS,
    max_group_chars: int = DEFAULT_MAX_GROUP_CHARS,
) -> list[dict]:
    groups = []
    current_group = None

    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            continue
        speaker = _speaker_label(seg.get("speaker", "unknown"))
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start))

        should_break = (
            current_group is None
            or current_group["speaker"] != speaker
            or bool(seg.get("force_break_before"))
        )
        if current_group is not None and not should_break:
            projected_text_len = current_group["chars"] + len(text)
            projected_duration = end - current_group["start"]
            should_break = (
                projected_duration > max_group_seconds
                or projected_text_len > max_group_chars
            )

        if should_break:
            if current_group is not None:
                groups.append(current_group)
            current_group = {
                "start": start,
                "end": end,
                "speaker": speaker,
                "texts": [text],
                "chars": len(text),
            }
        else:
            current_group["texts"].append(text)
            current_group["end"] = max(current_group["end"], end)
            current_group["chars"] += len(text)

    if current_group is not None:
        groups.append(current_group)
    return groups


def format_output(
    segments: list[dict],
    with_speakers: bool,
    max_group_seconds: float = DEFAULT_MAX_GROUP_SECONDS,
    max_group_chars: int = DEFAULT_MAX_GROUP_CHARS,
) -> str:
    """格式化最终输出文本，连续同一说话人的内容合并为一个段落。"""
    if not with_speakers:
        lines = []
        for seg in segments:
            text = seg.get("text", "").strip()
            if not text:
                continue
            ts = _fmt_ts(seg.get("start", 0.0))
            lines.append(f"{ts}: {text}")
        return "\n".join(lines)

    groups = build_readable_groups(segments, max_group_seconds, max_group_chars)
    lines = []
    for group in groups:
        ts = _fmt_ts(group["start"], force_hours=True)
        text = _join_fragments(group["texts"])
        speaker = _speaker_label(group["speaker"])
        lines.append(f"{ts} {speaker}: {text}")
    return "\n\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="音频转写工具（Apple Silicon MLX 加速）")
    parser.add_argument("audio", help="音频文件路径")
    parser.add_argument("--output", "-o", help="输出文件路径 (默认同目录 transcript.txt)")
    parser.add_argument("--model", "-m", default="mlx-community/whisper-large-v3-turbo",
                        help="Whisper 模型 (默认 mlx-community/whisper-large-v3-turbo)")
    parser.add_argument("--no-diarize", action="store_true",
                        help="不做说话人分离，仅转写")
    parser.add_argument("--num-speakers", type=int, default=None,
                        help="已知说话人数量（自动合并多余说话人，播客通常为 2）")
    parser.add_argument("--threshold", type=float, default=0.5,
                        help="说话人活动检测阈值 0-1 (默认 0.5)")
    parser.add_argument("--diar-model", default="mlx-community/diar_sortformer_4spk-v1-fp32",
                        help="说话人分离模型 (默认 Sortformer v1)")
    parser.add_argument("--raw-jsonl", help="事实层 JSONL 输出路径 (默认 _pipeline/transcript_raw.jsonl)")
    parser.add_argument("--raw-output", help="短句校对版 TXT 输出路径 (默认 _pipeline/transcript_raw.txt)")
    parser.add_argument("--corrections", help="结构化修正文件 corrections.yaml")
    parser.add_argument("--lexicon", help="术语替换文件 lexicon.yaml")
    parser.add_argument("--max-group-seconds", type=float, default=DEFAULT_MAX_GROUP_SECONDS,
                        help=f"阅读版单段最长秒数 (默认 {DEFAULT_MAX_GROUP_SECONDS:.0f})")
    parser.add_argument("--max-group-chars", type=int, default=DEFAULT_MAX_GROUP_CHARS,
                        help=f"阅读版单段最长字数 (默认 {DEFAULT_MAX_GROUP_CHARS})")
    args = parser.parse_args()

    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"错误: 文件不存在: {audio_path}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output) if args.output else audio_path.parent / "transcript.txt"
    pipeline_dir = output_path.parent / "_pipeline"
    raw_jsonl_path = Path(args.raw_jsonl) if args.raw_jsonl else pipeline_dir / "transcript_raw.jsonl"
    raw_txt_path = Path(args.raw_output) if args.raw_output else pipeline_dir / "transcript_raw.txt"

    segments = transcribe_mlx(audio_path, args.model)

    if args.no_diarize:
        raw_segments = normalize_segments(segments, source="mlx-whisper")
        write_segments_jsonl(raw_segments, raw_jsonl_path)
        write_raw_txt(raw_segments, raw_txt_path, with_speakers=False)
        rendered_segments = render_segments(
            raw_segments,
            corrections=load_corrections(Path(args.corrections)) if args.corrections else [],
            lexicon=load_lexicon(Path(args.lexicon)) if args.lexicon else {},
        )
        transcript = format_output(rendered_segments, with_speakers=False)
    else:
        diar_segments = diarize_sortformer(audio_path, args.threshold, args.diar_model)
        if args.num_speakers and len(set(s.speaker for s in diar_segments)) > args.num_speakers:
            diar_segments = collapse_speakers(diar_segments, args.num_speakers)
        segments = merge_transcript_and_diarization(segments, diar_segments)
        raw_segments = normalize_segments(segments, source="mlx-whisper+sortformer")
        write_segments_jsonl(raw_segments, raw_jsonl_path)
        write_raw_txt(raw_segments, raw_txt_path, with_speakers=True)
        rendered_segments = render_segments(
            raw_segments,
            corrections=load_corrections(Path(args.corrections)) if args.corrections else [],
            lexicon=load_lexicon(Path(args.lexicon)) if args.lexicon else {},
        )
        transcript = format_output(
            rendered_segments,
            with_speakers=True,
            max_group_seconds=args.max_group_seconds,
            max_group_chars=args.max_group_chars,
        )
        print("[3/3] 合并完成", file=sys.stderr)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(transcript, encoding="utf-8")

    n_speakers = len(set(s.get("speaker") for s in raw_segments if s.get("speaker"))) if not args.no_diarize else 0
    speaker_info = f", {n_speakers} 位说话人" if not args.no_diarize else ""
    print(f"完成: {output_path} ({len(transcript)} 字{speaker_info})", file=sys.stderr)
    print(f"  raw JSONL: {raw_jsonl_path}", file=sys.stderr)
    print(f"  raw TXT: {raw_txt_path}", file=sys.stderr)
    print(str(output_path))


if __name__ == "__main__":
    main()
