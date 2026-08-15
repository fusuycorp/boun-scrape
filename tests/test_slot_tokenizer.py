"""Unit tests for schedule slot tokenization."""

import pytest
from boun_scrape.domain.models import CourseSlot
from boun_scrape.scraper.slot_tokenizer import (
    build_slots,
    parse_days,
    parse_hours,
    parse_rooms,
)


class TestParseDays:
    """Tests for 2-character lookahead day tokenization."""

    def test_single_letter_days(self) -> None:
        assert parse_days("M") == ["M"]
        assert parse_days("T") == ["T"]
        assert parse_days("W") == ["W"]
        assert parse_days("F") == ["F"]
        assert parse_days("MWF") == ["M", "W", "F"]

    def test_two_letter_lookahead_days(self) -> None:
        assert parse_days("Th") == ["Th"]
        assert parse_days("St") == ["St"]
        assert parse_days("Su") == ["Su"]
        assert parse_days("MTh") == ["M", "Th"]
        assert parse_days("TTh") == ["T", "Th"]
        assert parse_days("MWThF") == ["M", "W", "Th", "F"]
        assert parse_days("StSu") == ["St", "Su"]
        assert parse_days("ThFSt") == ["Th", "F", "St"]

    def test_tba_and_whitespace(self) -> None:
        assert parse_days("TBA") == ["TBA"]
        assert parse_days("  TBA  ") == ["TBA"]
        assert parse_days(" M W F ") == ["M", "W", "F"]
        assert parse_days(" T Th ") == ["T", "Th"]

    def test_empty_and_none(self) -> None:
        assert parse_days("") == []
        assert parse_days("   ") == []
        assert parse_days(None) == []


class TestParseHours:
    """Tests for algebraic hour partition."""

    def test_single_digit_hours(self) -> None:
        assert parse_hours("123", 3) == ["1", "2", "3"]
        assert parse_hours("12", 2) == ["1", "2"]
        assert parse_hours("5", 1) == ["5"]

    def test_two_digit_algebraic_partition(self) -> None:
        # 1 two-digit hour (10) and 2 single-digit hours (8, 9)
        assert parse_hours("8910", 3) == ["8", "9", "10"]
        # 2 two-digit hours (10, 11)
        assert parse_hours("1011", 2) == ["10", "11"]
        # 3 two-digit hours (10, 11, 12)
        assert parse_hours("101112", 3) == ["10", "11", "12"]
        # 2 single-digit (3, 4) and 2 two-digit (11, 12)
        assert parse_hours("341112", 4) == ["3", "4", "11", "12"]
        # 4 two-digit hours (11, 12, 13, 14)
        assert parse_hours("11121314", 4) == ["11", "12", "13", "14"]

    def test_single_digit_period_one_before_two_digit_period(self) -> None:
        # Period 1 immediately followed by period 10 — a naive left-to-right
        # greedy scan misreads "11" as a two-digit token, yielding ["11", "0"].
        assert parse_hours("110", 2) == ["1", "10"]
        assert parse_hours("1213", 3) == ["1", "2", "13"]

    def test_space_separated_tokens(self) -> None:
        assert parse_hours("1 2 3", 3) == ["1", "2", "3"]
        assert parse_hours("10 11", 2) == ["10", "11"]

    def test_tba_and_empty(self) -> None:
        assert parse_hours("TBA", 3) == ["TBA", "TBA", "TBA"]
        assert parse_hours("  TBA  ", 2) == ["TBA", "TBA"]
        assert parse_hours("", 2) == ["", ""]
        assert parse_hours(None, 2) == ["", ""]

    def test_edge_cases(self) -> None:
        assert parse_hours("123", 0) == []
        assert parse_hours("123", -1) == []
        # Shorter hour string padded with empty string
        assert parse_hours("1", 2) == ["1", ""]


class TestParseRooms:
    """Tests for room replication, delimiter splitting, and padding."""

    def test_single_room_replication(self) -> None:
        assert parse_rooms("NH101", 3) == ["NH101", "NH101", "NH101"]
        assert parse_rooms("KB433", 1) == ["KB433"]

    def test_delimited_rooms(self) -> None:
        assert parse_rooms("NH101 | NH102 | NH103", 3) == ["NH101", "NH102", "NH103"]
        assert parse_rooms("KB433|KB434", 2) == ["KB433", "KB434"]
        assert parse_rooms("M2170\nM2180", 2) == ["M2170", "M2180"]

    def test_padding_and_slicing(self) -> None:
        # Fewer rooms than slots -> pad with empty strings
        assert parse_rooms("NH101 | NH102", 3) == ["NH101", "NH102", ""]
        # More rooms than slots -> slice to num_slots
        assert parse_rooms("A | B | C | D", 2) == ["A", "B"]

    def test_entities_and_empty(self) -> None:
        assert parse_rooms("&nbsp;", 2) == ["", ""]
        assert parse_rooms("  &nbsp;  ", 3) == ["", "", ""]
        assert parse_rooms("", 2) == ["", ""]
        assert parse_rooms(None, 2) == ["", ""]
        assert parse_rooms("TBA", 2) == ["TBA", "TBA"]

    def test_zero_or_negative_slots(self) -> None:
        assert parse_rooms("NH101", 0) == []
        assert parse_rooms("NH101", -2) == []


class TestBuildSlots:
    """Tests for composite CourseSlot construction."""

    def test_standard_3_slot_course(self) -> None:
        slots = build_slots(
            day_str="MWF",
            hour_str="123",
            room_raw="NH101",
            slot_title="CMPE 150.01",
            instructor="SUZAN USKUDARLI",
        )
        assert len(slots) == 3
        assert slots[0] == CourseSlot(
            day="M", hour="1", room="NH101", slot_title="CMPE 150.01", instructor="SUZAN USKUDARLI"
        )
        assert slots[1] == CourseSlot(
            day="W", hour="2", room="NH101", slot_title="CMPE 150.01", instructor="SUZAN USKUDARLI"
        )
        assert slots[2] == CourseSlot(
            day="F", hour="3", room="NH101", slot_title="CMPE 150.01", instructor="SUZAN USKUDARLI"
        )

    def test_two_digit_hours_with_multiple_rooms(self) -> None:
        slots = build_slots(
            day_str="TTh",
            hour_str="1011",
            room_raw="KB433 | KB434",
            slot_title="MATH 101.01",
            instructor="ALP BADER",
        )
        assert len(slots) == 2
        assert slots[0] == CourseSlot(
            day="T", hour="10", room="KB433", slot_title="MATH 101.01", instructor="ALP BADER"
        )
        assert slots[1] == CourseSlot(
            day="Th", hour="11", room="KB434", slot_title="MATH 101.01", instructor="ALP BADER"
        )

    def test_tba_course(self) -> None:
        slots = build_slots(
            day_str="TBA",
            hour_str="TBA",
            room_raw="TBA",
            slot_title="PROJECT",
            instructor="STAFF",
        )
        assert len(slots) == 1
        assert slots[0] == CourseSlot(
            day="TBA", hour="TBA", room="TBA", slot_title="PROJECT", instructor="STAFF"
        )

    def test_empty_day_returns_empty(self) -> None:
        assert build_slots(day_str="", hour_str="", room_raw="") == []
        assert build_slots(day_str=None, hour_str=None, room_raw=None) == []
