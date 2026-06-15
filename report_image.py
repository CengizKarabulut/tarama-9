"""
PNG report image renderer for Telegram scan summaries.
"""

from pathlib import Path
import re
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


CANVAS_WIDTH = 1200
PADDING_X = 54
TOP_HEIGHT = 190
TABLE_HEADER_HEIGHT = 48
ROW_HEIGHT = 38
BOTTOM_PADDING = 46

COL_NO = 72
COL_SYMBOL = 150
COL_CHANGE_RIGHT = 760
COL_CLOSE_RIGHT = 1085

COLOR_BG = "#F4F7FB"
COLOR_CARD = "#FFFFFF"
COLOR_BRAND = "#0F2742"
COLOR_MUTED = "#667085"
COLOR_LINE = "#D8E0EA"
COLOR_HEADER = "#EAF1FF"
COLOR_ROW_ALT = "#F8FAFC"
COLOR_GREEN = "#137333"
COLOR_RED = "#B42318"
COLOR_TEXT = "#111827"
COLOR_BLUE = "#1D4ED8"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "Arial Bold.ttf" if bold else "Arial.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


FONT_BRAND = _font(42, True)
FONT_TITLE = _font(30, True)
FONT_META = _font(22)
FONT_META_BOLD = _font(22, True)
FONT_TABLE_HEAD = _font(22, True)
FONT_ROW = _font(22)
FONT_ROW_BOLD = _font(22, True)
FONT_EMPTY = _font(28, True)


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    return cleaned.strip("-").lower() or "report"


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _right_text(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, font: ImageFont.ImageFont, fill: str):
    draw.text((x - _text_width(draw, text, font), y), text, font=font, fill=fill)


def _format_price(value) -> str:
    try:
        return f"{float(value):,.2f}".replace(",", " ")
    except (TypeError, ValueError):
        return "-"


def _format_change(value) -> tuple[str, str]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-", COLOR_TEXT

    color = COLOR_GREEN if number >= 0 else COLOR_RED
    return f"{number:+.2f}%", color


