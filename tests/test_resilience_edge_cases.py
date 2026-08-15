"""Resilience and edge case test suite for parsing, tokenization, encoding, and concurrency."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest

from boun_scrape.domain.models import Course, CourseSlot, QuotaRecord
from boun_scrape.scraper.client import decode_windows_1254
from boun_scrape.scraper.parser import (
    extract_viewstate_and_semesters,
    parse_departments_from_html,
    parse_quota_from_html,
    parse_schedules_from_html,
)
from boun_scrape.scraper.quota import QuotaService, format_course_key
from boun_scrape.scraper.slot_tokenizer import (
    build_slots,
    parse_days,
    parse_hours,
    parse_rooms,
)
from boun_scrape.storage.database import DatabaseManager
from boun_scrape.storage.repository import CourseRepository


class TestMalformedHtmlResilience:
    """Tests resilience against truncated, unclosed, or invalid HTML."""

    def test_empty_and_whitespace_html(self) -> None:
        assert parse_departments_from_html("") == []
        assert parse_departments_from_html("   \n\t  ") == []
        assert parse_schedules_from_html("", "2024/2025-1", "CMPE") == []
        assert parse_quota_from_html("") == []
        vs, sems = extract_viewstate_and_semesters("")
        assert vs == {}
        assert sems == []

    def test_truncated_and_unclosed_tags_in_schedule(self) -> None:
        html = """
        <html><body>
        <table>
            <tr class="schtd">
                <td>CMPE 150.01</td><td></td><td>Intro</td><td>3</td><td>6</td>
                <td>Prof. Smith</td><td>MW</td><td>12</td><td>In Person</td>
        """
        # Less than 11 td cells - should not crash, returns empty list
        courses = parse_schedules_from_html(html, "2024/2025-1", "CMPE")
        assert courses == []

    def test_schedule_with_broken_continuation_row(self) -> None:
        # Continuation row without any preceding primary course row
        html = """
        <table>
            <tr class="schtd">
                <td></td><td></td><td>P.S.</td><td></td><td></td>
                <td>TA Jane</td><td>F</td><td>56</td><td></td><td></td><td>LAB1</td>
                <td></td><td></td><td></td><td></td>
            </tr>
        </table>
        """
        courses = parse_schedules_from_html(html, "2024/2025-1", "CMPE")
        assert courses == []

    def test_quota_with_missing_columns(self) -> None:
        html = """
        <table>
            <tr class="schtd">
                <td>CMPE</td><td>Open</td>
            </tr>
        </table>
        """
        # Less than 4 td cells in row
        records = parse_quota_from_html(html)
        assert records == []

    def test_html_without_tables(self) -> None:
        html = "<div><p>Some random non-table content error page</p></div>"
        assert parse_departments_from_html(html) == []
        assert parse_schedules_from_html(html, "2024/2025-1", "CMPE") == []
        assert parse_quota_from_html(html) == []


class TestTurkishWindows1254Encoding:
    """Tests Turkish characters roundtrip and Windows-1254 encoding handling."""

    def test_windows_1254_decoding_roundtrip(self) -> None:
        turkish_text = (
            "Boğaziçi Üniversitesi Bilgisayar Mühendisliği Bölümü "
            "İnşaat, Çevre, Öğretim Üyesi: Doç. Dr. Şölen Güzel (Iı İi Ğğ Üü Şş Öö Çç)"
        )
        encoded_bytes = turkish_text.encode("windows-1254")
        decoded_text = decode_windows_1254(encoded_bytes)
        assert decoded_text == turkish_text

    def test_department_parsing_with_turkish_characters(self) -> None:
        html = """
        <table class="table-bordered">
            <tr>
                <td><a href="/scripts/sch.asp?kisaadi=CMPE&bolum=B%DDLG%DDSAYAR+M%DCHEND%DDSL%DD%D0%DD">BİLGİSAYAR MÜHENDİSLİĞİ</a></td>
                <td><a href="/scripts/sch.asp?kisaadi=CE&bolum=%DDN%DEAAT+M%DCHEND%DDSL%DD%D0%DD">İNŞAAT MÜHENDİSLİĞİ</a></td>
            </tr>
        </table>
        """
        depts = parse_departments_from_html(html)
        assert len(depts) == 2
        assert depts[0].code == "CMPE"
        assert depts[0].name == "BİLGİSAYAR MÜHENDİSLİĞİ"
        assert depts[1].code == "CE"
        assert depts[1].name == "İNŞAAT MÜHENDİSLİĞİ"

    def test_schedules_with_turkish_instructor_and_course_name(self) -> None:
        html = """
        <table>
            <tr class="schtd">
                <td>TK 221.01</td><td></td><td>Türk Dili I</td><td>2</td><td>2</td>
                <td>Öğr. Gör. Şükrü Şen</td><td>M</td><td>34</td><td>Yüzyüze</td><td></td><td>ÖEB 101</td>
                <td></td><td></td><td></td><td></td>
            </tr>
        </table>
        """
        courses = parse_schedules_from_html(html, "2024/2025-1", "TK")
        assert len(courses) == 1
        assert courses[0].course_code == "TK 221"
        assert courses[0].course_name == "Türk Dili I"
        assert courses[0].instructor == "Öğr. Gör. Şükrü Şen"


class TestDoubleDigitPeriodsAndIrregularDays:
    """Tests complex hours, double-digit partition (10-14), and irregular day combinations."""

    def test_hours_partition_10_to_14(self) -> None:
        # 3 slots: 10, 11, 12
        assert parse_hours("101112", 3) == ["10", "11", "12"]

        # 4 slots: 8, 9, 10, 11
        assert parse_hours("891011", 4) == ["8", "9", "10", "11"]

        # 5 slots: 10, 11, 12, 13, 14
        assert parse_hours("1011121314", 5) == ["10", "11", "12", "13", "14"]

        # 4 slots: 7, 8, 9, 10
        assert parse_hours("78910", 4) == ["7", "8", "9", "10"]

        # 1 slot: 11
        assert parse_hours("11", 1) == ["11"]

        # 2 slots: 1, 1
        assert parse_hours("11", 2) == ["1", "1"]

    def test_irregular_day_combinations(self) -> None:
        # Thursday, Saturday, Sunday
        assert parse_days("ThStSu") == ["Th", "St", "Su"]

        # Monday, Wednesday, Thursday, Friday
        assert parse_days("MWThF") == ["M", "W", "Th", "F"]

        # Tuesday, Thursday, Saturday
        assert parse_days("TThSt") == ["T", "Th", "St"]

        # Days with embedded whitespace
        assert parse_days("M W F") == ["M", "W", "F"]
        assert parse_days("Th  St") == ["Th", "St"]

        # TBA
        assert parse_days("TBA") == ["TBA"]

    def test_rooms_broadcasting_and_newlines(self) -> None:
        # Broadcast single room across 3 slots
        assert parse_rooms("NH101", 3) == ["NH101", "NH101", "NH101"]

        # Newline separated rooms
        assert parse_rooms("NH101\nNH102\nNH103", 3) == ["NH101", "NH102", "NH103"]

        # Pipe separated with html non-breaking space
        assert parse_rooms("NH101 | &nbsp; | KB433", 3) == ["NH101", "", "KB433"]

        # Padding when fewer rooms than slots
        assert parse_rooms("NH101 | NH102", 4) == ["NH101", "NH102", "", ""]

    def test_build_slots_full_integration(self) -> None:
        slots = build_slots(
            day_str="MWTh",
            hour_str="1 2 10",
            room_raw="NH101 | NH102 | NH103",
            slot_title="Main Lecture",
            instructor="Prof. Smith",
        )
        assert len(slots) == 3
        assert slots[0].day == "M" and slots[0].hour == "1" and slots[0].room == "NH101"
        assert slots[1].day == "W" and slots[1].hour == "2" and slots[1].room == "NH102"
        assert slots[2].day == "Th" and slots[2].hour == "10" and slots[2].room == "NH103"


class TestNonStandardQuotaStrings:
    """Tests parsing and computation of special quota statuses and edge cases."""

    def test_closed_consent_quota(self) -> None:
        html = """
        <table>
            <tr class="schtd">
                <td>CMPE</td><td>Closed</td><td>Consent</td><td>12</td>
            </tr>
        </table>
        """
        records = parse_quota_from_html(html)
        assert len(records) == 1
        r = records[0]
        assert r.status == "Closed"
        assert r.is_consent is True
        assert r.available is None

    def test_unlimited_quota(self) -> None:
        html = """
        <table>
            <tr class="schtd">
                <td>ALL</td><td>Open</td><td>Unlimited</td><td>85</td>
            </tr>
        </table>
        """
        records = parse_quota_from_html(html)
        assert len(records) == 1
        r = records[0]
        assert r.is_unlimited is True
        assert r.available is None

    def test_zero_capacity_slot(self) -> None:
        html = """
        <table>
            <tr class="schtd">
                <td>MATH</td><td>Closed</td><td>0</td><td>0</td>
            </tr>
        </table>
        """
        records = parse_quota_from_html(html)
        assert len(records) == 1
        r = records[0]
        assert r.quota_numeric == 0
        assert r.current_numeric == 0
        assert r.available == 0

    def test_overenrolled_negative_availability(self) -> None:
        html = """
        <table>
            <tr class="schtd">
                <td>CMPE</td><td>Closed</td><td>50</td><td>55</td>
            </tr>
        </table>
        """
        records = parse_quota_from_html(html)
        assert len(records) == 1
        r = records[0]
        assert r.quota_numeric == 50
        assert r.current_numeric == 55
        assert r.available == -5

    def test_non_numeric_quota_strings(self) -> None:
        html = """
        <table>
            <tr class="schtd">
                <td>PHYS</td><td>Open</td><td>TBA</td><td>-</td>
            </tr>
        </table>
        """
        records = parse_quota_from_html(html)
        assert len(records) == 1
        r = records[0]
        assert r.quota_numeric is None
        assert r.current_numeric is None
        assert r.available is None


class TestConcurrencyAndThreadSafety:
    """Tests multi-threaded concurrent database operations and quota caching."""

    def test_concurrent_sqlite_writes_and_reads(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "concurrent_test.db")
        db_mgr = DatabaseManager(db_path)
        db_mgr.init_db()

        def _worker(worker_id: int) -> int:
            repo = CourseRepository(db_mgr)
            term = f"202{worker_id}/202{worker_id + 1}-1"
            courses = [
                Course(
                    term=term,
                    department="CMPE",
                    course_code=f"CMPE{100 + worker_id}",
                    section="01",
                    course_name=f"Course {worker_id}",
                    slots=[CourseSlot(day="M", hour="12", room="NH101")],
                )
            ]
            saved = repo.save_courses_and_slots(term, courses)
            fetched = repo.get_courses_by_term(term)
            assert len(fetched) == 1
            return saved

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(_worker, i) for i in range(1, 9)]
            results = [f.result() for f in futures]

        assert sum(results) == 8
        repo = CourseRepository(db_mgr)
        terms = repo.get_terms()
        assert len(terms) == 8

    @pytest.mark.asyncio
    async def test_concurrent_quota_cache_access(self) -> None:
        quota_svc = QuotaService(ttl_seconds=60.0)
        # Pre-seed cache manually
        records = [
            QuotaRecord(
                department="CMPE",
                status="Open",
                quota="50",
                current="40",
                quota_numeric=50,
                current_numeric=40,
                is_consent=False,
                is_unlimited=False,
                available=10,
            )
        ]
        key = quota_svc._make_cache_key("2024/2025-1", "CMPE", "150", "01")
        async with quota_svc._lock:
            from boun_scrape.scraper.quota import _QuotaCacheEntry
            import time
            quota_svc._cache[key] = _QuotaCacheEntry(
                timestamp=time.monotonic(),
                records=records,
            )

        async def _fetch_task() -> list[QuotaRecord]:
            return await quota_svc.fetch_quota(
                term="2024/2025-1",
                abbr="CMPE",
                code="150",
                section="01",
                bypass_cache=False,
            )

        tasks = [_fetch_task() for _ in range(20)]
        all_results = await asyncio.gather(*tasks)
        assert len(all_results) == 20
        for res in all_results:
            assert len(res) == 1
            assert res[0].available == 10
        await quota_svc.aclose()

    def test_course_key_formatting_edge_cases(self) -> None:
        assert format_course_key("cmpe", "150", "01") == "CMPE 150.01"
        assert format_course_key("cmpe", "cmpe 150", "02") == "CMPE 150.02"
        assert format_course_key("MATH", "101", "") == "MATH 101"
        assert format_course_key("  phys  ", "  phys 101  ", "  01  ") == "PHYS 101.01"
