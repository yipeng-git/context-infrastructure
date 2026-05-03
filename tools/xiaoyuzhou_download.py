"""小宇宙播客下载工具

从小宇宙 FM 下载播客单集音频并保存元数据。
通过网页 __NEXT_DATA__ 解析公开播客信息，无需登录。

用法:
    python tools/xiaoyuzhou_download.py "https://www.xiaoyuzhoufm.com/episode/xxx"
    python tools/xiaoyuzhou_download.py "https://www.xiaoyuzhoufm.com/episode/xxx" --output-dir tmp/podcasts
    python tools/xiaoyuzhou_download.py "https://www.xiaoyuzhoufm.com/episode/xxx" --info-only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import httpx

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def extract_eid(url: str) -> str:
    match = re.search(r"episode/([a-f0-9]+)", url)
    if not match:
        raise ValueError(f"无法从 URL 提取 episode ID: {url}")
    return match.group(1)


def safe_filename(name: str, max_len: int = 120) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "_", name).strip()
    return name[:max_len] if name else "untitled"


def fetch_episode(url: str) -> dict:
    """通过网页 __NEXT_DATA__ 获取单集信息"""
    eid = extract_eid(url)
    page_url = f"https://www.xiaoyuzhoufm.com/episode/{eid}"

    with httpx.Client(headers=HEADERS, timeout=60, follow_redirects=True) as client:
        resp = client.get(page_url)
        resp.raise_for_status()

    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        resp.text,
    )
    if not match:
        raise RuntimeError(f"无法从页面解析数据 (eid={eid})")

    next_data = json.loads(match.group(1))
    props = next_data.get("props", {}).get("pageProps", {})
    ep = props.get("episode") or props.get("episodeData") or props
    podcast = ep.get("podcast", {})
    enclosure = ep.get("enclosure", {})

    audio_url = enclosure.get("url", "")
    if not audio_url:
        media_key = ep.get("mediaKey", "")
        if media_key and media_key.startswith("http"):
            audio_url = media_key

    return {
        "eid": eid,
        "title": ep.get("title", ""),
        "podcast_title": podcast.get("title", ""),
        "description": ep.get("description", ""),
        "shownotes": ep.get("shownotes", ""),
        "duration": ep.get("duration", 0),
        "published_at": ep.get("pubDate", ""),
        "audio_url": audio_url,
        "episode_url": page_url,
        "cover_url": (ep.get("image") or {}).get("picUrl", ""),
    }


def guess_extension(url: str) -> str:
    path = url.lower().split("?")[0]
    for ext in (".mp3", ".m4a", ".wav", ".opus"):
        if path.endswith(ext):
            return ext
    return ".m4a"


def download_audio(episode: dict, output_dir: Path) -> Path:
    """流式下载音频"""
    audio_url = episode["audio_url"]
    if not audio_url:
        raise ValueError(f"单集没有音频链接: {episode['title']}")

    ext = guess_extension(audio_url)
    ep_dir = output_dir / safe_filename(episode["podcast_title"], 80) / safe_filename(episode["title"])
    ep_dir.mkdir(parents=True, exist_ok=True)
    filepath = ep_dir / f"audio{ext}"

    if filepath.exists() and filepath.stat().st_size > 0:
        print(f"音频已存在，跳过: {filepath}", file=sys.stderr)
        return filepath

    temp_path = filepath.with_suffix(filepath.suffix + ".tmp")
    try:
        with httpx.Client(headers=HEADERS, timeout=60, follow_redirects=True) as client:
            with client.stream("GET", audio_url) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                downloaded = 0
                with open(temp_path, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = downloaded / total * 100
                            mb = downloaded / 1024 / 1024
                            total_mb = total / 1024 / 1024
                            sys.stderr.write(f"\r下载中: {pct:.1f}% ({mb:.1f}MB / {total_mb:.1f}MB)")
                            sys.stderr.flush()
                if total:
                    print(file=sys.stderr)
        temp_path.rename(filepath)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise

    return filepath


def format_duration(seconds: int) -> str:
    if not seconds:
        return "未知"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}小时{m}分钟" if h else f"{m}分{s}秒"


def main():
    parser = argparse.ArgumentParser(description="小宇宙播客下载工具")
    parser.add_argument("url", help="播客单集链接 (xiaoyuzhoufm.com/episode/xxx)")
    parser.add_argument("--output-dir", "-o", default="../collected-contents", help="输出目录 (默认 collected-contents)")
    parser.add_argument("--info-only", action="store_true", help="只显示信息，不下载")
    args = parser.parse_args()

    episode = fetch_episode(args.url)

    if args.info_only:
        print(json.dumps(episode, ensure_ascii=False, indent=2))
        return

    output_dir = Path(args.output_dir)
    print(f"标题: {episode['title']}", file=sys.stderr)
    print(f"播客: {episode['podcast_title']}", file=sys.stderr)
    print(f"时长: {format_duration(episode['duration'])}", file=sys.stderr)

    audio_path = download_audio(episode, output_dir)
    ep_dir = audio_path.parent

    metadata_path = ep_dir / "metadata.json"
    episode["audio_path"] = str(audio_path)
    metadata_path.write_text(json.dumps(episode, ensure_ascii=False, indent=2), encoding="utf-8")

    result = {
        "title": episode["title"],
        "podcast_title": episode["podcast_title"],
        "duration": episode["duration"],
        "audio_path": str(audio_path),
        "metadata_path": str(metadata_path),
        "episode_dir": str(ep_dir),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
