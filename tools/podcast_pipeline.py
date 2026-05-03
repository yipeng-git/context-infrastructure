"""播客知识飞轮流水线。

一键串起小宇宙下载、ASR、事实层保存、阅读版生成、QA 报告和修正重建。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from transcribe_audio import (
    DEFAULT_MAX_GROUP_CHARS,
    DEFAULT_MAX_GROUP_SECONDS,
    apply_corrections,
    build_readable_groups,
    collapse_speakers,
    diarize_sortformer,
    format_output,
    format_raw_output,
    load_corrections,
    load_lexicon,
    load_segments_jsonl,
    merge_transcript_and_diarization,
    normalize_segments,
    render_segments,
    transcribe_mlx,
    write_raw_txt,
    write_segments_jsonl,
)
from xiaoyuzhou_download import download_audio, fetch_episode


AUDIO_EXTENSIONS = (".mp3", ".m4a", ".wav", ".opus")
PIPELINE_DIRNAME = "_pipeline"
DEFAULT_TERM_SUSPECTS = [
    "chargept",
    "cloudcode",
    "达疑",
    "货客",
    "潜移茫化",
    "核尔",
    "Rainseer",
    "旅 Brad",
]
OUTRO_MARKERS = [
    "YoYo Television",
    "优优独播",
    "The truth is",
    "This is my last try",
    "Oh-oh-oh",
]

CORRECTIONS_TEMPLATE = """# corrections.yaml
# 只记录人工确认或高确定性的局部修正。raw JSONL 不会被改动。
#
# 示例：
# corrections:
#   - type: speaker_remap
#     start: "01:09:13"
#     end: "01:12:14"
#     from: speaker_01
#     to: speaker_00
#     reason: diarization drift
corrections: []
"""

LEXICON_TEMPLATE = """# lexicon.yaml
# 播客级术语表。这里的替换只作用于派生文本，不修改 transcript_raw.jsonl。
replacements:
  chargept: ChatGPT
  cloudcode: Claude Code
  达疑: 答疑
  货客: 获客
  潜移茫化: 潜移默化
