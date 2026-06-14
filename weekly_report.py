"""
Weekly performance report for a single tarama repository.
"""

import asyncio
import html
import json
import os
import sys
import time
from datetime import datetime

from main import BRAND_NAME, SIGNAL_BUCKET, TARAMA_LABEL
from scanner import MarketScanner
from telegram_sender import get_telegram_sender
from tvDatafeed import Interval


PERIOD_ORDER = ["15m", "1H", "4H", "1D", "1W", "1M"]
PERIOD_NAMES = {
    "15m": "15 DAKIKA",
    "1H": "1 SAAT",
    "4H": "4 SAAT",
    "1D": "GUNLUK",
    "1W": "HAFTALIK",
    "1M": "AYLIK",
}

STRATEGY_META = {
    "macd_cross": {
        "state_key": "last_sent_macd_cross",
        "title": "S1 - MACD Pozitif Kesisim",
    },
    "h8": {
        "state_key": "last_sent_h8",
        "title": "H8 - SMI/MACD Pozitif",
    },
    "i9": {
        "state_key": "last_sent_i9",
        "title": "I9 - SMI/MACD Pozitif Full",
    },
    "ema": {
        "state_key": "last_sent_ema",
        "title": "S2 - EMA Dizilimi",
    },
    "rsi_macd": {
        "state_key": "last_sent_rsi_macd",
        "title": "S3 - RSI + MACD + Hacim",
    },
    "new_scan": {
        "state_key": "last_sent_new_scan",
        "title": "S4 - SMA + MACD + Hacim",
    },
    "full": {
        "state_key": "last_sent_smi_macd",
        "title": "S5 - SMI/MACD Full",
        "is_full": True,
    },
    "smi": {
        "state_key": "last_sent_smi_macd",
        "title": "S6 - SMI/MACD",
        "is_full": False,
    },
    "rsi": {
        "state_key": "last_sent_rsi",
        "title": "S7 - RSI",
    },
}

DIVIDER = "<b>==============================</b>"


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


async def build_rows(state: dict) -> tuple[dict[str, list[dict]], list[dict]]:
    meta = STRATEGY_META[SIGNAL_BUCKET]
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


async def generate_weekly_report() -> list[str]:
    if SIGNAL_BUCKET not in STRATEGY_META:
        return [f"<b>{html.escape(TARAMA_LABEL)} icin haftalik rapor metasi bulunamadi.</b>"]

    state_file = "state.json"
    if not os.path.exists(state_file):
        return ["<b>state.json bulunamadi.</b>"]

    with open(state_file, "r", encoding="utf-8") as file:
        state = json.load(file)

    grouped, unknown_period = await build_rows(state)
    meta = STRATEGY_META[SIGNAL_BUCKET]
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
            f"<b>{html.escape(TARAMA_LABEL)} - {title}</b>\n\n"
            f"{signal_lines(rows)}\n\n"
            f"{stats_block(title, rows)}"
        )

    if unknown_period:
        unknown_period.sort(key=lambda row: (row["change"] is None, -(row["change"] or 0)))
        all_rows.extend(unknown_period)
        messages.append(
            f"<b>{html.escape(TARAMA_LABEL)} - DIGER</b>\n\n"
            f"{signal_lines(unknown_period)}\n\n"
            f"{stats_block('DIGER', unknown_period)}"
        )

    if not all_rows:
        return [f"<b>{html.escape(TARAMA_LABEL)} icin bu hafta sinyal uretilmedi.</b>"]

    distribution = "\n".join(
        f"- {PERIOD_NAMES[period]}: {len(grouped[period])}"
        for period in PERIOD_ORDER
        if grouped[period]
    )
    messages.append(
        f"{DIVIDER}\n"
        f"<b>{html.escape(TARAMA_LABEL)} GENEL TOPLAM</b>\n\n"
        f"{stats_block('GENEL', all_rows)}\n"
        f"<b>Zaman dilimi dagilimi:</b>\n{distribution}\n"
        f"{DIVIDER}"
    )
    return messages


def send_chunked(sender, text: str):
    limit = 3500
    if len(text) <= limit:
        sender.send_message(text)
        return

    buffer = ""
    for line in text.split("\n"):
        if len(buffer) + len(line) + 1 > limit:
            sender.send_message(buffer)
            time.sleep(0.5)
            buffer = ""
        buffer += line + "\n"
    if buffer.strip():
        sender.send_message(buffer)


if __name__ == "__main__":
    async def main():
        messages = await generate_weekly_report()
        sender = get_telegram_sender()
        for index, message in enumerate(messages):
            send_chunked(sender, message)
            if index < len(messages) - 1:
                time.sleep(1.2)

    asyncio.run(main())
