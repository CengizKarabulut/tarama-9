"""
Timeframe-based market scanner entrypoint.
This repository scans Aylik (1M) with all signal buckets.
"""

import asyncio
import html
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from config import LOG_LEVEL, LOG_FORMAT
from report_image import create_common_period_report_image, create_signal_report_image
from scanner import MarketScanner
from scheduler import TZ_TURKEY
from telegram_sender import get_telegram_sender

logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

BRAND_NAME = "StockMarketLab"
TARAMA_LABEL = "Aylik Bot"
TIMEFRAME_LABEL = "Aylik"
FIXED_PERIOD = "1M"
REPORTS_DIR = Path("reports")
SIGNALS_PER_IMAGE = int(os.getenv("SIGNALS_PER_IMAGE", "30"))
SUMMARY_ROWS_PER_IMAGE = int(os.getenv("SUMMARY_ROWS_PER_IMAGE", "24"))
SEND_EMPTY_BUCKET_REPORTS = os.getenv("SEND_EMPTY_BUCKET_REPORTS", "true").lower() == "true"

BUCKETS = [
    ("macd_cross", "macd_cross", "M-1"),
    ("h8", "h8", "S-M-1"),
    ("i9", "i9", "S-M-V-1"),
    ("ema", "ema", "E-V-1"),
    ("rsi_macd", "rsi_macd", "R-M-V-1"),
    ("new_scan", "new_scan", "A-M-V-1"),
    ("smi_macd", "full", "S-M-V-2"),
    ("smi_macd", "smi", "S-M-2"),
    ("rsi", "rsi", "R-V-1"),
]
ENABLED_STRATEGIES = list(dict.fromkeys(strategy for strategy, _, _ in BUCKETS))
KNOWN_PERIODS = ["15m", "30m", "45m", "1H", "2H", "4H", "1D", "1W", "1M"]


def normalize_period(period: str) -> str:
    period_map = {
        "15": "15m", "15m": "15m", "15M": "15m",
        "30": "30m", "30m": "30m", "30M": "30m",
        "45": "45m", "45m": "45m", "45M": "45m",
        "1h": "1H", "1H": "1H",
        "2h": "2H", "2H": "2H",
        "4h": "4H", "4H": "4H",
        "1d": "1D", "1D": "1D",
        "1w": "1W", "1W": "1W",
        "1mo": "1M", "1MO": "1M",
        "1m": "1M", "1M": "1M",
    }
    return period_map.get((period or "").strip(), (period or "").strip())


def resolve_scan_args(args: list[str]) -> tuple[str, str]:
    if len(args) >= 2:
        maybe_period = normalize_period(args[0])
        if maybe_period in KNOWN_PERIODS:
            return maybe_period, args[1].lower()
    if args:
        return FIXED_PERIOD, args[0].lower()
    return FIXED_PERIOD, "bist"


def balanced_chunks(items: list, max_size: int) -> list[list]:
    if not items:
        return [items]

    max_size = max(1, max_size)
    page_count = (len(items) + max_size - 1) // max_size
    base_size, extra = divmod(len(items), page_count)
    chunks = []
    start = 0
    for index in range(page_count):
        size = base_size + (1 if index < extra else 0)
        chunks.append(items[start:start + size])
        start += size
    return chunks


def indexed_chunks(items: list, max_size: int):
    start_no = 1
    for chunk in balanced_chunks(items, max_size):
        yield start_no, chunk
        start_no += len(chunk)


def bucket_results(results: tuple) -> dict[str, list[dict] | int]:
    (
        full_signals,
        smi_signals,
        rsi_signals,
        new_scan_signals,
        rsi_macd_signals,
        ema_signals,
        macd_cross_signals,
        h8_signals,
        i9_signals,
        total_scanned,
    ) = results
    return {
        "full": full_signals,
        "smi": smi_signals,
        "rsi": rsi_signals,
        "new_scan": new_scan_signals,
        "rsi_macd": rsi_macd_signals,
        "ema": ema_signals,
        "macd_cross": macd_cross_signals,
        "h8": h8_signals,
        "i9": i9_signals,
        "total_scanned": total_scanned,
    }


