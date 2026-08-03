#!/usr/bin/env python3
"""CGV 용산아이파크몰 IMAX 예매 오픈 감시기 (외부 패키지 불필요)."""
from __future__ import annotations

import argparse
import base64
import html
import json
import logging
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"
STATE_PATH = APP_DIR / "state.json"
LOG_PATH = APP_DIR / "watcher.log"
DEFAULT_CONFIG = {
    "theater_name": "CGV 용산아이파크몰",
    "theater_code": "0013",
    "start_date": "2026-08-18",
    "end_date": "2026-08-23",
    "active_start_hour": 6,
    "active_end_hour": 23,
    "endpoint": "https://m.cgv.co.kr/Schedule/cont/ajaxMovieSchedule.aspx",
    "booking_url": "https://www.cgv.co.kr/ticket/",
    "telegram_bot_token": "",
    "telegram_chat_id": "",
}


@dataclass(frozen=True)
class Showtime:
    date: str
    movie: str
    screen: str
    start_time: str

    @property
    def key(self) -> str:
        return "|".join((self.date, self.movie, self.screen, self.start_time))


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(
            json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return {**DEFAULT_CONFIG, **json.loads(CONFIG_PATH.read_text(encoding="utf-8"))}


def load_seen() -> set[str]:
    try:
        return set(json.loads(STATE_PATH.read_text(encoding="utf-8")).get("seen", []))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return set()


def save_seen(seen: Iterable[str]) -> None:
    temp = STATE_PATH.with_suffix(".tmp")
    temp.write_text(
        json.dumps({"seen": sorted(set(seen))}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temp, STATE_PATH)


def fetch_schedule(endpoint: str, theater_code: str, date: str) -> str:
    form = urllib.parse.urlencode(
        {"theaterCd": theater_code, "playYMD": date.replace("-", "")}
    ).encode("ascii")
    request = urllib.request.Request(
        endpoint,
        data=form,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/127 Safari/537.36"
            ),
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Referer": "https://m.cgv.co.kr/",
            "X-Requested-With": "XMLHttpRequest",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        try:
            return raw.decode(charset)
        except (LookupError, UnicodeDecodeError):
            return raw.decode("utf-8", errors="replace")


def split_js_args(raw: str) -> list[str]:
    return [
        html.unescape(a or b).strip()
        for a, b in re.findall(r"'((?:\\.|[^'])*)'|\"((?:\\.|[^\"])*)\"", raw)
    ]


def parse_imax_showtimes(page: str, date: str) -> list[Showtime]:
    results: list[Showtime] = []
    for match in re.finditer(r"popupSchedule\s*\((.*?)\)", page, re.I | re.S):
        args = split_js_args(match.group(1))
        if len(args) < 3:
            continue
        movie, screen, start_time = args[0], args[1], args[2]
        if "IMAX" not in screen.upper():
            continue
        if not re.fullmatch(r"\d{1,2}:\d{2}", start_time):
            continue
        results.append(Showtime(date, movie, screen, start_time))

    if not results:
        pattern = re.compile(
            r"<a\b[^>]*data-screenkorname=[\"']([^\"']*IMAX[^\"']*)[\"'][^>]*>",
            re.I,
        )
        for match in pattern.finditer(page):
            tag = match.group(0)
            movie_match = re.search(r"data-moviename=[\"']([^\"']+)", tag, re.I)
            time_match = re.search(r"data-playstarttime=[\"'](\d{2})(\d{2})", tag, re.I)
            if movie_match and time_match:
                results.append(
                    Showtime(
                        date,
                        html.unescape(movie_match.group(1)).strip(),
                        html.unescape(match.group(1)).strip(),
                        f"{time_match.group(1)}:{time_match.group(2)}",
                    )
                )
    return sorted(set(results), key=lambda item: (item.date, item.start_time, item.movie))


def notify_windows(title: str, message: str) -> None:
    script = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime] > $null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml('<toast duration="long"><visual><binding template="ToastGeneric"><text>{html.escape(title, quote=True)}</text><text>{html.escape(message, quote=True)}</text></binding></visual><audio src="ms-winsoundevent:Notification.Looping.Alarm2"/></toast>')
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('CGV IMAX Watcher').Show($toast)
"""
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    powershell = (
        Path(system_root)
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    subprocess.run(
        [str(powershell), "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        timeout=15,
    )


def notify_telegram(token: str, chat_id: str, message: str) -> None:
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(request, timeout=15):
        pass


def date_range(start: str, end: str) -> list[str]:
    current = datetime.strptime(start, "%Y-%m-%d").date()
    last = datetime.strptime(end, "%Y-%m-%d").date()
    dates: list[str] = []
    while current <= last:
        dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates


def run(force: bool = False, dry_run: bool = False) -> int:
    config = load_config()
    now = datetime.now()
    end_date = datetime.strptime(config["end_date"], "%Y-%m-%d").date()
    if not force and not (
        int(config["active_start_hour"]) <= now.hour <= int(config["active_end_hour"])
    ):
        logging.info("활성 시간 밖이므로 검사하지 않습니다: %s", now.strftime("%H:%M"))
        return 0
    if not force and now.date() > end_date:
        logging.info("감시 종료일이 지났습니다: %s", end_date)
        return 0

    dates = date_range(config["start_date"], config["end_date"])
    seen = load_seen()
    found: list[Showtime] = []
    failures = 0
    for date in dates:
        try:
            page = fetch_schedule(config["endpoint"], config["theater_code"], date)
            shows = parse_imax_showtimes(page, date)
            found.extend(shows)
            logging.info("%s 확인: IMAX 회차 %d개", date, len(shows))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            failures += 1
            logging.error("%s 조회 실패: %s", date, exc)

    if failures == len(dates):
        return 2
    new_shows = [show for show in found if show.key not in seen]
    if not new_shows:
        logging.info("새로 열린 IMAX 예매 회차가 없습니다.")
        return 0

    lines = [
        f"{show.date[5:]} {show.start_time} · {show.movie} ({show.screen})"
        for show in new_shows
    ]
    message = "용산 IMAX 예매가 열렸습니다!\n" + "\n".join(lines[:12])
    if len(lines) > 12:
        message += f"\n외 {len(lines) - 12}개 회차"
    message += f"\n{config['booking_url']}"
    logging.info(message.replace("\n", " | "))
    if not dry_run:
        notified = False
        if os.name == "nt":
            try:
                notify_windows("CGV 용산 IMAX 예매 오픈", message)
                notified = True
            except Exception as exc:
                logging.error("Windows 알림 실패: %s", exc)

        telegram_token = os.environ.get(
            "TELEGRAM_BOT_TOKEN", config["telegram_bot_token"]
        ).strip()
        telegram_chat_id = os.environ.get(
            "TELEGRAM_CHAT_ID", config["telegram_chat_id"]
        ).strip()
        if telegram_token and telegram_chat_id:
            try:
                notify_telegram(telegram_token, telegram_chat_id, message)
                notified = True
            except Exception as exc:
                logging.error("텔레그램 알림 실패: %s", exc)

        if not notified:
            logging.error(
                "사용 가능한 알림 채널이 없거나 전송에 실패했습니다. "
                "상태를 저장하지 않아 다음 실행에서 다시 시도합니다."
            )
            return 3
        seen.update(show.key for show in new_shows)
        save_seen(seen)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="CGV 용산 IMAX 예매 오픈 감시기")
    parser.add_argument("--force", action="store_true", help="시간/종료일 검사를 무시")
    parser.add_argument("--dry-run", action="store_true", help="알림과 상태 저장 없이 조회")
    parser.add_argument(
        "--test-notification",
        action="store_true",
        help="CGV 조회 없이 알림 채널만 시험",
    )
    args = parser.parse_args()
    setup_logging()
    try:
        if args.test_notification:
            config = load_config()
            token = os.environ.get(
                "TELEGRAM_BOT_TOKEN", config["telegram_bot_token"]
            ).strip()
            chat_id = os.environ.get(
                "TELEGRAM_CHAT_ID", config["telegram_chat_id"]
            ).strip()
            if token and chat_id:
                notify_telegram(
                    token,
                    chat_id,
                    "CGV 용산 IMAX 알리미 테스트가 성공했습니다.",
                )
                logging.info("텔레그램 테스트 알림을 전송했습니다.")
                return 0
            if os.name == "nt":
                notify_windows(
                    "CGV 용산 IMAX 알리미",
                    "Windows 테스트 알림이 정상적으로 동작합니다.",
                )
                logging.info("Windows 테스트 알림을 전송했습니다.")
                return 0
            logging.error("TELEGRAM_BOT_TOKEN과 TELEGRAM_CHAT_ID가 필요합니다.")
            return 3
        return run(force=args.force, dry_run=args.dry_run)
    except Exception:
        logging.exception("예상하지 못한 오류")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
