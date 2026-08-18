"""Scraper and HTML parser modules for Boğaziçi University data."""

from boun_scrape.scraper.client import (
    BounError,
    BounHttpError,
    BounScraperClient,
    RecaptchaBlockedError,
    SessionExpiredError,
    decode_windows_1254,
    load_recaptcha_token,
    parse_cookie_file,
    parse_cookie_text,
    parse_curl_command,
)
from boun_scrape.scraper.flow import (
    discover_terms,
    fetch_department_schedule,
    fetch_departments,
    scrape_term_pipeline,
)
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

__all__ = [
    "BounError",
    "BounHttpError",
    "BounScraperClient",
    "RecaptchaBlockedError",
    "SessionExpiredError",
    "build_slots",
    "decode_windows_1254",
    "discover_terms",
    "extract_viewstate_and_semesters",
    "fetch_department_schedule",
    "fetch_departments",
    "format_course_key",
    "load_recaptcha_token",
    "parse_cookie_file",
    "parse_cookie_text",
    "parse_curl_command",
    "parse_days",
    "parse_departments_from_html",
    "parse_hours",
    "parse_quota_from_html",
    "parse_rooms",
    "parse_schedules_from_html",
    "QuotaService",
    "scrape_term_pipeline",
]

