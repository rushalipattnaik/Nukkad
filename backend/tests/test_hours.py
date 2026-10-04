from __future__ import annotations

from app.analysis.hours import (
    hours_coverage_stats,
    is_open_during_need_window,
    parse_hour_string,
)


def test_parse_simple_range():
    assert parse_hour_string("9 AM-9 PM") == [(9.0, 21.0)]


def test_parse_overnight_range_wraps_past_midnight():
    assert parse_hour_string("10 PM-5 AM") == [(22.0, 29.0)]


def test_parse_24_hours():
    assert parse_hour_string("Open 24 hours") == [(0.0, 24.0)]


def test_parse_closed():
    assert parse_hour_string("Closed") == []


def test_parse_multiple_ranges_same_day():
    assert parse_hour_string("9 AM-1 PM, 4 PM-8 PM") == [(9.0, 13.0), (16.0, 20.0)]


def test_parse_garbage_is_empty_not_crash():
    assert parse_hour_string("¯\\_(ツ)_/¯") == []


def test_open_during_late_night_window_true():
    hours = {"monday": "10 AM-11 PM"}
    # need window 21-6 (after 9 PM); 10am-11pm covers 21:00-23:00
    assert is_open_during_need_window(hours, (21, 6), ("monday",)) is True


def test_open_during_late_night_window_false():
    hours = {"monday": "9 AM-8 PM"}
    assert is_open_during_need_window(hours, (21, 6), ("monday",)) is False


def test_open_during_returns_none_when_no_data_for_relevant_days():
    hours = {"monday": "9 AM-8 PM"}
    # need window only applies on weekends, which we have no data for
    assert is_open_during_need_window(hours, (9, 18), ("saturday", "sunday")) is None


def test_hours_coverage_stats_basic():
    places = [
        {"operating_hours": {"monday": "9 AM-10 PM"}},
        {"operating_hours": {"monday": "10 AM-8 PM"}},
        {"operating_hours": {}},  # no hours data at all
    ]
    stats = hours_coverage_stats(places, need_hours=(21, 6), need_days=("monday",))
    assert stats["total"] == 3
    assert stats["with_hours"] == 2
    assert stats["hours_coverage_pct"] == round(100 * 2 / 3, 1)
    # place 1 (9am-10pm) overlaps the 21:00-06:00 window; place 2 (10am-8pm) does not
    assert stats["judgeable"] == 2
    assert stats["open_in_window"] == 1
    assert stats["open_in_window_share"] == 0.5