def create_signal_report_image(
    brand_name: str,
    tarama_label: str,
    market_type: str,
    period: str,
    timestamp: str,
    total_scanned: int,
    total_signals: int,
    signals: Iterable[dict],
    start_index: int,
    page: int,
    total_pages: int,
    output_dir: Path | str,
) -> Path:
    rows = list(signals)
    table_rows = max(len(rows), 1)
    height = TOP_HEIGHT + TABLE_HEADER_HEIGHT + (table_rows * ROW_HEIGHT) + BOTTOM_PADDING

    image = Image.new("RGB", (CANVAS_WIDTH, height), COLOR_BG)
    draw = ImageDraw.Draw(image)

    card_x0 = 28
    card_y0 = 24
    card_x1 = CANVAS_WIDTH - 28
    card_y1 = height - 24
    draw.rounded_rectangle((card_x0, card_y0, card_x1, card_y1), radius=28, fill=COLOR_CARD)

    draw.text((PADDING_X, 46), brand_name, font=FONT_BRAND, fill=COLOR_BRAND)
    draw.text((PADDING_X, 102), tarama_label, font=FONT_TITLE, fill=COLOR_BLUE)

    badge = f"{market_type} | {period}"
    badge_w = _text_width(draw, badge, FONT_META_BOLD) + 42
    draw.rounded_rectangle(
        (CANVAS_WIDTH - PADDING_X - badge_w, 50, CANVAS_WIDTH - PADDING_X, 92),
        radius=20,
        fill=COLOR_HEADER,
    )
    draw.text((CANVAS_WIDTH - PADDING_X - badge_w + 21, 59), badge, font=FONT_META_BOLD, fill=COLOR_BLUE)

    meta = f"{timestamp}   |   Taranan: {total_scanned}   |   Sinyal: {total_signals}"
    draw.text((PADDING_X, 143), meta, font=FONT_META, fill=COLOR_MUTED)

    page_text = f"Liste {page}/{total_pages}"
    _right_text(draw, CANVAS_WIDTH - PADDING_X, 143, page_text, FONT_META_BOLD, COLOR_MUTED)

    header_y = TOP_HEIGHT
    draw.rounded_rectangle(
        (PADDING_X, header_y, CANVAS_WIDTH - PADDING_X, header_y + TABLE_HEADER_HEIGHT),
        radius=14,
        fill=COLOR_HEADER,
    )
    draw.text((COL_NO, header_y + 12), "No", font=FONT_TABLE_HEAD, fill=COLOR_BRAND)
    draw.text((COL_SYMBOL, header_y + 12), "Sembol", font=FONT_TABLE_HEAD, fill=COLOR_BRAND)
    _right_text(draw, COL_CHANGE_RIGHT, header_y + 12, "Degisim", FONT_TABLE_HEAD, COLOR_BRAND)
    _right_text(draw, COL_CLOSE_RIGHT, header_y + 12, "Kapanis", FONT_TABLE_HEAD, COLOR_BRAND)

    row_y = header_y + TABLE_HEADER_HEIGHT
    if not rows:
        draw.rectangle((PADDING_X, row_y, CANVAS_WIDTH - PADDING_X, row_y + ROW_HEIGHT), fill=COLOR_ROW_ALT)
        empty_text = "Bu zaman diliminde sinyal yok"
        empty_w = _text_width(draw, empty_text, FONT_EMPTY)
        draw.text(((CANVAS_WIDTH - empty_w) / 2, row_y + 4), empty_text, font=FONT_EMPTY, fill=COLOR_MUTED)
    else:
        for offset, signal in enumerate(rows, start=start_index):
            if (offset - start_index) % 2 == 1:
                draw.rectangle((PADDING_X, row_y, CANVAS_WIDTH - PADDING_X, row_y + ROW_HEIGHT), fill=COLOR_ROW_ALT)

            symbol = str(signal.get("symbol", ""))[:12]
            close = _format_price(signal.get("close", 0))
            change, change_color = _format_change(signal.get("change", 0))

            draw.text((COL_NO, row_y + 8), f"{offset:>2}", font=FONT_ROW, fill=COLOR_MUTED)
            draw.text((COL_SYMBOL, row_y + 8), symbol, font=FONT_ROW_BOLD, fill=COLOR_TEXT)
            _right_text(draw, COL_CHANGE_RIGHT, row_y + 8, change, FONT_ROW_BOLD, change_color)
            _right_text(draw, COL_CLOSE_RIGHT, row_y + 8, close, FONT_ROW, COLOR_TEXT)

            draw.line((PADDING_X, row_y + ROW_HEIGHT, CANVAS_WIDTH - PADDING_X, row_y + ROW_HEIGHT), fill=COLOR_LINE)
            row_y += ROW_HEIGHT

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    filename = "_".join(
        [
            _safe_filename(tarama_label),
            _safe_filename(market_type),
            _safe_filename(period),
            f"p{page}",
        ]
    ) + ".png"
    final_path = output_path / filename
    image.save(final_path, "PNG", optimize=True)
    return final_path


