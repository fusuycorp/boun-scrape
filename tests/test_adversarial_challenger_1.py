"""Adversarial stress-test harness for Challenger 1.

Exercises:
1. Timestamp filtering & normalization across formats on /api/v1/feeds/quota-snapshots and /api/v1/feeds/deltas.
2. Downstream boun-archive incremental cursor simulation (ASC/DESC polling).
3. Feed ordering (order=asc vs order=desc) and [since, until] range queries.
4. Relational JOIN in get_courses_by_term under stress (0 courses, thousands of courses, orphaned slots).
5. BOUN_WEBHOOK_URLS parsing in Settings & WebhookDispatcher integration.
"""

from datetime import datetime, timezone, timedelta
import os
import tempfile
import urllib.parse
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from boun_scrape.config import Settings
from boun_scrape.domain.events import ChangeType, CourseDeltaEvent
from boun_scrape.domain.models import Course, CourseSlot, QuotaRecord
from boun_scrape.feeds.webhooks import WebhookDispatcher
from boun_scrape.api.app import create_app
from boun_scrape.storage.database import DatabaseManager
from boun_scrape.storage.repository import CourseRepository, _normalize_timestamp


@pytest.fixture
def temp_db_and_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_adversarial.db")
        db = DatabaseManager(db_path)
        db.init_db()
        repo = CourseRepository(db)
        yield db, repo, db_path


@pytest.fixture
def app_client(temp_db_and_repo):
    db, repo, db_path = temp_db_and_repo
    test_settings = Settings(
        environment="test",
        db_path=db_path,
        jwt_secret_key="test-secret-key-12345678901234567890",
        admin_password_hash="$2b$12$e8Y6lF10bB1oA.t1qZzS4eeHkXm9Mv6GzO8eB9kQWvP9C1V2F5c7u",
    )
    app = create_app(test_settings)
    client = TestClient(app)
    return client, repo, db