def send_bucket_summary(
    sender,
    market_type: str,
    period: str,
    bucket_label: str,
    signals: list[dict],
    total_scanned: int,
):
    now = datetime.now(TZ_TURKEY).strftime("%Y-%m-%d %H:%M")
    ordered_signals = sorted(signals, key=lambda item: str(item.get("symbol", "")))
    report_label = f"{TARAMA_LABEL} - {bucket_label}"

    if not ordered_signals:
        if not SEND_EMPTY_BUCKET_REPORTS:
            return
        image_path = create_signal_report_image(
            brand_name=BRAND_NAME,
            tarama_label=report_label,
            market_type=market_type.upper(),
            period=period,
            timestamp=now,
            total_scanned=total_scanned,
            total_signals=0,
            signals=[],
            start_index=1,
            page=1,
            total_pages=1,
            output_dir=REPORTS_DIR,
        )
        caption = (
            f"<b>{BRAND_NAME}</b>\n"
            f"<b>{html.escape(report_label)}</b> | <code>{html.escape(market_type.upper())} {html.escape(period)}</code>\n"
            f"<i>Sinyal yok.</i>"
        )
        if not sender.send_photo(str(image_path), caption=caption):
            logger.error("%s %s %s icin gorsel bildirim gonderilemedi.", report_label, market_type, period)
        return

    chunks = list(indexed_chunks(ordered_signals, SIGNALS_PER_IMAGE))
    for index, (start_no, chunk) in enumerate(chunks, start=1):
        end_no = start_no + len(chunk) - 1
        image_path = create_signal_report_image(
            brand_name=BRAND_NAME,
            tarama_label=report_label,
            market_type=market_type.upper(),
            period=period,
            timestamp=now,
            total_scanned=total_scanned,
            total_signals=len(ordered_signals),
            signals=chunk,
            start_index=start_no,
            page=index,
            total_pages=len(chunks),
            output_dir=REPORTS_DIR,
        )
        caption = (
            f"<b>{BRAND_NAME}</b>\n"
            f"<b>{html.escape(report_label)}</b> | <code>{html.escape(market_type.upper())} {html.escape(period)}</code>\n"
            f"<code>Liste {index}/{len(chunks)} | {start_no}-{end_no}/{len(ordered_signals)}</code>"
        )
        if not sender.send_photo(str(image_path), caption=caption):
            logger.error("%s %s %s icin gorsel bildirim gonderilemedi.", report_label, market_type, period)
            return
        time.sleep(1)


async def main_scan_logic(market_type: str, period: str = FIXED_PERIOD, use_state: bool = True):
    scanner = MarketScanner()
    sender = get_telegram_sender()
    period = normalize_period(period) or FIXED_PERIOD

    logger.info(
        "%s baslatiliyor: timeframe=%s market=%s period=%s state=%s strategies=%s",
        TARAMA_LABEL,
        TIMEFRAME_LABEL,
        market_type,
        period,
        use_state,
        ",".join(ENABLED_STRATEGIES),
    )

    try:
        raw_results = await scanner.scan_market(
            market_type=market_type,
            period=period,
            strategies=ENABLED_STRATEGIES,
            use_state=use_state,
        )
        results = bucket_results(raw_results)
        total_scanned = int(results["total_scanned"])

        bucket_payloads = []
        for _, bucket_key, bucket_label in BUCKETS:
            signals = list(results[bucket_key])
            send_bucket_summary(sender, market_type, period, bucket_label, signals, total_scanned)
            bucket_payloads.append({"key": bucket_key, "label": bucket_label, "signals": signals})

        scan_result = {
            "period": period,
            "market_type": market_type,
            "total_scanned": total_scanned,
            "buckets": bucket_payloads,
        }
        send_common_scan_summary(scan_result)
        return scan_result
    except Exception as exc:
        logger.error("%s sirasinda hata: %s", TARAMA_LABEL, exc, exc_info=True)
        sender.send_error(f"{BRAND_NAME}\n{TARAMA_LABEL} sirasinda hata: {html.escape(str(exc))}")
        return None