"""


def fmt_ts(seconds: float) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def resolve_episode_dir(target: str, output_dir: Path) -> Path:
    if target.startswith("http"):
        episode = fetch_episode(target)
        audio_path = download_audio(episode, output_dir)
        episode["audio_path"] = str(audio_path)
        metadata_path = audio_path.parent / "metadata.json"
        metadata_path.write_text(json.dumps(episode, ensure_ascii=False, indent=2), encoding="utf-8")
        return audio_path.parent

    path = Path(target)
    if path.is_file():
        return path.parent
    if path.is_dir():
        return path
    raise FileNotFoundError(f"无法识别目标: {target}")


def pipeline_dir(episode_dir: Path) -> Path:
    path = episode_dir / PIPELINE_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def pipeline_output_path(episode_dir: Path, filename: str) -> Path:
    return pipeline_dir(episode_dir) / filename


def pipeline_input_path(episode_dir: Path, filename: str) -> Path:
    preferred = episode_dir / PIPELINE_DIRNAME / filename
    if preferred.exists():
        return preferred
    legacy = episode_dir / filename
    if legacy.exists():
        return legacy
    return preferred


def existing_pipeline_or_legacy_path(episode_dir: Path, filename: str) -> Path | None:
    path = pipeline_input_path(episode_dir, filename)
    return path if path.exists() else None


def find_audio(episode_dir: Path) -> Path:
    for ext in AUDIO_EXTENSIONS:
        candidate = episode_dir / f"audio{ext}"
        if candidate.exists():
            return candidate
    for child in episode_dir.iterdir():
        if child.suffix.lower() in AUDIO_EXTENSIONS:
            return child
    raise FileNotFoundError(f"未找到音频文件: {episode_dir}")


def ensure_config_files(episode_dir: Path) -> tuple[Path, Path]:
    corrections_path = pipeline_output_path(episode_dir, "corrections.yaml")
    lexicon_path = pipeline_output_path(episode_dir, "lexicon.yaml")
    legacy_corrections_path = episode_dir / "corrections.yaml"
    legacy_lexicon_path = episode_dir / "lexicon.yaml"
    if not corrections_path.exists():
        if legacy_corrections_path.exists():
            corrections_path.write_text(legacy_corrections_path.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            corrections_path.write_text(CORRECTIONS_TEMPLATE, encoding="utf-8")
    if not lexicon_path.exists():
        if legacy_lexicon_path.exists():
            lexicon_path.write_text(legacy_lexicon_path.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            lexicon_path.write_text(LEXICON_TEMPLATE, encoding="utf-8")
    return corrections_path, lexicon_path


def load_episode_corrections(episode_dir: Path) -> list[dict]:
    path = existing_pipeline_or_legacy_path(episode_dir, "corrections.yaml")
    return load_corrections(path) if path else []


def load_episode_lexicon(episode_dir: Path) -> dict[str, str]:
    path = existing_pipeline_or_legacy_path(episode_dir, "lexicon.yaml")
    return load_lexicon(path) if path else {}


def transcribe_episode(
    episode_dir: Path,
    num_speakers: int | None,
    no_diarize: bool,
    threshold: float,
    model: str,
    diar_model: str,
    debug_files: bool,
) -> list[dict]:
    audio_path = find_audio(episode_dir)
    segments = transcribe_mlx(audio_path, model)

    if no_diarize:
        raw_segments = normalize_segments(segments, source="mlx-whisper")
        with_speakers = False
    else:
        diar_segments = diarize_sortformer(audio_path, threshold, diar_model)
        if num_speakers and len(set(s.speaker for s in diar_segments)) > num_speakers:
            diar_segments = collapse_speakers(diar_segments, num_speakers)
        segments = merge_transcript_and_diarization(segments, diar_segments)
        raw_segments = normalize_segments(segments, source="mlx-whisper+sortformer")
        with_speakers = True

    write_segments_jsonl(raw_segments, pipeline_output_path(episode_dir, "transcript_raw.jsonl"))
    if debug_files:
        write_raw_txt(raw_segments, pipeline_output_path(episode_dir, "transcript_raw.txt"), with_speakers=with_speakers)
    return raw_segments


def render_episode(
    episode_dir: Path,
    max_group_seconds: float,
    max_group_chars: int,
    debug_files: bool = False,
) -> list[dict]:
    raw_path = pipeline_input_path(episode_dir, "transcript_raw.jsonl")
    if not raw_path.exists():
        raise FileNotFoundError(f"缺少事实层文件: {raw_path}")

    raw_segments = load_segments_jsonl(raw_path)
    corrections = load_episode_corrections(episode_dir)
    lexicon = load_episode_lexicon(episode_dir)
    rendered_segments = render_segments(raw_segments, corrections=corrections, lexicon=lexicon)
    with_speakers = any(seg.get("speaker") and seg.get("speaker") != "unknown" for seg in rendered_segments)
    transcript = format_output(
        rendered_segments,
        with_speakers=with_speakers,
        max_group_seconds=max_group_seconds,
        max_group_chars=max_group_chars,
    )
    (episode_dir / "transcript.txt").write_text(transcript, encoding="utf-8")
    if debug_files:
        pipeline_output_path(episode_dir, "transcript_rendered_raw.txt").write_text(
            format_raw_output(rendered_segments, with_speakers=with_speakers),
            encoding="utf-8",
        )
    return rendered_segments


def _build_speaker_runs(segments: list[dict]) -> list[dict]:
    runs = []
    current = None
    for seg in segments:
        speaker = seg.get("speaker", "unknown")
        text = seg.get("text", "").strip()
        if not text:
            continue
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start))
        if current is None or current["speaker"] != speaker or bool(seg.get("force_break_before")):
            if current:
                runs.append(current)
            current = {
                "start": start,
                "end": end,
                "speaker": speaker,
                "texts": [text],
            }
        else:
            current["texts"].append(text)
            current["end"] = max(current["end"], end)
    if current:
        runs.append(current)
    return runs


def _issue(kind: str, severity: str, start: float, end: float, detail: str) -> dict:
    return {
        "kind": kind,
        "severity": severity,
        "start": start,
        "end": end,
        "detail": detail,
    }


def collect_qa_issues(
    segments: list[dict],
    max_group_seconds: float,
    max_group_chars: int,
) -> list[dict]:
    issues = []
    runs = _build_speaker_runs(segments)
    groups = build_readable_groups(segments, max_group_seconds, max_group_chars)

    for run in runs:
        duration = run["end"] - run["start"]
        chars = sum(len(text) for text in run["texts"])
        if duration > max_group_seconds or chars > max_group_chars:
            issues.append(_issue(
                "long_monologue",
                "medium",
                run["start"],
                run["end"],
                f"{run['speaker']} 连续 {duration:.0f}s / {chars} 字，建议检查是否 speaker drift",
            ))
        if duration > max_group_seconds * 2:
            issues.append(_issue(
                "possible_speaker_drift",
                "high",
                run["start"],
                run["end"],
                f"{run['speaker']} 连续超过 {max_group_seconds * 2:.0f}s，可能存在说话人漂移",
            ))

    for seg in segments:
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start))
        speaker = str(seg.get("speaker", "unknown"))
        text = seg.get("text", "")
        if speaker == "unknown":
            issues.append(_issue("unknown_speaker", "medium", start, end, text[:80]))
        for term in DEFAULT_TERM_SUSPECTS:
            if term in text:
                issues.append(_issue("term_suspect", "low", start, end, f"疑似误识别词: {term}"))
        for marker in OUTRO_MARKERS:
            if marker in text:
                issues.append(_issue("outro_noise", "low", start, end, f"疑似片尾/噪声: {marker}"))

    for group in groups:
        duration = float(group["end"]) - float(group["start"])
        chars = int(group["chars"])
        if duration > max_group_seconds or chars > max_group_chars:
            issues.append(_issue(
                "segment_too_long",
                "medium",
                group["start"],
                group["end"],
                f"阅读版段落仍过长: {duration:.0f}s / {chars} 字",
            ))
    return issues


def write_qa_report(episode_dir: Path, segments: list[dict], issues: list[dict]) -> Path:
    high = sum(1 for issue in issues if issue["severity"] == "high")
    medium = sum(1 for issue in issues if issue["severity"] == "medium")
    low = sum(1 for issue in issues if issue["severity"] == "low")

    lines = [
        "# Transcript QA",
        "",
        f"- 生成时间: {datetime.now().isoformat(timespec='seconds')}",
        f"- segments: {len(segments)}",
        f"- issues: {len(issues)} (high={high}, medium={medium}, low={low})",
        "",
        "## Issues",
        "",
    ]

    if not issues:
        lines.append("未发现明显风险。")
    else:
        for issue in sorted(issues, key=lambda item: (item["start"], item["kind"])):
            lines.extend([
                f"### {issue['severity']} / {issue['kind']} / {fmt_ts(issue['start'])}-{fmt_ts(issue['end'])}",
                "",
                issue["detail"],
                "",
            ])

    report_path = pipeline_output_path(episode_dir, "transcript_qa.md")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def run_qa(
    episode_dir: Path,
    max_group_seconds: float,
    max_group_chars: int,
) -> list[dict]:
    raw_path = pipeline_input_path(episode_dir, "transcript_raw.jsonl")
    if not raw_path.exists():
        raise FileNotFoundError(f"缺少事实层文件: {raw_path}")
    segments = load_segments_jsonl(raw_path)
    segments = apply_corrections(segments, load_episode_corrections(episode_dir))
    segments = render_segments(segments, lexicon=load_episode_lexicon(episode_dir))
    issues = collect_qa_issues(segments, max_group_seconds, max_group_chars)
    write_qa_report(episode_dir, segments, issues)
    return issues


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--max-group-seconds", type=float, default=DEFAULT_MAX_GROUP_SECONDS)
    parser.add_argument("--max-group-chars", type=int, default=DEFAULT_MAX_GROUP_CHARS)


def main() -> None:
    parser = argparse.ArgumentParser(description="播客知识飞轮流水线")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="下载/转写/渲染/QA 一键流程")
    run_parser.add_argument("target", help="小宇宙 URL、episode 目录或音频文件")
    run_parser.add_argument("--output-dir", default="../collected-contents")
    run_parser.add_argument("--num-speakers", type=int, default=2)
    run_parser.add_argument("--no-diarize", action="store_true")
    run_parser.add_argument("--threshold", type=float, default=0.5)
    run_parser.add_argument("--model", default="mlx-community/whisper-large-v3-turbo")
    run_parser.add_argument("--diar-model", default="mlx-community/diar_sortformer_4spk-v1-fp32")
    run_parser.add_argument("--skip-transcribe", action="store_true")
    run_parser.add_argument("--debug-files", action="store_true", help="写入 _pipeline 下的 raw/debug 文本")
    add_common_args(run_parser)

    render_parser = subparsers.add_parser("render", help="从 raw JSONL 重建阅读版 transcript")
    render_parser.add_argument("episode_dir")
    render_parser.add_argument("--debug-files", action="store_true", help="写入 _pipeline/transcript_rendered_raw.txt")
    add_common_args(render_parser)

    qa_parser = subparsers.add_parser("qa", help="只运行 transcript QA")
    qa_parser.add_argument("episode_dir")
    add_common_args(qa_parser)

    init_parser = subparsers.add_parser("init", help="创建 corrections.yaml 和 lexicon.yaml")
    init_parser.add_argument("episode_dir")

    args = parser.parse_args()

    if args.command == "run":
        episode_dir = resolve_episode_dir(args.target, Path(args.output_dir))
        if not args.skip_transcribe:
            transcribe_episode(
                episode_dir,
                num_speakers=args.num_speakers,
                no_diarize=args.no_diarize,
                threshold=args.threshold,
                model=args.model,
                diar_model=args.diar_model,
                debug_files=args.debug_files,
            )
        render_episode(episode_dir, args.max_group_seconds, args.max_group_chars, debug_files=args.debug_files)
        issues = run_qa(episode_dir, args.max_group_seconds, args.max_group_chars)
        print(json.dumps({
            "episode_dir": str(episode_dir),
            "transcript": str(episode_dir / "transcript.txt"),
            "raw_jsonl": str(pipeline_output_path(episode_dir, "transcript_raw.jsonl")),
            "qa": str(pipeline_output_path(episode_dir, "transcript_qa.md")),
            "issues": len(issues),
        }, ensure_ascii=False, indent=2))

    elif args.command == "render":
        episode_dir = Path(args.episode_dir)
        render_episode(episode_dir, args.max_group_seconds, args.max_group_chars, debug_files=args.debug_files)
        print(str(episode_dir / "transcript.txt"))

    elif args.command == "qa":
        episode_dir = Path(args.episode_dir)
        issues = run_qa(episode_dir, args.max_group_seconds, args.max_group_chars)
        print(json.dumps({
            "qa": str(pipeline_output_path(episode_dir, "transcript_qa.md")),
            "issues": len(issues),
        }, ensure_ascii=False, indent=2))

    elif args.command == "init":
        corrections_path, lexicon_path = ensure_config_files(Path(args.episode_dir))
        print(json.dumps({
            "corrections": str(corrections_path),
            "lexicon": str(lexicon_path),
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