def create_common_period_report_image(
    brand_name: str,
    tarama_label: str,
    timestamp: str,
    rows: Iterable[dict],
    page: int,
    total_pages: int,
    total_symbols: int,
    output_dir: Path | str,
) -> Path:
    table_rows = list(rows)
    visible_rows = max(len(table_rows), 1)
    row_height = 44
    height = TOP_HEIGHT + TABLE_HEADER_HEIGHT + (visible_rows * row_height) + BOTTOM_PADDING

    image = Image.new("RGB", (CANVAS_WIDTH, height), COLOR_BG)
    draw = ImageDraw.Draw(image)

    card_x0 = 28
    card_y0 = 24
    card_x1 = CANVAS_WIDTH - 28
    card_y1 = height - 24
    draw.rounded_rectangle((card_x0, card_y0, card_x1, card_y1), radius=28, fill=COLOR_CARD)

    draw.text((PADDING_X, 46), brand_name, font=FONT_BRAND, fill=COLOR_BRAND)
    draw.text((PADDING_X, 102), f"{tarama_label} - Coklu Periyot Ozeti", font=FONT_TITLE, fill=COLOR_BLUE)

    badge = f"{total_symbols} hisse"
    badge_w = _text_width(draw, badge, FONT_META_BOLD) + 42
    draw.rounded_rectangle(
        (CANVAS_WIDTH - PADDING_X - badge_w, 50, CANVAS_WIDTH - PADDING_X, 92),
        radius=20,
        fill=COLOR_HEADER,
    )
    draw.text((CANVAS_WIDTH - PADDING_X - badge_w + 21, 59), badge, font=FONT_META_BOLD, fill=COLOR_BLUE)

    draw.text((PADDING_X, 143), timestamp, font=FONT_META, fill=COLOR_MUTED)
    _right_text(draw, CANVAS_WIDTH - PADDING_X, 143, f"Liste {page}/{total_pages}", FONT_META_BOLD, COLOR_MUTED)

    header_y = TOP_HEIGHT
    draw.rounded_rectangle(
        (PADDING_X, header_y, CANVAS_WIDTH - PADDING_X, header_y + TABLE_HEADER_HEIGHT),
        radius=14,
        fill=COLOR_HEADER,
    )
    draw.text((COL_SYMBOL, header_y + 12), "Sembol", font=FONT_TABLE_HEAD, fill=COLOR_BRAND)
    draw.text((320, header_y + 12), "Periyotlar", font=FONT_TABLE_HEAD, fill=COLOR_BRAND)

    row_y = header_y + TABLE_HEADER_HEIGHT
    if not table_rows:
        draw.rectangle((PADDING_X, row_y, CANVAS_WIDTH - PADDING_X, row_y + row_height), fill=COLOR_ROW_ALT)
        empty_text = "Birden fazla periyotta sinyal yok"
        empty_w = _text_width(draw, empty_text, FONT_EMPTY)
        draw.text(((CANVAS_WIDTH - empty_w) / 2, row_y + 6), empty_text, font=FONT_EMPTY, fill=COLOR_MUTED)
    else:
        for index, row in enumerate(table_rows):
            if index % 2 == 1:
                draw.rectangle((PADDING_X, row_y, CANVAS_WIDTH - PADDING_X, row_y + row_height), fill=COLOR_ROW_ALT)

            symbol = str(row.get("symbol", ""))[:12]
            periods = ", ".join(dict.fromkeys(row.get("periods", [])))
            draw.text((COL_SYMBOL, row_y + 10), symbol, font=FONT_ROW_BOLD, fill=COLOR_TEXT)
            draw.text((320, row_y + 10), periods, font=FONT_ROW, fill=COLOR_TEXT)
            draw.line((PADDING_X, row_y + row_height, CANVAS_WIDTH - PADDING_X, row_y + row_height), fill=COLOR_LINE)
            row_y += row_height

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    filename = "_".join(
        [
            _safe_filename(tarama_label),
            "coklu-periyot-ozeti",
            f"p{page}",
        ]
    ) + ".png"
    final_path = output_path / filename
    image.save(final_path, "PNG", optimize=True)
    return final_path


