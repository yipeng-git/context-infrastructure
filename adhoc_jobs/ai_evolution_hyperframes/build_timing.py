#!/usr/bin/env python3
"""Parse per-scene edge-tts SRT + audio durations into a global timeline JSON.

Output: assets/timing.json with scene windows (start/dur/audioStart) and
caption groups in GLOBAL composition time, ready to inline into index.html.
"""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
AUDIO = ROOT / "media" / "audio"

LEAD = 0.25   # silence before voice starts within a scene
TAIL = 0.55   # hold after voice ends before next scene
SCENES = [1, 2, 3, 4, 5, 6, 7]

SRT_TS = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)")


def ts_to_sec(t: str) -> float:
    h, m, s, ms = SRT_TS.match(t).groups()
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_srt(path: Path):
    cues = []
    block = []
    for line in path.read_text(encoding="utf-8").splitlines() + [""]:
        if line.strip() == "":
            if block:
                # block: [index, "start --> end", text...]
                timing = next((l for l in block if "-->" in l), None)
                if timing:
                    a, b = timing.split("-->")
                    start = ts_to_sec(a.strip())
                    end = ts_to_sec(b.strip())
                    text_lines = block[block.index(timing) + 1:]
                    text = "".join(text_lines).strip()
                    if text:
                        cues.append({"start": start, "end": end, "text": text})
                block = []
        else:
            block.append(line)
    return cues


def audio_dur(path: Path) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "csv=p=0", str(path)
    ]).decode().strip()
    return float(out)


scenes = []
captions = []
cursor = 0.0
for i in SCENES:
    adur = audio_dur(AUDIO / f"s{i}.mp3")
    audio_start = cursor + LEAD
    dur = LEAD + adur + TAIL
    scenes.append({
        "i": i,
        "start": round(cursor, 3),
        "dur": round(dur, 3),
        "audioStart": round(audio_start, 3),
        "audioDur": round(adur, 3),
    })
    raw = parse_srt(AUDIO / f"s{i}.srt")
    # Normalize: clamp end to audio end, fix tiny overlaps, shift to global time
    for j, c in enumerate(raw):
        g_start = audio_start + c["start"]
        g_end = audio_start + min(c["end"], adur)
        # prevent overlap with next cue
        if j + 1 < len(raw):
            nxt = audio_start + raw[j + 1]["start"]
            if g_end > nxt:
                g_end = nxt - 0.02
        captions.append({
            "scene": i,
            "start": round(g_start, 3),
            "end": round(g_end, 3),
            "text": c["text"],
        })
    cursor += dur

total = round(cursor, 3)
data = {"total": total, "scenes": scenes, "captions": captions}
(ROOT / "media" / "timing.json").write_text(
    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"TOTAL = {total}s ({int(total//60)}:{total%60:05.2f})")
for s in scenes:
    print(f"  scene {s['i']}: start={s['start']:>6} dur={s['dur']:>6} audioStart={s['audioStart']:>6}")
print(f"caption groups: {len(captions)}")
