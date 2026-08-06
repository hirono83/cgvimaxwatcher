import json
import unittest
from datetime import datetime
from unittest.mock import patch

import cgv_imax_watcher as watcher
from cgv_imax_watcher import parse_imax_showtimes


class ParseTests(unittest.TestCase):
    def test_open_imax_only(self):
        payload = {
            "statusCode": 0,
            "data": [
                {
                    "expoProdNm": "영화 A(IMAX LASER 2D)",
                    "expoScnsNm": "IMAX관",
                    "tcscnsGradNm": "아이맥스",
                    "scnsrtTm": "1030",
                    "cntlYn": "N",
                },
                {
                    "expoProdNm": "영화 B",
                    "expoScnsNm": "4관",
                    "scnsrtTm": "1200",
                    "cntlYn": "N",
                },
                {
                    "expoProdNm": "영화 C(IMAX)",
                    "expoScnsNm": "IMAX관",
                    "scnsrtTm": "1400",
                    "cntlYn": "Y",
                },
            ],
        }
        shows = parse_imax_showtimes(json.dumps(payload), "2026-08-18")
        self.assertEqual(1, len(shows))
        self.assertEqual("영화 A(IMAX LASER 2D)", shows[0].movie)
        self.assertEqual("10:30", shows[0].start_time)

    def test_duplicate_is_removed(self):
        row = {
            "expoProdNm": "영화 A",
            "expoScnsNm": "IMAX관",
            "scnsrtTm": "2400",
            "cntlYn": "N",
        }
        payload = {"statusCode": 0, "data": [row, row]}
        shows = parse_imax_showtimes(json.dumps(payload), "2026-08-18")
        self.assertEqual(1, len(shows))
        self.assertEqual("24:00", shows[0].start_time)

    def test_html_response_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_imax_showtimes("<!DOCTYPE html>", "2026-08-18")


class HourlyRetryTests(unittest.TestCase):
    def make_config(self):
        today = datetime.now().date().isoformat()
        return {
            **watcher.DEFAULT_CONFIG,
            "start_date": today,
            "end_date": today,
            "active_start_hour": 0,
            "active_end_hour": 23,
        }

    def test_successful_hour_skips_fallback(self):
        hour_key = datetime.now().strftime("%Y-%m-%dT%H")
        with (
            patch.object(watcher, "load_config", return_value=self.make_config()),
            patch.object(
                watcher,
                "load_state",
                return_value={"seen": set(), "last_success_hour": hour_key},
            ),
            patch.object(watcher, "fetch_schedule") as fetch_schedule,
        ):
            self.assertEqual(0, watcher.run())
        fetch_schedule.assert_not_called()

    def test_successful_check_marks_current_hour(self):
        hour_key = datetime.now().strftime("%Y-%m-%dT%H")
        empty_schedule = json.dumps({"statusCode": 0, "data": []})
        with (
            patch.object(watcher, "load_config", return_value=self.make_config()),
            patch.object(
                watcher,
                "load_state",
                return_value={"seen": set(), "last_success_hour": ""},
            ),
            patch.object(watcher, "fetch_schedule", return_value=empty_schedule),
            patch.object(watcher, "send_notification", return_value=True),
            patch.object(watcher, "save_state") as save_state,
        ):
            self.assertEqual(0, watcher.run())
        save_state.assert_called_once_with(set(), hour_key)

if __name__ == "__main__":
    unittest.main()