def create_weekly_performance_report_image(
    brand_name: str,
    tarama_label: str,
    report_title: str,
    timestamp: str,
    rows: Iterable[dict],
    page: int,
    total_pages: int,
    total_rows: int,
    output_dir: Path | str,
) -> Path:
    table_rows = list(rows)
    visible_rows = max(len(table_rows), 1)
    row_height = 42
    height = TOP_HEIGHT + TABLE_HEADER_HEIGHT + (visible_rows * row_height) + BOTTOM_PADDING

    image = Image.new("RGB", (CANVAS_WIDTH, height), COLOR_BG)
    draw = ImageDraw.Draw(image)

    card_x0 = 28
    card_y0 = 24
    card_x1 = CANVAS_WIDTH - 28
    card_y1 = height - 24
    draw.rounded_rectangle((card_x0, card_y0, card_x1, card_y1), radius=28, fill=COLOR_CARD)

    draw.text((PADDING_X, 46), brand_name, font=FONT_BRAND, fill=COLOR_BRAND)
    draw.text((PADDING_X, 102), f"{tarama_label} - Haftalik Rapor", font=FONT_TITLE, fill=COLOR_BLUE)

    badge = f"{total_rows} sinyal"
    badge_w = _text_width(draw, badge, FONT_META_BOLD) + 42
    draw.rounded_rectangle(
        (CANVAS_WIDTH - PADDING_X - badge_w, 50, CANVAS_WIDTH - PADDING_X, 92),
        radius=20,
        fill=COLOR_HEADER,
    )
    draw.text((CANVAS_WIDTH - PADDING_X - badge_w + 21, 59), badge, font=FONT_META_BOLD, fill=COLOR_BLUE)

    meta = f"{report_title}   |   {timestamp}"
    draw.text((PADDING_X, 143), meta[:74], font=FONT_META, fill=COLOR_MUTED)
    _right_text(draw, CANVAS_WIDTH - PADDING_X, 143, f"Liste {page}/{total_pages}", FONT_META_BOLD, COLOR_MUTED)

    header_y = TOP_HEIGHT
    draw.rounded_rectangle(
        (PADDING_X, header_y, CANVAS_WIDTH - PADDING_X, header_y + TABLE_HEADER_HEIGHT),
        radius=14,
        fill=COLOR_HEADER,
    )
    draw.text((COL_SYMBOL, header_y + 12), "Sembol", font=FONT_TABLE_HEAD, fill=COLOR_BRAND)
    draw.text((300, header_y + 12), "Periyot", font=FONT_TABLE_HEAD, fill=COLOR_BRAND)
    draw.text((430, header_y + 12), "Tarih", font=FONT_TABLE_HEAD, fill=COLOR_BRAND)
    _right_text(draw, 735, header_y + 12, "Giris", FONT_TABLE_HEAD, COLOR_BRAND)
    _right_text(draw, 910, header_y + 12, "Son", FONT_TABLE_HEAD, COLOR_BRAND)
    _right_text(draw, COL_CLOSE_RIGHT, header_y + 12, "Getiri", FONT_TABLE_HEAD, COLOR_BRAND)

    row_y = header_y + TABLE_HEADER_HEIGHT
    if not table_rows:
        draw.rectangle((PADDING_X, row_y, CANVAS_WIDTH - PADDING_X, row_y + row_height), fill=COLOR_ROW_ALT)
        empty_text = "Bu hafta sinyal yok"
        empty_w = _text_width(draw, empty_text, FONT_EMPTY)
        draw.text(((CANVAS_WIDTH - empty_w) / 2, row_y + 6), empty_text, font=FONT_EMPTY, fill=COLOR_MUTED)
    else:
        for index, row in enumerate(table_rows):
            if index % 2 == 1:
                draw.rectangle((PADDING_X, row_y, CANVAS_WIDTH - PADDING_X, row_y + row_height), fill=COLOR_ROW_ALT)

            symbol = str(row.get("symbol", ""))[:12]
            period = str(row.get("period", ""))[:6]
            signal_time = str(row.get("time", ""))[:16]
            signal_price = _format_price(row.get("signal_price"))
            current_price = _format_price(row.get("current_price"))
            change, change_color = _format_change(row.get("change"))

            draw.text((COL_SYMBOL, row_y + 10), symbol, font=FONT_ROW_BOLD, fill=COLOR_TEXT)
            draw.text((300, row_y + 10), period, font=FONT_ROW, fill=COLOR_TEXT)
            draw.text((430, row_y + 10), signal_time, font=FONT_ROW, fill=COLOR_TEXT)
            _right_text(draw, 735, row_y + 10, signal_price, FONT_ROW, COLOR_TEXT)
            _right_text(draw, 910, row_y + 10, current_price, FONT_ROW, COLOR_TEXT)
            _right_text(draw, COL_CLOSE_RIGHT, row_y + 10, change, FONT_ROW_BOLD, change_color)

            draw.line((PADDING_X, row_y + row_height, CANVAS_WIDTH - PADDING_X, row_y + row_height), fill=COLOR_LINE)
            row_y += row_height

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    filename = "_".join(
        [
            _safe_filename(tarama_label),
            "haftalik-rapor",
            f"p{page}",
        ]
    ) + ".png"
    final_path = output_path / filename
    image.save(final_path, "PNG", optimize=True)
    return final_path
