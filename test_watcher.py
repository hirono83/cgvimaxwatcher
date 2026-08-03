import unittest
from cgv_imax_watcher import parse_imax_showtimes


class ParseTests(unittest.TestCase):
    def test_popup_schedule_imax_only(self):
        page = """
        <a href="javascript:popupSchedule('영화 A','IMAX관','10:30','120')">10:30</a>
        <a href="javascript:popupSchedule('영화 B','4관','12:00','120')">12:00</a>
        """
        shows = parse_imax_showtimes(page, "2026-08-18")
        self.assertEqual(1, len(shows))
        self.assertEqual("영화 A", shows[0].movie)
        self.assertEqual("10:30", shows[0].start_time)

    def test_duplicate_is_removed(self):
        link = "<a href=\"javascript:popupSchedule('영화 A','IMAX관','10:30')\">10:30</a>"
        shows = parse_imax_showtimes(link + link, "2026-08-18")
        self.assertEqual(1, len(shows))


if __name__ == "__main__":
    unittest.main()
