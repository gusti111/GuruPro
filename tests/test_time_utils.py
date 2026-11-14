import unittest
from datetime import datetime, timezone, timedelta

from backend.time_utils import parse_utc_datetime


class ParseUtcDateTimeTests(unittest.TestCase):
    def test_parses_zulu_iso_string(self):
        self.assertEqual(
            parse_utc_datetime("2026-11-01T12:30:00Z"),
            datetime(2026, 11, 1, 12, 30, tzinfo=timezone.utc),
        )

    def test_normalizes_offset_to_utc(self):
        self.assertEqual(
            parse_utc_datetime("2026-11-01T19:30:00+07:00"),
            datetime(2026, 11, 1, 12, 30, tzinfo=timezone.utc),
        )

    def test_assumes_utc_for_naive_datetime(self):
        self.assertEqual(
            parse_utc_datetime(datetime(2026, 11, 1, 12, 30)),
            datetime(2026, 11, 1, 12, 30, tzinfo=timezone.utc),
        )

    def test_accepts_aware_datetime(self):
        source = datetime(2026, 11, 1, 19, 30, tzinfo=timezone(timedelta(hours=7)))
        self.assertEqual(
            parse_utc_datetime(source),
            datetime(2026, 11, 1, 12, 30, tzinfo=timezone.utc),
        )

    def test_supports_firestore_like_timestamp(self):
        class TimestampLike:
            def to_datetime(self):
                return datetime(2026, 11, 1, 12, 30)
        self.assertEqual(
            parse_utc_datetime(TimestampLike()),
            datetime(2026, 11, 1, 12, 30, tzinfo=timezone.utc),
        )

    def test_rejects_invalid_values(self):
        self.assertIsNone(parse_utc_datetime("not-a-timestamp"))
        self.assertIsNone(parse_utc_datetime(None))
        self.assertIsNone(parse_utc_datetime(123))


if __name__ == "__main__":
    unittest.main()