class TestTimestampFilteringAndFeeds:
    """Stress-test timestamp parsing, filtering, and feed endpoints."""

    def test_timestamp_normalization_unit(self):
        """Test _normalize_timestamp across all valid, weird, and malformed inputs."""
        # 1. ISO-8601 with Z
        norm_z = _normalize_timestamp("2026-08-31T14:30:00Z")
        assert norm_z == "2026-08-31T14:30:00+00:00"

        # 2. ISO-8601 with lowercase z
        norm_z_lower = _normalize_timestamp("2026-08-31T14:30:00z")
        assert norm_z_lower == "2026-08-31T14:30:00+00:00"

        # 3. ISO-8601 with timezone offset +03:00
        norm_offset = _normalize_timestamp("2026-08-31T17:30:00+03:00")
        assert norm_offset == "2026-08-31T14:30:00+00:00"

        # 4. Space separated without timezone (assumed UTC)
        norm_space = _normalize_timestamp("2026-08-31 14:30:00")
        assert norm_space == "2026-08-31T14:30:00+00:00"

        # 5. Unix timestamp epoch in seconds (string integer)
        norm_epoch = _normalize_timestamp("1788186600")
        assert norm_epoch == "2026-08-31T14:30:00+00:00"

        # 6. Unix timestamp epoch with subseconds
        norm_epoch_float = _normalize_timestamp("1788186600.5")
        assert norm_epoch_float.startswith("2026-08-31T14:30:00.500000")

        # 7. Edge inputs: None, empty, whitespace
        assert _normalize_timestamp(None) is None
        assert _normalize_timestamp("") is None
        assert _normalize_timestamp("   ") is None

        # 8. Malformed string falls back safely to raw string
        assert _normalize_timestamp("not-a-timestamp") == "not-a-timestamp"

    def test_quota_snapshots_feed_filtering_formats(self, app_client):
        """Test /api/v1/feeds/quota-snapshots with various timestamp query formats."""
        client, repo, db = app_client

        t0 = datetime(2026, 8, 31, 10, 0, 0, tzinfo=timezone.utc)
        snapshots = []
        for i in range(5):
            snapshots.append((
                "2026-1", "CMPE150", f"0{i+1}",
                QuotaRecord(department="ALL", status="OPEN", quota="50", current=str(10 * i), quota_numeric=50, current_numeric=10*i, is_consent=False, is_unlimited=False, available=50 - 10*i),
            ))

        with db.transaction() as conn:
            for term, code, sec, r in snapshots:
                idx = int(sec) - 1
                t_str = (t0 + timedelta(hours=idx)).isoformat()
                conn.execute(
                    """
                    INSERT INTO quota_snapshots (
                        term, course_code, section, quota_department, status, quota, current,
                        quota_numeric, current_numeric, is_consent, is_unlimited, available, captured_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (term, code, sec, r.department, r.status, r.quota, r.current, r.quota_numeric, r.current_numeric, 0, 0, r.available, t_str),
                )

        # Baseline: get all 5
        res = client.get("/api/v1/feeds/quota-snapshots?term=2026-1")
        assert res.status_code == 200
        assert len(res.json()) == 5

        # Query format 1: ISO with 'Z' (after 11:00 UTC -> should return 12:00, 13:00, 14:00)
        res1 = client.get("/api/v1/feeds/quota-snapshots?term=2026-1&after_timestamp=2026-08-31T11:00:00Z")
        assert res1.status_code == 200
        data1 = res1.json()
        assert len(data1) == 3
        assert [d["section"] for d in data1] == ["03", "04", "05"]

        # Query format 2: URL-encoded Offset +03:00 (14:00 +03:00 == 11:00 UTC)
        res2 = client.get("/api/v1/feeds/quota-snapshots?term=2026-1&after_timestamp=2026-08-31T14:00:00%2B03:00")
        assert res2.status_code == 200
        data2 = res2.json()
        assert len(data2) == 3
        assert [d["section"] for d in data2] == ["03", "04", "05"]

        # Query format 3: Space-separated (2026-08-31 11:00:00)
        res3 = client.get("/api/v1/feeds/quota-snapshots?term=2026-1&after_timestamp=2026-08-31%2011:00:00")
        assert res3.status_code == 200
        data3 = res3.json()
        assert len(data3) == 3
        assert [d["section"] for d in data3] == ["03", "04", "05"]

        # Query format 4: Unix epoch for 2026-08-31 11:00:00 UTC
        epoch_11 = int(datetime(2026, 8, 31, 11, 0, 0, tzinfo=timezone.utc).timestamp())
        res4 = client.get(f"/api/v1/feeds/quota-snapshots?term=2026-1&after_timestamp={epoch_11}")
        assert res4.status_code == 200
        data4 = res4.json()
        assert len(data4) == 3
        assert [d["section"] for d in data4] == ["03", "04", "05"]

    def test_boun_archive_incremental_polling_simulation(self, app_client):
        """Simulate downstream boun-archive incremental cursor polling loop."""
        client, repo, db = app_client

        # Seed initial batch of snapshots
        t0 = datetime(2026, 8, 31, 8, 0, 0, tzinfo=timezone.utc)
        with db.transaction() as conn:
            for i in range(10):
                t_str = (t0 + timedelta(minutes=i*10)).isoformat()
                conn.execute(
                    """
                    INSERT INTO quota_snapshots (
                        term, course_code, section, quota_department, status, quota, current,
                        quota_numeric, current_numeric, is_consent, is_unlimited, available, captured_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("2026-1", "MATH101", f"sec_{i:02d}", "ALL", "OPEN", "50", str(i), 50, i, 0, 0, 50-i, t_str),
                )

        # Downstream boun-archive polls in ASC order with limit=4, using url-encoded cursor
        all_polled = []
        cursor = None
        for _ in range(5):
            url = "/api/v1/feeds/quota-snapshots?term=2026-1&order=asc&limit=4"
            if cursor:
                url += f"&after_timestamp={urllib.parse.quote(cursor)}"
            res = client.get(url)
            assert res.status_code == 200
            items = res.json()
            if not items:
                break
            all_polled.extend(items)
            cursor = items[-1]["captured_at"]

        # Verify all 10 items were collected in exact chronological order without duplicates or skips
        assert len(all_polled) == 10
        sections_polled = [item["section"] for item in all_polled]
        expected_sections = [f"sec_{i:02d}" for i in range(10)]
        assert sections_polled == expected_sections

        # Now insert 3 new snapshots dynamically and poll once more
        t_new = t0 + timedelta(minutes=200)
        with db.transaction() as conn:
            for i in range(10, 13):
                t_str = (t_new + timedelta(minutes=i)).isoformat()
                conn.execute(
                    """
                    INSERT INTO quota_snapshots (
                        term, course_code, section, quota_department, status, quota, current,
                        quota_numeric, current_numeric, is_consent, is_unlimited, available, captured_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("2026-1", "MATH101", f"sec_{i:02d}", "ALL", "OPEN", "50", str(i), 50, i, 0, 0, 50-i, t_str),
                )

        encoded_cursor = urllib.parse.quote(cursor)
        res_increment = client.get(f"/api/v1/feeds/quota-snapshots?term=2026-1&order=asc&limit=10&after_timestamp={encoded_cursor}")
        assert res_increment.status_code == 200
        new_items = res_increment.json()
        assert len(new_items) == 3
        assert [item["section"] for item in new_items] == ["sec_10", "sec_11", "sec_12"]


class TestFeedOrderingAndRangeQueries:
    """Stress-test feed ordering (asc/desc) and [since, until] range filters."""

    def test_deltas_feed_asc_vs_desc_and_case_insensitivity(self, app_client):
        """Verify order=asc vs order=desc on /api/v1/feeds/deltas."""
        client, repo, db = app_client

        t0 = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)
        events = []
        for i in range(6):
            events.append(
                CourseDeltaEvent(
                    change_type=ChangeType.MODIFIED,
                    term="2026-1",
                    department="CMPE",
                    course_code="CMPE150",
                    section=f"0{i+1}",
                    timestamp=(t0 + timedelta(minutes=i*10)).isoformat(),
                    old_value={"instructor": f"Inst_{i}"},
                    new_value={"instructor": f"Inst_{i+1}"},
                    details=f"Delta {i}",
                )
            )
        repo.save_deltas(events, run_id="run_order_test")

        # 1. Default order is DESC (newest first)
        res_default = client.get("/api/v1/feeds/deltas?term=2026-1")
        assert res_default.status_code == 200
        desc_items = res_default.json()
        assert [d["section"] for d in desc_items] == ["06", "05", "04", "03", "02", "01"]

        # 2. Explicit order=desc
        res_desc = client.get("/api/v1/feeds/deltas?term=2026-1&order=desc")
        assert res_desc.status_code == 200
        assert [d["section"] for d in res_desc.json()] == ["06", "05", "04", "03", "02", "01"]

        # 3. Explicit order=asc
        res_asc = client.get("/api/v1/feeds/deltas?term=2026-1&order=asc")
        assert res_asc.status_code == 200
        assert [d["section"] for d in res_asc.json()] == ["01", "02", "03", "04", "05", "06"]

        # 4. Case-insensitivity: order=ASC and order=DESC
        res_caps_asc = client.get("/api/v1/feeds/deltas?term=2026-1&order=ASC")
        assert res_caps_asc.status_code == 200
        assert [d["section"] for d in res_caps_asc.json()] == ["01", "02", "03", "04", "05", "06"]

        res_caps_desc = client.get("/api/v1/feeds/deltas?term=2026-1&order=DESC")
        assert res_caps_desc.status_code == 200
        assert [d["section"] for d in res_caps_desc.json()] == ["06", "05", "04", "03", "02", "01"]

        # 5. Invalid order rejected by validator with 422
        res_invalid = client.get("/api/v1/feeds/deltas?term=2026-1&order=invalid_order")
        assert res_invalid.status_code == 422

    def test_feed_since_and_until_range_queries(self, app_client):
        """Stress-test [since, until] range boundaries and edge cases on feeds."""
        client, repo, db = app_client

        t0 = datetime(2026, 8, 31, 10, 0, 0, tzinfo=timezone.utc)
        events = []
        for i in range(10):  # 10:00 to 10:45 in 5-min intervals
            events.append(
                CourseDeltaEvent(
                    change_type=ChangeType.MODIFIED,
                    term="2026-1",
                    department="MATH",
                    course_code="MATH201",
                    section=f"sec_{i:02d}",
                    timestamp=(t0 + timedelta(minutes=i*5)).isoformat(),
                    old_value=None,
                    new_value={"credits": 4.0},
                    details=f"Interval {i}",
                )
            )
        repo.save_deltas(events, run_id="run_range_test")

        # Range 1: since 10:10 to until 10:30 (inclusive: indices 2, 3, 4, 5, 6 -> 5 items)
        since_ts = urllib.parse.quote((t0 + timedelta(minutes=10)).isoformat())
        until_ts = urllib.parse.quote((t0 + timedelta(minutes=30)).isoformat())
        res_range = client.get(f"/api/v1/feeds/deltas?term=2026-1&since={since_ts}&until={until_ts}&order=asc")
        assert res_range.status_code == 200
        items = res_range.json()
        assert len(items) == 5
        assert [d["section"] for d in items] == ["sec_02", "sec_03", "sec_04", "sec_05", "sec_06"]

        # Range 2: since == until (exact point in time)
        exact_ts = urllib.parse.quote((t0 + timedelta(minutes=15)).isoformat())
        res_exact = client.get(f"/api/v1/feeds/deltas?term=2026-1&since={exact_ts}&until={exact_ts}")
        assert res_exact.status_code == 200
        items_exact = res_exact.json()
        assert len(items_exact) == 1
        assert items_exact[0]["section"] == "sec_03"

        # Range 3: since > until (inverted window -> empty)
        res_empty = client.get(f"/api/v1/feeds/deltas?term=2026-1&since={until_ts}&until={since_ts}")
        assert res_empty.status_code == 200
        assert len(res_empty.json()) == 0


class TestRelationalJoinInGetCoursesByTerm:
    """Stress-test the relational JOIN in get_courses_by_term against edge cases."""

    def test_term_with_zero_courses(self, temp_db_and_repo):
        """Edge case 1: Querying a term with no courses returns empty list without error."""
        db, repo, _ = temp_db_and_repo
        courses = repo.get_courses_by_term("NONEXISTENT_TERM")
        assert courses == []

    def test_large_term_with_thousands_of_courses_and_slots(self, temp_db_and_repo):
        """Edge case 2: Querying 1,500 courses with 4,500 slots succeeds via single JOIN."""
        db, repo, _ = temp_db_and_repo

        term = "2026-STRESS"
        total_courses_count = 1500
        batch_courses = []
        for i in range(total_courses_count):
            slots = [
                CourseSlot(
                    id=None,
                    course_id=None,
                    day="M",
                    hour=f"{h}:00",
                    room=f"NH{h}01",
                    slot_title=f"Slot {h}",
                    instructor=f"Prof. {i}",
                )
                for h in range(1, 4)
            ]
            batch_courses.append(
                Course(
                    id=None,
                    term=term,
                    department="CMPE",
                    course_code=f"CMPE{100 + (i % 500)}",
                    section=f"{i:04d}",
                    course_name=f"Course Name {i}",
                    instructor=f"Prof. {i}",
                    credits=3.0,
                    ects=6.0,
                    delivery_method="Face to Face",
                    exam_location="TBD",
                    exam_date="TBD",
                    sl="",
                    required_for="",
                    departments="",
                    slots=slots,
                )
            )

        persisted_count = repo.save_courses_and_slots(term, batch_courses)
        assert persisted_count == total_courses_count

        # Fetch all via relational JOIN
        loaded_courses = repo.get_courses_by_term(term)
        assert len(loaded_courses) == total_courses_count
        # Verify slot integrity on sampled items
        assert len(loaded_courses[0].slots) == 3
        assert len(loaded_courses[-1].slots) == 3
        assert loaded_courses[0].slots[0].day == "M"

    def test_orphaned_slots_and_cross_term_isolation(self, temp_db_and_repo):
        """Edge case 3: Orphaned slots and slots from other terms do not leak or corrupt results."""
        db, repo, _ = temp_db_and_repo

        # Create Course in Term A
        course_a = Course(
            id=None,
            term="2026-A",
            department="PHYS",
            course_code="PHYS101",
            section="01",
            course_name="Physics I",
            instructor="Dr. Newton",
            credits=4.0,
            ects=7.0,
            delivery_method="In Person",
            exam_location="KB",
            exam_date="TBD",
            sl="",
            required_for="",
            departments="",
            slots=[CourseSlot(id=None, course_id=None, day="W", hour="1", room="KB101", slot_title="Lecture", instructor="Dr. Newton")],
        )
        repo.save_courses_and_slots("2026-A", [course_a])

        # Create Course in Term B
        course_b = Course(
            id=None,
            term="2026-B",
            department="CHEM",
            course_code="CHEM101",
            section="01",
            course_name="Chemistry I",
            instructor="Dr. Curie",
            credits=4.0,
            ects=7.0,
            delivery_method="In Person",
            exam_location="KB",
            exam_date="TBD",
            sl="",
            required_for="",
            departments="",
            slots=[CourseSlot(id=None, course_id=None, day="Th", hour="2", room="KB102", slot_title="Lab", instructor="Dr. Curie")],
        )
        repo.save_courses_and_slots("2026-B", [course_b])

        # Manually insert an orphaned slot with course_id=999999 (non-existent)
        with db.transaction() as conn:
            conn.execute("PRAGMA foreign_keys = OFF;")
            conn.execute(
                """
                INSERT INTO course_slots (course_id, day, hour, room, slot_title, instructor)
                VALUES (999999, 'F', '5', 'ORPHAN_ROOM', 'Ghost Slot', 'Ghost')
                """
            )
            conn.execute("PRAGMA foreign_keys = ON;")

        # Fetch Term A: should only have PHYS101 with 1 slot
        courses_a = repo.get_courses_by_term("2026-A")
        assert len(courses_a) == 1
        assert courses_a[0].course_code == "PHYS101"
        assert len(courses_a[0].slots) == 1
        assert courses_a[0].slots[0].room == "KB101"

        # Fetch Term B: should only have CHEM101 with 1 slot
        courses_b = repo.get_courses_by_term("2026-B")
        assert len(courses_b) == 1
        assert courses_b[0].course_code == "CHEM101"
        assert len(courses_b[0].slots) == 1
        assert courses_b[0].slots[0].room == "KB102"


class TestWebhookUrlsEnvParsing:
    """Stress-test BOUN_WEBHOOK_URLS parsing and WebhookDispatcher."""

    @pytest.mark.parametrize(
        "raw_val, expected",
        [
            ("https://a.com/hook, https://b.com/hook", ["https://a.com/hook", "https://b.com/hook"]),
            (" , https://a.com/hook , , https://b.com/hook , ", ["https://a.com/hook", "https://b.com/hook"]),
            ('["https://a.com/hook", "https://b.com/hook"]', ["https://a.com/hook", "https://b.com/hook"]),
            ('[\n  "https://a.com/hook",\n  "https://b.com/hook"\n]', ["https://a.com/hook", "https://b.com/hook"]),
            ("", []),
            ("   ", []),
            ("https://single.com/hook", ["https://single.com/hook"]),
        ],
    )
    def test_settings_webhook_urls_parsing_matrix(self, raw_val, expected):
        """Verify Settings parses various BOUN_WEBHOOK_URLS formats accurately."""
        s = Settings(
            environment="test",
            webhook_urls=raw_val,
            jwt_secret_key="test-secret-key-12345678901234567890",
            admin_password_hash="$2b$12$e8Y6lF10bB1oA.t1qZzS4eeHkXm9Mv6GzO8eB9kQWvP9C1V2F5c7u",
        )
        assert s.webhook_urls == expected

    def test_webhook_dispatcher_with_parsed_urls(self):
        """Verify WebhookDispatcher initializes with parsed URLs from Settings."""
        s = Settings(
            environment="test",
            webhook_urls="https://service-a.internal/hook, https://service-b.internal/hook",
            jwt_secret_key="test-secret-key-12345678901234567890",
            admin_password_hash="$2b$12$e8Y6lF10bB1oA.t1qZzS4eeHkXm9Mv6GzO8eB9kQWvP9C1V2F5c7u",
        )
        dispatcher = WebhookDispatcher(urls=s.webhook_urls, settings=s)
        assert dispatcher.urls == ["https://service-a.internal/hook", "https://service-b.internal/hook"]
