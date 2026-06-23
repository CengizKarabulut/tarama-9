"""
Weekly performance report for a single timeframe repository.
"""

import asyncio
import html
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from main import BRAND_NAME, TARAMA_LABEL
from report_image import create_weekly_performance_report_image
from scanner import MarketScanner
from telegram_sender import get_telegram_sender
from tvDatafeed import Interval


PERIOD_ORDER = ["15m", "30m", "45m", "1H", "2H", "4H", "1D", "1W", "1M"]
PERIOD_NAMES = {
    "15m": "15 DAKIKA",
    "30m": "30 DAKIKA",
    "45m": "45 DAKIKA",
    "1H": "1 SAAT",
    "2H": "2 SAAT",
    "4H": "4 SAAT",
    "1D": "GUNLUK",
    "1W": "HAFTALIK",
    "1M": "AYLIK",
}

STRATEGY_META = {
    "macd_cross": {
        "state_key": "last_sent_macd_cross",
        "title": "M-1 - MACD Pozitif Kesisim",
    },
    "h8": {
        "state_key": "last_sent_h8",
        "title": "S-M-1 - SMI/MACD Momentum",
    },
    "i9": {
        "state_key": "last_sent_i9",
        "title": "S-M-V-1 - SMI/MACD Guclu Onay",
    },
    "ema": {
        "state_key": "last_sent_ema",
        "title": "E-V-1 - EMA Trend + Hacim",
    },
    "rsi_macd": {
        "state_key": "last_sent_rsi_macd",
        "title": "R-M-V-1 - RSI + MACD + Hacim",
    },
    "new_scan": {
        "state_key": "last_sent_new_scan",
        "title": "A-M-V-1 - SMA + MACD + Hacim",
    },
    "full": {
        "state_key": "last_sent_smi_macd",
        "title": "S-M-V-2 - SMI/MACD Full",
        "is_full": True,
    },
    "smi": {
        "state_key": "last_sent_smi_macd",
        "title": "S-M-2 - SMI/MACD Erken",
        "is_full": False,
    },
    "rsi": {
        "state_key": "last_sent_rsi",
        "title": "R-V-1 - RSI Momentum",
    },
}

DIVIDER = "<b>==============================</b>"
REPORTS_DIR = Path("reports")
WEEKLY_IMAGE_MAX_ROWS = int(os.getenv("WEEKLY_IMAGE_MAX_ROWS", "30"))


async def get_current_price(symbol: str, scanner: MarketScanner) -> float | None:
    try:
        df = scanner.tv.get_hist(symbol, "BIST", interval=Interval.in_daily, n_bars=5)
        if df is not None and not df.empty:
            return float(df.iloc[-1]["close"])
    except Exception as exc:
        print(f"Fiyat cekme hatasi ({symbol}): {exc}")
    return None


def format_time(value: str) -> str:
    try:
        return datetime.fromisoformat(str(value)).strftime("%d/%m %H:%M")
    except Exception:
        return str(value)


def should_include_entry(data, meta: dict) -> bool:
    if "is_full" not in meta:
        return True
    return isinstance(data, dict) and bool(data.get("is_full")) is meta["is_full"]


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


def write_weekly_report_images(report_title: str, rows: list[dict]) -> list[Path]:
    chunks = balanced_chunks(rows, WEEKLY_IMAGE_MAX_ROWS)
    return [
        create_weekly_performance_report_image(
            brand_name=BRAND_NAME,
            tarama_label=TARAMA_LABEL,
            report_title=report_title,
            timestamp=datetime.now().strftime("%d.%m.%Y %H:%M"),
            rows=chunk,
            page=index,
            total_pages=len(chunks),
            total_rows=len(rows),
            output_dir=REPORTS_DIR,
        )
        for index, chunk in enumerate(chunks, start=1)
    ]


async def build_rows(state: dict, strategy_key: str) -> tuple[dict[str, list[dict]], list[dict]]:
    meta = STRATEGY_META[strategy_key]
    entries = state.get(meta["state_key"], {})
    grouped = {period: [] for period in PERIOD_ORDER}
    unknown_period = []
    scanner = MarketScanner()
    price_cache: dict[str, float | None] = {}

    for symbol_period, data in entries.items():
        if "_" not in symbol_period or not should_include_entry(data, meta):
            continue

        symbol, period = symbol_period.rsplit("_", 1)
        if isinstance(data, dict):
            signal_price = float(data.get("price", 0) or 0)
            timestamp = data.get("time", "")
        else:
            signal_price = 0.0
            timestamp = data

        if symbol not in price_cache:
            price_cache[symbol] = await get_current_price(symbol, scanner)
        current_price = price_cache[symbol]

        change = None
        if signal_price > 0 and current_price:
            change = ((current_price - signal_price) / signal_price) * 100

        row = {
            "symbol": symbol,
            "period": period,
            "time": format_time(timestamp),
            "signal_price": signal_price,
            "current_price": current_price,
            "change": change,
        }

        if period in grouped:
            grouped[period].append(row)
        else:
            unknown_period.append(row)

    return grouped, unknown_period


