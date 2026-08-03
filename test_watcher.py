import json
import unittest

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


if __name__ == "__main__":
    unittest.main()