def send_common_scan_summary(scan_result: dict):
    sender = get_telegram_sender()
    now = datetime.now(TZ_TURKEY).strftime("%Y-%m-%d %H:%M")
    symbol_map: dict[str, list[str]] = {}
    symbol_data: dict[str, dict] = {}

    for bucket in scan_result["buckets"]:
        bucket_label = bucket["label"]
        seen_in_bucket = set()
        for signal in bucket["signals"]:
            symbol = str(signal.get("symbol", ""))
            if not symbol or symbol in seen_in_bucket:
                continue
            seen_in_bucket.add(symbol)
            symbol_map.setdefault(symbol, [])
            symbol_data.setdefault(symbol, signal)
            if bucket_label not in symbol_map[symbol]:
                symbol_map[symbol].append(bucket_label)

    repeated = {symbol: labels for symbol, labels in symbol_map.items() if len(labels) > 1}
    if not repeated:
        return

    summary_rows = sorted(
        (
            {
                "symbol": symbol,
                "scans": repeated[symbol],
                "change": symbol_data.get(symbol, {}).get("change"),
                "daily_change": symbol_data.get(symbol, {}).get("daily_change", symbol_data.get(symbol, {}).get("change")),
                "current_price": symbol_data.get(symbol, {}).get("current_price", symbol_data.get(symbol, {}).get("close")),
            }
            for symbol in repeated
        ),
        key=lambda row: (-len(row["scans"]), row["symbol"]),
    )
    summary_chunks = balanced_chunks(summary_rows, SUMMARY_ROWS_PER_IMAGE)
    for index, chunk in enumerate(summary_chunks, start=1):
        image_path = create_common_period_report_image(
            brand_name=BRAND_NAME,
            tarama_label=TARAMA_LABEL,
            timestamp=now,
            rows=chunk,
            page=index,
            total_pages=len(summary_chunks),
            total_symbols=len(summary_rows),
            output_dir=REPORTS_DIR,
            summary_title=f"{TARAMA_LABEL} - Coklu Sinyal Ozeti",
            column_title="Tarama Kodlari",
            empty_text="Birden fazla sinyal kodunda ortak hisse yok",
            filename_suffix="coklu-sinyal-ozeti",
        )
        caption = (
            f"<b>{BRAND_NAME}</b>\n"
            f"<b>{TARAMA_LABEL} - Coklu Sinyal Ozeti</b>\n"
            f"<code>Liste {index}/{len(summary_chunks)} | {len(chunk)}/{len(summary_rows)} hisse</code>"
        )
        sender.send_photo(str(image_path), caption=caption)
        time.sleep(1)


async def run_fixed_scan(market_type: str = "bist", period: str = FIXED_PERIOD, use_state: bool = True):
    await main_scan_logic(market_type, period, use_state=use_state)


async def run_bot():
    force = "--force" in sys.argv
    nostate = "--nostate" in sys.argv
    args = [arg for arg in sys.argv[1:] if arg not in ["--force", "--nostate"]]

    if args:
        command = args[0]
        command_args = args[1:]
        if command == "scan":
            period, market_type = resolve_scan_args(command_args)
            await main_scan_logic(market_type, period, use_state=(not nostate))
        elif command == "multi":
            period, market_type = resolve_scan_args(command_args)
            await run_fixed_scan(market_type, period, use_state=(not nostate))
        elif command == "auto":
            from scheduler import get_scheduler

            scheduler = get_scheduler()
            auto_args = [arg for arg in command_args if not arg.startswith("--")]
            market_type = auto_args[0].lower() if auto_args else "bist"

            async def run_fixed_scan_with_state(selected_market_type):
                await run_fixed_scan(selected_market_type, FIXED_PERIOD, use_state=(not nostate))

            await scheduler.run_once_if_needed(
                run_fixed_scan_with_state,
                market_type=market_type,
                force=force,
            )
        else:
            logger.warning("Bilinmeyen komut: %s", command)
            sys.exit(1)
    else:
        from scheduler import get_scheduler

        scheduler = get_scheduler()
        await scheduler.start(run_fixed_scan, market_type="bist")


if __name__ == "__main__":
    asyncio.run(run_bot())
