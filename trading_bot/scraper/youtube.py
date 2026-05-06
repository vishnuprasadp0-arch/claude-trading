import re
from trading_bot.utils.logging import get_logger

logger = get_logger(__name__)

_TRANSCRIPT_LANGS = ["ml", "en", "en-IN"]


def get_video_info(url: str) -> dict:
    import yt_dlp
    ydl_opts = {"quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        video_id = info.get("id") or _extract_video_id(url)
        return {
            "video_id": video_id,
            "title": info.get("title", "Unknown"),
            "duration": info.get("duration"),
        }


def list_channel_videos(channel_url: str, max_videos: int = 15) -> list[dict]:
    """Return the most recent videos from a channel without downloading."""
    import yt_dlp
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "playlistend": max_videos,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)
        entries = info.get("entries") or []
        videos = []
        for e in entries:
            vid_id = e.get("id")
            if vid_id:
                videos.append({
                    "video_id": vid_id,
                    "title": e.get("title", "Unknown"),
                    "url": f"https://www.youtube.com/watch?v={vid_id}",
                    "duration": e.get("duration"),
                })
        return videos


def _join_snippets(fetched) -> str:
    """Join transcript snippets regardless of whether they are dicts or objects."""
    parts = []
    for s in fetched:
        if hasattr(s, "text"):
            parts.append(s.text or "")
        elif hasattr(s, "get"):
            parts.append(s.get("text", ""))
    return " ".join(parts)


def get_transcript(video_id: str) -> str:
    """Fetch transcript using youtube-transcript-api v1.x, preferring Malayalam."""
    from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled

    api = YouTubeTranscriptApi()

    # Try preferred languages directly
    try:
        fetched = api.fetch(video_id, languages=_TRANSCRIPT_LANGS)
        text = _join_snippets(fetched)
        logger.info(f"Transcript fetched for {video_id} ({len(text):,} chars)")
        return text
    except NoTranscriptFound:
        pass
    except TranscriptsDisabled:
        raise RuntimeError(f"Transcripts disabled for {video_id}")

    # Fall back: list all available transcripts and pick the best one
    try:
        transcript_list = api.list(video_id)
        for lang in _TRANSCRIPT_LANGS + ["hi"]:
            for generated in (False, True):
                try:
                    transcripts = [
                        t for t in transcript_list
                        if t.language_code.startswith(lang[:2])
                        and t.is_generated == generated
                    ]
                    if transcripts:
                        text = _join_snippets(transcripts[0].fetch())
                        logger.info(f"Transcript via fallback: lang={lang} generated={generated}")
                        return text
                except Exception:
                    continue

        # Last resort: first available
        first = next(iter(transcript_list))
        text = _join_snippets(first.fetch())
        logger.info(f"Transcript via last resort: {first.language_code}")
        return text

    except Exception as e:
        raise RuntimeError(f"No transcript available for {video_id}: {e}")


def _extract_video_id(url: str) -> str:
    for pattern in [r"youtube\.com/watch\?v=([^&]+)", r"youtu\.be/([^?]+)"]:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    raise ValueError(f"Cannot extract video ID from: {url}")
