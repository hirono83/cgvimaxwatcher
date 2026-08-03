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
    "endpoint": "https://cgv.co.kr/api/v1/booking/searchMovScnInfo",
    "booking_url": "https://cgv.co.kr/cnm/movieBook/cinema",
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
    query = urllib.parse.urlencode(
        {
            "coCd": "A420",
            "siteNo": theater_code,
            "scnYmd": date.replace("-", ""),
            "scnsNo": "",
            "scnSseq": "",
            "rtctlScopCd": "08",
            "custNo": "",
        }
    )
    url = endpoint + ("&" if "?" in endpoint else "?") + query
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/127 Safari/537.36"
            ),
            "Accept": "application/json",
            "Accept-Language": "ko-KR",
            "Referer": "https://cgv.co.kr/cnm/movieBook/cinema",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        try:
            body = raw.decode(charset)
        except (LookupError, UnicodeDecodeError):
            body = raw.decode("utf-8", errors="replace")
    if body.lstrip().startswith(("<!DOCTYPE", "<html")):
        raise ValueError("CGV가 시간표 JSON 대신 HTML 페이지를 반환했습니다.")
    return body

def split_js_args(raw: str) -> list[str]:
    return [
        html.unescape(a or b).strip()
        for a, b in re.findall(r"'((?:\\.|[^'])*)'|\"((?:\\.|[^\"])*)\"", raw)
    ]


def parse_imax_showtimes(page: str, date: str) -> list[Showtime]:
    try:
        payload = json.loads(page)
    except json.JSONDecodeError as exc:
        raise ValueError("CGV 시간표 응답이 올바른 JSON이 아닙니다.") from exc

    if not isinstance(payload, dict) or payload.get("statusCode") not in (0, "0"):
        raise ValueError(
            f"CGV 시간표 API 오류: {payload.get('statusCode')} "
            f"{payload.get('statusMessage', '')}"
        )

    rows = payload.get("data")
    if rows is None:
        rows = []
    if not isinstance(rows, list):
        raise ValueError("CGV 시간표 data가 목록 형식이 아닙니다.")

    results: list[Showtime] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        screen = str(
            item.get("expoScnsNm")
            or item.get("scnsNm")
            or item.get("scnsEnm")
            or ""
        ).strip()
        screen_markers = " ".join(
            str(item.get(key) or "")
            for key in (
                "expoScnsNm",
                "scnsNm",
                "scnsEnm",
                "tcscnsGradNm",
                "movkndDsplEnm",
            )
        ).upper()
        if "IMAX" not in screen_markers and "아이맥스" not in screen_markers:
            continue
        # cntlYn=Y is shown by CGV as booking preparation, not an open session.
        if str(item.get("cntlYn") or "").upper() == "Y":
            continue

        raw_time = str(item.get("scnsrtTm") or "").strip()
        if not re.fullmatch(r"\d{4}", raw_time):
            continue
        start_time = f"{raw_time[:2]}:{raw_time[2:]}"
        movie = str(
            item.get("expoProdNm") or item.get("movNm") or item.get("prodNm") or ""
        ).strip()
        if not movie:
            continue
        results.append(Showtime(date, movie, screen or "IMAX관", start_time))

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


def send_notification(config: dict, title: str, message: str) -> bool:
    notified = False
    if os.name == "nt":
        try:
            notify_windows(title, message)
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
    return notified


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
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            failures += 1
            logging.error("%s 조회 실패: %s", date, exc)

    if failures == len(dates):
        return 2
    new_shows = [show for show in found if show.key not in seen]
    if not new_shows:
        newline = chr(10)
        if failures:
            title = "CGV 용산 IMAX 조회 오류"
            message = newline.join(
                [
                    f"일부 날짜 조회 실패: {failures}/{len(dates)}개 날짜",
                    "새 회차 여부를 완전히 확인하지 못했습니다.",
                ]
            )
            logging.error(message.replace(newline, " | "))
            result_code = 2
        else:
            title = "CGV 용산 IMAX 알리미"
            message = newline.join(
                [
                    "변동사항 없음",
                    f"확인 시각: {now.strftime('%Y-%m-%d %H:%M')}",
                    f"현재 열린 대상 IMAX 회차: {len(found)}개",
                ]
            )
            logging.info(message.replace(newline, " | "))
            result_code = 0

        if not dry_run and not send_notification(config, title, message):
            logging.error("사용 가능한 알림 채널이 없거나 전송에 실패했습니다.")
            return 3
        return result_code

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
        if not send_notification(config, "CGV 용산 IMAX 예매 오픈", message):
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
