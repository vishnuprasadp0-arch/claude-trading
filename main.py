#!/usr/bin/env python3
"""NSE Paper Trading Bot — CLI entry point."""
import argparse
import sys
from pathlib import Path

from trading_bot.config.settings import EXCEL_PATH
from trading_bot.utils.logging import get_logger

logger = get_logger("main")


def cmd_scrape(args):
    from trading_bot.scraper.youtube import get_video_info, get_transcript, list_channel_videos
    from trading_bot.scraper.extractor import extract_strategy
    from trading_bot.excel.workbook import WorkbookManager
    from trading_bot.excel.strategy_tab import ensure_strategy_tab, write_strategy, list_all_strategies

    excel_path = Path(args.excel) if args.excel else EXCEL_PATH

    # --channel: list videos and let user pick
    if args.channel:
        videos = _pick_videos_from_channel(args.channel, args.limit)
        if not videos:
            print("No videos selected. Exiting.")
            return
    elif args.url:
        info = get_video_info(args.url)
        videos = [info]
    else:
        print("Error: provide --url <video_url> or --channel <channel_url>")
        sys.exit(1)

    for video in videos:
        video_id = video["video_id"]
        title = video["title"]
        url = video.get("url") or args.url

        print(f"\n--- Processing: {title} ---")
        logger.info(f"Fetching transcript for {video_id}...")
        transcript = get_transcript(video_id)
        logger.info(f"Transcript: {len(transcript):,} characters")

        logger.info("Extracting strategy with LLM (Malayalam → English)...")
        strategy = extract_strategy(transcript, url, title)

        with WorkbookManager(excel_path) as mgr:
            ensure_strategy_tab(mgr.workbook)
            strategy_id = write_strategy(mgr.workbook, strategy, url)

        print(f"  ID        : {strategy_id}")
        print(f"  Name      : {strategy.get('name')}")
        print(f"  Timeframe : {strategy.get('timeframe')}")
        print(f"  Direction : {strategy.get('direction')}")
        print(f"  Indicators: {', '.join(strategy.get('indicators', []))}")

    # Print full strategy table so user can pick which to activate
    import openpyxl
    wb = openpyxl.load_workbook(excel_path)
    all_strategies = list_all_strategies(wb)

    print(f"\n{'='*72}")
    print(f"  All strategies in Strategy tab ({len(all_strategies)} total)")
    print(f"{'='*72}")
    print(f"  {'ID':<10} {'Active':<8} {'TF':<6} {'Dir':<6} {'Name'}")
    print(f"  {'-'*10} {'-'*8} {'-'*6} {'-'*6} {'-'*35}")
    for s in all_strategies:
        active_marker = "<-- ACTIVE" if s["active"] else ""
        print(f"  {s['id']:<10} {'YES' if s['active'] else 'no':<8} "
              f"{s['timeframe']:<6} {s['direction']:<6} {str(s['name'])[:40]}  {active_marker}")
    print(f"{'='*72}")
    print(f"\nTo activate a strategy: open SwingPlanner.xlsx → Strategy tab")
    print(f"  1. Set Active = FALSE on any currently active row")
    print(f"  2. Set Active = TRUE  on the row you want")
    print(f"\nThen run: python main.py run --once")


def _pick_videos_from_channel(channel_url: str, limit: int) -> list[dict]:
    from trading_bot.scraper.youtube import list_channel_videos

    print(f"Fetching videos from channel: {channel_url}")
    videos = list_channel_videos(channel_url, max_videos=limit)

    if not videos:
        print("No videos found.")
        return []

    print(f"\nFound {len(videos)} videos:\n")
    for i, v in enumerate(videos, start=1):
        dur = _fmt_duration(v.get("duration"))
        print(f"  {i:>2}. {v['title'][:70]}  [{dur}]")

    print("\nEnter video numbers to scrape (e.g. 1,3,5) or 'all', or press Enter to cancel:")
    raw = input("> ").strip()

    if not raw:
        return []
    if raw.lower() == "all":
        return videos

    selected = []
    for part in raw.split(","):
        try:
            idx = int(part.strip()) - 1
            if 0 <= idx < len(videos):
                selected.append(videos[idx])
        except ValueError:
            pass
    return selected


def _fmt_duration(seconds) -> str:
    if not seconds:
        return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def cmd_run(args):
    from trading_bot.execution.engine import run_once, run_loop

    excel_path = Path(args.excel) if args.excel else EXCEL_PATH

    if not excel_path.exists():
        logger.error(f"Excel file not found: {excel_path}")
        logger.error("Set EXCEL_PATH in .env or pass --excel <path>")
        sys.exit(1)

    if args.once:
        run_once(excel_path)
    else:
        run_loop(excel_path)


def cmd_status(args):
    import openpyxl
    from trading_bot.excel.system_tab import read_open_trades

    excel_path = Path(args.excel) if args.excel else EXCEL_PATH

    if not excel_path.exists():
        logger.error(f"Excel file not found: {excel_path}")
        sys.exit(1)

    wb = openpyxl.load_workbook(excel_path)
    trades = read_open_trades(wb)

    if not trades:
        print("No open trades.")
        return

    header = f"{'Row':<5} {'Stock':<12} {'Entry':>10} {'SL':>10} {'Target':>10} {'Qty':>6} {'Conf':<8} Date"
    print(f"\n{header}")
    print("-" * (len(header) + 6))
    for t in trades:
        print(
            f"{t['row']:<5} {str(t['stock']):<12} "
            f"{str(t['entry']):>10} {str(t['stop_loss']):>10} {str(t['target']):>10} "
            f"{str(t['quantity']):>6} {str(t['confidence']):<8} {t['entry_date']}"
        )
    print(f"\nTotal open: {len(trades)}")


def main():
    parser = argparse.ArgumentParser(
        description="NSE Paper Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape a specific video
  python main.py scrape --url https://www.youtube.com/watch?v=XXXX

  # Browse a channel and pick videos to scrape
  python main.py scrape --channel https://www.youtube.com/@synthicator-in

  # Browse and show up to 20 videos
  python main.py scrape --channel https://www.youtube.com/@synthicator-in --limit 20

  # Show open trades
  python main.py status
""",
    )
    parser.add_argument("--excel", metavar="PATH", help="Path to SwingPlanner.xlsx (overrides .env)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scrape = sub.add_parser("scrape", help="Extract strategy from a YouTube video or channel")
    p_scrape.add_argument("--url", help="Single YouTube video URL")
    p_scrape.add_argument("--channel", help="YouTube channel URL (lists videos to pick from)")
    p_scrape.add_argument("--limit", type=int, default=15, metavar="N",
                          help="Max videos to list from channel (default: 15)")
    p_scrape.set_defaults(func=cmd_scrape)

    p_run = sub.add_parser("run", help="Legacy live run path")
    p_run.add_argument("--once", action="store_true", help="Single evaluation pass then exit")
    p_run.set_defaults(func=cmd_run)

    p_status = sub.add_parser("status", help="Print open trades from the System tab")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