def stats_block(title: str, rows: list[dict]) -> str:
    measured = [row for row in rows if row["change"] is not None]
    out = f"<b>{html.escape(title)} ISTATISTIGI</b>\n"
    out += f"- Toplam sinyal: <b>{len(rows)}</b>\n"
    out += f"- Olculebilir: <b>{len(measured)}</b>\n"

    if not measured:
        out += "<i>Bu dilimde fiyatli sinyal yok.</i>\n"
        return out

    wins = [row for row in measured if row["change"] >= 0]
    losses = [row for row in measured if row["change"] < 0]
    average = sum(row["change"] for row in measured) / len(measured)
    win_rate = len(wins) / len(measured) * 100
    best = max(measured, key=lambda row: row["change"])
    worst = min(measured, key=lambda row: row["change"])

    out += f"- Kazancli: <b>{len(wins)}</b> | Kayipli: <b>{len(losses)}</b>\n"
    out += f"- Basari orani: <b>%{win_rate:.1f}</b>\n"
    out += f"- Ortalama getiri: <b>%{average:+.2f}</b>\n"
    out += f"- En iyi: <b>{html.escape(best['symbol'])}</b> %{best['change']:+.2f}\n"
    out += f"- En kotu: <b>{html.escape(worst['symbol'])}</b> %{worst['change']:+.2f}\n"
    return out


def signal_lines(rows: list[dict]) -> str:
    lines = []
    for row in rows:
        symbol = html.escape(row["symbol"])
        if row["change"] is not None:
            lines.append(
                f"- <b>{symbol}</b> - {row['time']}\n"
                f"  <code>%{row['change']:+.2f} "
                f"({row['signal_price']:.2f} -> {row['current_price']:.2f})</code>"
            )
        elif row["current_price"] is not None:
            lines.append(
                f"- <b>{symbol}</b> - {row['time']}\n"
                f"  <code>Guncel: {row['current_price']:.2f}; giris fiyati yok</code>"
            )
        else:
            lines.append(f"- <b>{symbol}</b> - {row['time']}\n  <code>Veri alinamadi</code>")
    return "\n".join(lines)


async def build_strategy_report(strategy_key: str, state: dict) -> tuple[list[str], list[Path]]:
    grouped, unknown_period = await build_rows(state, strategy_key)
    meta = STRATEGY_META[strategy_key]
    display_title = meta["title"]
    messages = [
        (
            f"{DIVIDER}\n"
            f"<b>{html.escape(BRAND_NAME)}</b>\n"
            f"<b>{html.escape(TARAMA_LABEL)} HAFTALIK RAPOR</b>\n"
            f"<b>{html.escape(display_title)}</b>\n"
            f"<code>{datetime.now().strftime('%d.%m.%Y %H:%M')}</code>\n"
            f"{DIVIDER}"
        )
    ]

    all_rows = []
    for period in PERIOD_ORDER:
        rows = grouped[period]
        if not rows:
            continue
        rows.sort(key=lambda row: (row["change"] is None, -(row["change"] or 0)))
        all_rows.extend(rows)
        title = PERIOD_NAMES[period]
        messages.append(
            f"<b>{html.escape(display_title)} - {title}</b>\n\n"
            f"{signal_lines(rows)}\n\n"
            f"{stats_block(title, rows)}"
        )

    if unknown_period:
        unknown_period.sort(key=lambda row: (row["change"] is None, -(row["change"] or 0)))
        all_rows.extend(unknown_period)
        messages.append(
            f"<b>{html.escape(display_title)} - DIGER</b>\n\n"
            f"{signal_lines(unknown_period)}\n\n"
            f"{stats_block('DIGER', unknown_period)}"
        )

    if not all_rows:
        return [], []

    distribution = "\n".join(
        f"- {PERIOD_NAMES[period]}: {len(grouped[period])}"
        for period in PERIOD_ORDER
        if grouped[period]
    )
    messages.append(
        f"{DIVIDER}\n"
        f"<b>{html.escape(display_title)} GENEL TOPLAM</b>\n\n"
        f"{stats_block('GENEL', all_rows)}\n"
        f"<b>Zaman dilimi dagilimi:</b>\n{distribution}\n"
        f"{DIVIDER}"
    )
    return messages, write_weekly_report_images(display_title, all_rows)


async def generate_weekly_report() -> list[str]:
    messages, _ = await generate_weekly_report_with_images()
    return messages


async def generate_weekly_report_with_images() -> tuple[list[str], list[Path]]:
    state_file = "state.json"
    if not os.path.exists(state_file):
        return ["<b>state.json bulunamadi.</b>"], []

    with open(state_file, "r", encoding="utf-8") as file:
        state = json.load(file)

    all_messages: list[str] = []
    all_image_paths: list[Path] = []
    for strategy_key in STRATEGY_META:
        messages, image_paths = await build_strategy_report(strategy_key, state)
        all_messages.extend(messages)
        all_image_paths.extend(image_paths)

    if not all_messages:
        return [f"<b>{html.escape(TARAMA_LABEL)} icin bu hafta sinyal uretilmedi.</b>"], []
    return all_messages, all_image_paths


if __name__ == "__main__":
    async def main():
        _, image_paths = await generate_weekly_report_with_images()
        sender = get_telegram_sender()
        for index, image_path in enumerate(image_paths):
            caption = f"<b>{html.escape(TARAMA_LABEL)} Haftalik Rapor</b>"
            if len(image_paths) > 1:
                caption += f" | Gorsel {index + 1}/{len(image_paths)}"
            sender.send_photo(str(image_path), caption=caption)
            time.sleep(1)

    asyncio.run(main())
