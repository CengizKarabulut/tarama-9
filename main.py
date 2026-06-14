"""
Single strategy market scanner entrypoint.
This repository intentionally reports only Tarama 9.
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
from report_image import create_signal_report_image
from scanner import MarketScanner
from scheduler import TZ_TURKEY
from telegram_sender import get_telegram_sender

logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

BRAND_NAME = "StockMarketLab"
TARAMA_LABEL = "Tarama 9"
STRATEGY_KEY = "rsi"
SIGNAL_BUCKET = "rsi"
PERIODS = ["15m", "1H", "4H", "1D", "1W", "1M"]
REPORTS_DIR = Path("reports")
SIGNALS_PER_IMAGE = int(os.getenv("SIGNALS_PER_IMAGE", "30"))


def normalize_period(period: str) -> str:
    period_map = {
        "15m": "15m", "15M": "15m",
        "1h": "1H", "1H": "1H",
        "4h": "4H", "4H": "4H",
        "1d": "1D", "1D": "1D",
        "1w": "1W", "1W": "1W",
        "1mo": "1M", "1MO": "1M",
        "1m": "1M", "1M": "1M",
    }
    return period_map.get(period.strip(), period.strip())


def parse_period_selection(period_selection: str) -> list[str]:
    selection = (period_selection or "all").strip()
    if selection.lower() in {"all", "hepsi", "multi"}:
        return PERIODS

    selected_periods: list[str] = []
    for raw_period in selection.replace(";", ",").split(","):
        if not raw_period.strip():
            continue
        period = normalize_period(raw_period)
        if period not in PERIODS:
            raise ValueError(f"Gecersiz zaman dilimi: {raw_period}")
        if period not in selected_periods:
            selected_periods.append(period)

    return selected_periods or PERIODS


def format_signal_table(signals: list[dict], start_index: int = 1) -> str:
    rows = [
        "No Sembol       Deg%    Kapanis",
        "-- -------- -------- ----------",
    ]
    for offset, signal in enumerate(signals, start=start_index):
        symbol = str(signal.get("symbol", ""))[:8]
        close = float(signal.get("close", 0) or 0)
        change = float(signal.get("change", 0) or 0)
        rows.append(f"{offset:>2} {symbol:<8} {change:>+7.2f}% {close:>10.2f}")
    return "\n".join(rows)


def chunked(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def bucket_results(results: tuple) -> dict[str, list[dict]]:
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


def send_fallback_text(sender, market_type: str, period: str, signals: list[dict], total_scanned: int):
    now = datetime.now(TZ_TURKEY).strftime("%Y-%m-%d %H:%M")
    ordered_signals = sorted(signals, key=lambda item: str(item.get("symbol", "")))
    base_header = (
        f"<b>{BRAND_NAME}</b>\n"
        f"<b>{TARAMA_LABEL}</b>\n"
        f"<code>{html.escape(market_type.upper())} | {html.escape(period)} | "
        f"{total_scanned} sembol | {len(ordered_signals)} sinyal</code>\n"
        f"<code>{now}</code>"
    )

    if not ordered_signals:
        sender.send_message(base_header + "\n\n<i>Sinyal yok.</i>")
        return

    chunks = list(chunked(ordered_signals, SIGNALS_PER_IMAGE))
    for index, chunk in enumerate(chunks, start=1):
        start_no = (index - 1) * SIGNALS_PER_IMAGE + 1
        end_no = start_no + len(chunk) - 1
        table = html.escape(format_signal_table(chunk, start_no))
        msg = (
            base_header
            + f"\n<code>Liste {index}/{len(chunks)} | {start_no}-{end_no}/{len(ordered_signals)}</code>\n\n"
            + f"<pre>{table}</pre>"
        )
        sender.send_message(msg)
        time.sleep(1)


def send_period_summary(sender, market_type: str, period: str, signals: list[dict], total_scanned: int):
    now = datetime.now(TZ_TURKEY).strftime("%Y-%m-%d %H:%M")
    ordered_signals = sorted(signals, key=lambda item: str(item.get("symbol", "")))

    if not ordered_signals:
        image_path = create_signal_report_image(
            brand_name=BRAND_NAME,
            tarama_label=TARAMA_LABEL,
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
            f"<b>{TARAMA_LABEL}</b> | <code>{html.escape(market_type.upper())} {html.escape(period)}</code>\n"
            f"<i>Sinyal yok.</i>"
        )
        if not sender.send_photo(str(image_path), caption=caption):
            send_fallback_text(sender, market_type, period, ordered_signals, total_scanned)
        return

    chunks = list(chunked(ordered_signals, SIGNALS_PER_IMAGE))
    for index, chunk in enumerate(chunks, start=1):
        start_no = (index - 1) * SIGNALS_PER_IMAGE + 1
        end_no = start_no + len(chunk) - 1
        image_path = create_signal_report_image(
            brand_name=BRAND_NAME,
            tarama_label=TARAMA_LABEL,
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
            f"<b>{TARAMA_LABEL}</b> | <code>{html.escape(market_type.upper())} {html.escape(period)}</code>\n"
            f"<code>Liste {index}/{len(chunks)} | {start_no}-{end_no}/{len(ordered_signals)}</code>"
        )
        if not sender.send_photo(str(image_path), caption=caption):
            send_fallback_text(sender, market_type, period, ordered_signals, total_scanned)
            return
        time.sleep(1)


async def main_scan_logic(market_type: str, period: str, use_state: bool = True):
    scanner = MarketScanner()
    sender = get_telegram_sender()
    period = normalize_period(period)

    logger.info(
        "%s baslatiliyor: market=%s period=%s state=%s",
        TARAMA_LABEL,
        market_type,
        period,
        use_state,
    )

    try:
        raw_results = await scanner.scan_market(
            market_type=market_type,
            period=period,
            strategies=[STRATEGY_KEY],
            use_state=use_state,
        )
        results = bucket_results(raw_results)
        signals = results[SIGNAL_BUCKET]
        total_scanned = results["total_scanned"]

        send_period_summary(sender, market_type, period, signals, total_scanned)

        return {
            "period": period,
            "signals": signals,
            "total_scanned": total_scanned,
        }
    except Exception as exc:
        logger.error("%s sirasinda hata: %s", TARAMA_LABEL, exc, exc_info=True)
        sender.send_error(f"{BRAND_NAME}\n{TARAMA_LABEL} sirasinda hata: {html.escape(str(exc))}")
        return None


def send_final_summary(all_results: list[dict]):
    sender = get_telegram_sender()
    symbol_map: dict[str, list[str]] = {}
    for result in all_results:
        period = result["period"]
        for signal in result["signals"]:
            symbol = str(signal.get("symbol", ""))
            symbol_map.setdefault(symbol, []).append(period)

    repeated = {symbol: periods for symbol, periods in symbol_map.items() if len(periods) > 1}
    if not repeated:
        return

    lines = [f"<b>{BRAND_NAME}</b>", f"<b>{TARAMA_LABEL} - Coklu Periyot Ozeti</b>"]
    for symbol in sorted(repeated):
        periods = ", ".join(repeated[symbol])
        lines.append(f"- <code>{html.escape(symbol)}</code>: {html.escape(periods)}")

    sender.send_message("\n".join(lines))


async def run_selected_periods(market_type: str = "bist", period_selection: str = "all", use_state: bool = True):
    selected_periods = parse_period_selection(period_selection)
    all_results = []
    for period in selected_periods:
        result = await main_scan_logic(market_type, period, use_state=use_state)
        if result:
            all_results.append(result)
        await asyncio.sleep(3)

    if len(selected_periods) > 1 and all_results:
        send_final_summary(all_results)


async def run_multi_scan(market_type: str = "bist", use_state: bool = True):
    await run_selected_periods(market_type, "all", use_state=use_state)


async def run_bot():
    force = "--force" in sys.argv
    nostate = "--nostate" in sys.argv
    args = [arg for arg in sys.argv[1:] if arg not in ["--force", "--nostate"]]

    if args:
        command = args[0]
        if command == "scan":
            period = args[1] if len(args) > 1 else "1D"
            market_type = args[2].lower() if len(args) > 2 else "bist"
            await main_scan_logic(market_type, period, use_state=(not nostate))
        elif command == "multi":
            market_type = args[1].lower() if len(args) > 1 else "bist"
            period_selection = args[2] if len(args) > 2 else "all"
            await run_selected_periods(market_type, period_selection, use_state=(not nostate))
        elif command == "auto":
            from scheduler import get_scheduler

            scheduler = get_scheduler()
            auto_args = args[1:]
            market_type = auto_args[0].lower() if auto_args else "bist"

            async def run_multi_scan_with_state(selected_market_type):
                await run_multi_scan(selected_market_type, use_state=(not nostate))

            await scheduler.run_once_if_needed(
                run_multi_scan_with_state,
                market_type=market_type,
                force=force,
            )
        else:
            logger.warning("Bilinmeyen komut: %s", command)
            sys.exit(1)
    else:
        from scheduler import get_scheduler

        scheduler = get_scheduler()
        await scheduler.start(run_multi_scan, market_type="bist")


if __name__ == "__main__":
    asyncio.run(run_bot())