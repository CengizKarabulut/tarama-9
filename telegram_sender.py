"""
Minimal Telegram sender for one scanner repository.
"""

import html
import logging
import os
import re
import time
from typing import Optional

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_THREAD_ID

logger = logging.getLogger(__name__)


class TelegramSender:
    def __init__(self, bot_token: str, chat_id: str, thread_id: Optional[str] = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.thread_id = thread_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def _payload(self, extra: dict) -> dict:
        payload = {
            "chat_id": self.chat_id,
            **extra,
        }
        if self.thread_id:
            payload["message_thread_id"] = self.thread_id
        return {key: value for key, value in payload.items() if value is not None}

    def send_message(self, text: str, parse_mode: str = "HTML", retry_count: int = 3) -> bool:
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram configuration is missing. Message skipped.")
            return False

        payload = self._payload({
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        })

        for attempt in range(retry_count):
            try:
                response = requests.post(
                    f"{self.base_url}/sendMessage",
                    json=payload,
                    timeout=15,
                )
                if response.status_code == 200:
                    return True

                if response.status_code == 429:
                    retry_after = response.json().get("parameters", {}).get("retry_after", 30)
                    logger.warning("Telegram rate limit hit. Waiting %s seconds.", retry_after)
                    time.sleep(retry_after + 1)
                    continue

                if "can't parse entities" in response.text and payload.get("parse_mode") == "HTML":
                    payload["text"] = re.sub("<[^<]+?>", "", text)
                    payload.pop("parse_mode", None)
                    continue

                logger.error("Telegram API error (%s): %s", response.status_code, response.text)
                response.raise_for_status()
            except requests.exceptions.RequestException as exc:
                logger.error("Telegram send error on attempt %s: %s", attempt + 1, exc)
                if attempt < retry_count - 1:
                    time.sleep(2)
        return False

    def send_photo(self, photo_path: str, caption: str = "", parse_mode: str = "HTML", retry_count: int = 3) -> bool:
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram configuration is missing. Photo skipped.")
            return False
        if not photo_path or not os.path.exists(photo_path):
            logger.error("Telegram photo path does not exist: %s", photo_path)
            return False

        payload = self._payload({
            "caption": caption,
            "parse_mode": parse_mode if caption else None,
        })

        for attempt in range(retry_count):
            try:
                with open(photo_path, "rb") as photo_file:
                    response = requests.post(
                        f"{self.base_url}/sendPhoto",
                        data=payload,
                        files={"photo": photo_file},
                        timeout=30,
                    )
                if response.status_code == 200:
                    return True

                if response.status_code == 429:
                    retry_after = response.json().get("parameters", {}).get("retry_after", 30)
                    logger.warning("Telegram rate limit hit. Waiting %s seconds.", retry_after)
                    time.sleep(retry_after + 1)
                    continue

                if "can't parse entities" in response.text and payload.get("parse_mode") == "HTML":
                    payload["caption"] = re.sub("<[^<]+?>", "", caption)
                    payload.pop("parse_mode", None)
                    continue

                logger.error("Telegram photo API error (%s): %s", response.status_code, response.text)
                response.raise_for_status()
            except requests.exceptions.RequestException as exc:
                logger.error("Telegram photo send error on attempt %s: %s", attempt + 1, exc)
                if attempt < retry_count - 1:
                    time.sleep(2)
        return False

    def send_error(self, error_msg: str) -> bool:
        return self.send_message(f"<b>HATA</b>\n\n{html.escape(error_msg)}")


_sender_instance: Optional[TelegramSender] = None


def get_telegram_sender() -> TelegramSender:
    global _sender_instance
    if _sender_instance is None:
        _sender_instance = TelegramSender(
            TELEGRAM_BOT_TOKEN,
            TELEGRAM_CHAT_ID,
            TELEGRAM_THREAD_ID,
        )
    return _sender_instance