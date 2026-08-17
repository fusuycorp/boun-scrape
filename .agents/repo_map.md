# Repository Map

Total mapped files: 110

- `.agents/activity.jsonl` (6000 B)
- `.agents/decisions.md` (8440 B)
- `.agents/memory.md` (5126 B)
- `.agents/repo_map.md` (15753 B)
- `.env.example` (872 B)
- `.github/workflows/deploy.yml` (2825 B)
- `.gitignore` (120 B)
- `Dockerfile` (1189 B)
- `README.md` (7768 B)
- `docker-compose.yml` (971 B)
- `docs/README.md` (3968 B)
- `docs/api-reference.md` (7380 B)
- `docs/architecture.md` (13431 B)
- `docs/backend-architecture.md` (10881 B)
- `docs/database-schema.md` (10486 B)
- `docs/frontend-architecture.md` (7676 B)
- `docs/llm-context.md` (10592 B)
- `docs/scraping-pipeline.md` (9985 B)
- `frontend/.dockerignore` (296 B)
- `frontend/.gitignore` (253 B)
- `frontend/Dockerfile` (620 B)
- `frontend/README.md` (1829 B)
- `frontend/bun.lock` (45872 B)
- `frontend/eslint.config.js` (1097 B)
- `frontend/index.html` (576 B)
- `frontend/nginx.conf` (839 B)
- `frontend/package.json` (735 B)
- `frontend/public/favicon.svg` (9522 B)
- `frontend/public/icons.svg` (5031 B)
- `frontend/src/App.css` (33 B)
- `frontend/src/App.jsx` (5357 B)
    * function ProtectedRoute
    * const location
    * function StatusTicker
    * const now
    * const timestamp
    * function MainLayout
- `frontend/src/api/client.js` (3481 B)
    * const getAuthHeader
    * const token
    * let url
    * const searchParams
    * const queryString
    * const reqHeaders
- `frontend/src/assets/hero.png` (13057 B)
- `frontend/src/assets/react.svg` (4126 B)
- `frontend/src/assets/vite.svg` (8709 B)
- `frontend/src/components/ConfigManager.jsx` (6312 B)
    * const showToast
    * const isMountedRef
    * const fetchConfig
    * const res
    * const isDirty
    * const handleSave
- `frontend/src/components/ConfirmDialog.jsx` (4830 B)
    * const confirmBtnRef
    * const previouslyFocused
    * const t
    * const handleKey
- `frontend/src/components/CourseData.jsx` (21896 B)
    * const showToast
    * const isMountedRef
    * const timer
    * const fetchCourses
    * const res
    * const daysList
- `frontend/src/components/Dashboard.jsx` (11571 B)
    * const navigate
    * const showToast
    * const isMountedRef
    * const fetchDashboardData
    * const statCards
    * const Icon
- `frontend/src/components/EmptyState.jsx` (1743 B)
- `frontend/src/components/Login.jsx` (5118 B)
    * const navigate
    * const showToast
    * const handleSubmit
- `frontend/src/components/QuotaMonitor.jsx` (15280 B)
    * const showToast
    * const isMountedRef
    * const saved
    * const fetchSingleQuota
    * const key
    * const res
- `frontend/src/components/ScraperControl.jsx` (10839 B)
    * const showToast
    * const isMountedRef
    * const logTerminalRef
    * const autoScrollRef
    * const formatLogEntry
    * const pollScraper
- `frontend/src/components/Sidebar.jsx` (6695 B)
    * const navItems
    * const toggleMobile
    * const closeMobile
    * const navLinkStyle
    * const Icon
- `frontend/src/components/Toast.jsx` (4144 B)
    * let toastIdSeed
    * const VARIANT_STYLES
    * export function ToastProvider
    * const timersRef
    * const dismiss
    * const timer
- `frontend/src/contexts/AuthContext.jsx` (1797 B)
    * const AuthContext
    * export function AuthProvider
    * const validateSession
    * const meData
    * const login
    * const data
- `frontend/src/hooks/useSafeAsync.js` (712 B)
    * export function useMountedRef
    * const isMountedRef
    * export function useSafeCallback
    * const isMountedRef
- `frontend/src/hooks/useToast.js` (708 B)
    * export const ToastContext
    * export function useToast
    * const ctx
    * const showToast
- `frontend/src/index.css` (10815 B)
- `frontend/src/main.jsx` (229 B)
- `frontend/vite.config.js` (351 B)
- `pyproject.toml` (863 B)
- `src/boun_scrape/__init__.py` (130 B)
- `src/boun_scrape/api/__init__.py` (105 B)
- `src/boun_scrape/api/app.py` (3799 B)
    * def lifespan()
    * def create_app()
- `src/boun_scrape/api/auth.py` (3823 B)
    * def _b64_encode()
    * def _b64_decode()
    * def create_jwt_token()
    * def verify_jwt_token()
    * def verify_password()
    * def get_current_user()
- `src/boun_scrape/api/deps.py` (4145 B)
    * def get_settings_dep()
    * def _get_shared_db_manager()
    * def get_db_manager_dep()
    * def get_course_repo_dep()
    * def _get_shared_scraper_client()
    * def get_scraper_client_dep()
- `src/boun_scrape/api/logging_buffer.py` (2826 B)
    * class LogBuffer (__init__, add, get_logs, clear, __len__)
    * class BufferLoggingHandler (__init__, emit)
    * def get_global_log_buffer()
    * def setup_api_logging()
- `src/boun_scrape/api/rate_limit.py` (1808 B)
    * class RateLimiter (__init__, check)
    * def _client_ip()
    * def login_rate_limit_dep()
    * def quota_rate_limit_dep()
- `src/boun_scrape/api/routes/__init__.py` (451 B)
- `src/boun_scrape/api/routes/auth.py` (1569 B)
    * class Token
    * class UserInfo
    * def login()
    * def get_me()
- `src/boun_scrape/api/routes/courses.py` (4730 B)
    * def get_courses()
    * def get_course_by_id()
    * def get_departments()
    * def get_terms()
    * def get_stats()
- `src/boun_scrape/api/routes/feeds.py` (3991 B)
    * def get_deltas()
    * def get_scrape_runs()
    * def download_export()
- `src/boun_scrape/api/routes/quota.py` (3384 B)
    * def _resolve_term()
    * def get_course_quota()
    * def get_batch_course_quota()
- `src/boun_scrape/api/routes/scraper.py` (5304 B)
    * class CookieUpdateRequest
    * def trigger_scrape()
    * def get_scraper_status()
    * def stop_scraper()
    * def get_scraper_logs()
    * def get_scraper_config()
- `src/boun_scrape/cli/__init__.py` (108 B)
- `src/boun_scrape/cli/__main__.py` (127 B)
- `src/boun_scrape/cli/app.py` (10878 B)
    * def scrape_command()
    * def serve_command()
    * def daemon_command()
    * def export_command()
    * def quota_command()
    * def main()
- `src/boun_scrape/config.py` (5296 B)
    * class Settings (_resolve_secrets, parse_allowed_origins)
    * def get_settings()
- `src/boun_scrape/domain/__init__.py` (948 B)
- `src/boun_scrape/domain/dto.py` (6957 B)
    * class CourseSlotDTO
    * class CourseDTO
    * class DepartmentDTO
    * class QuotaDTO
    * class DeltaEventDTO
    * class ScrapeRunDTO
- `src/boun_scrape/domain/events.py` (1036 B)
    * class ChangeType
    * class CourseDeltaEvent
    * class ScrapeEvent
- `src/boun_scrape/domain/models.py` (3053 B)
    * class DayOfWeek
    * class QuotaStatus
    * class RunStatus
    * class Department
    * class CourseSlot
    * class Course (full_code)
- `src/boun_scrape/feeds/__init__.py` (217 B)
- `src/boun_scrape/feeds/webhooks.py` (9662 B)
    * class WebhookDeliveryResult
    * def compute_hmac_signature()
    * def serialize_webhook_payload()
    * class WebhookDispatcher (__init__, _send_to_single_url, dispatch, dispatch_deltas, dispatch_run_summary...)
- `src/boun_scrape/pipeline/__init__.py` (618 B)
- `src/boun_scrape/pipeline/delta.py` (7977 B)
    * def course_slot_to_dict()
    * def course_to_dict()
    * def compute_course_hash()
    * def compute_deltas()
- `src/boun_scrape/pipeline/exporter.py` (8152 B)
    * def _tmp_path_for()
    * def _sanitize_term()
    * def export_courses_json()
    * def export_courses_csv()
    * def _write_courses_csv()
    * def export_courses_sqlite()
- `src/boun_scrape/scheduler/__init__.py` (151 B)
- `src/boun_scrape/scheduler/runner.py` (13838 B)
    * class ScrapeSchedulerError
    * class ScrapeAlreadyRunningError
    * class ScrapeScheduler (__init__, is_running, is_scraping, get_status, execute_scrape_cycle...)
- `src/boun_scrape/scraper/__init__.py` (1370 B)
- `src/boun_scrape/scraper/client.py` (10346 B)
    * class BounError
    * class RecaptchaBlockedError
    * class BounHttpError (__init__)
    * class SessionExpiredError
    * def parse_cookie_text()
    * def parse_cookie_file()
- `src/boun_scrape/scraper/flow.py` (4818 B)
    * def discover_terms()
    * def fetch_departments()
    * def fetch_department_schedule()
    * def scrape_term_pipeline()
- `src/boun_scrape/scraper/parser.py` (8582 B)
    * def _parse_float()
    * def extract_viewstate_and_semesters()
    * def parse_departments_from_html()
    * def parse_schedules_from_html()
    * def parse_quota_from_html()
- `src/boun_scrape/scraper/quota.py` (6333 B)
    * def format_course_key()
    * class _QuotaCacheEntry
    * class QuotaService (__init__, client, cache_size, clear_cache, _make_cache_key...)
- `src/boun_scrape/scraper/slot_tokenizer.py` (4820 B)
    * def parse_days()
    * def parse_hours()
    * def parse_rooms()
    * def build_slots()
- `src/boun_scrape/storage/__init__.py` (221 B)
- `src/boun_scrape/storage/database.py` (4042 B)
    * class DatabaseManager (__init__, get_connection, connection, transaction, init_db)
- `src/boun_scrape/storage/repository.py` (19307 B)
    * def _row_to_course()
    * def _row_to_slot()
    * class CourseRepository (__init__, save_departments, save_courses_and_slots, get_courses, get_courses_by_term...)
- `tests/__init__.py` (34 B)
- `tests/fixtures/sample_quota.html` (1051 B)
- `tests/fixtures/sample_schedule.html` (3233 B)
- `tests/fixtures/sample_semester.html` (26220 B)
- `tests/test_api.py` (21780 B)
    * def test_settings()
    * def seeded_repo()
    * def mock_quota_service()
    * def mock_scheduler()
    * def test_log_buffer()
    * def async_client()
- `tests/test_api_auth_enforcement.py` (3393 B)
    * def app()
    * def test_scraper_routes_require_auth()
    * def test_quota_routes_require_auth()
    * def test_login_rate_limited_after_repeated_failures()
    * def test_auth_me_requires_auth()
    * def test_login_and_me_round_trip()
- `tests/test_auth.py` (2899 B)
    * class TestVerifyPassword (test_correct_bcrypt_password_verifies, test_incorrect_password_rejected, test_literal_admin_hash_is_not_a_backdoor, test_default_admin_hash_sentinel_is_not_a_backdoor, test_plaintext_equal_to_hash_is_rejected...)
    * class TestJwt (test_round_trip, test_wrong_secret_rejected, test_tampered_alg_header_rejected, test_malformed_token_rejected)
- `tests/test_cli.py` (9385 B)
    * def _strip_ansi()
    * def temp_db()
    * class TestCliApp (test_cli_help, test_scrape_help, test_scrape_command_success, test_serve_command, test_daemon_help...)
- `tests/test_client_and_flow.py` (10193 B)
    * class TestCookieParsing (test_parse_netscape_format, test_parse_key_value_string, test_parse_cookie_file)
    * class TestScraperClient (test_client_windows_1254_decoding, test_client_recaptcha_detection, test_client_retries_on_500_server_error, test_client_fails_when_retries_exhausted)
    * class TestScraperFlow (test_discover_terms, test_fetch_departments, test_fetch_department_schedule, test_scrape_term_pipeline)
- `tests/test_config.py` (3921 B)
    * class TestConfig (test_default_settings, test_env_override, test_dokploy_unprefixed_env_override, test_get_settings_singleton, test_dev_default_generates_ephemeral_secrets...)
- `tests/test_delta.py` (6727 B)
    * def _make_sample_course()
    * class TestDeltaEngine (test_course_hash_deterministic, test_course_hash_slot_order_invariant, test_course_hash_detects_changes, test_delta_added_courses, test_delta_removed_courses...)
- `tests/test_domain.py` (5078 B)
    * class TestDomainModels (test_department_model, test_course_and_slot_model, test_course_full_code_without_section, test_quota_record_model, test_scrape_snapshot_and_summary)
    * class TestDomainEvents (test_course_delta_event, test_scrape_event)
    * class TestDTOValidation (test_course_dto_serialization, test_paginated_response_dto, test_filter_params_validation)
- `tests/test_exporter.py` (9134 B)
    * def sample_courses()
    * def sample_deltas()
    * class TestExportJson (test_export_courses_json, test_export_courses_json_empty)
    * class TestExportCsv (test_export_courses_csv_headers_and_flattening)
    * class TestExportSqlite (test_export_courses_sqlite, test_export_courses_sqlite_overwrite)
    * class TestExportDeltas (test_export_deltas_json)
- `tests/test_parser.py` (9500 B)
    * def semester_html()
    * def schedule_html()
    * def quota_html()
    * class TestViewStateAndSemesters (test_extract_from_sample_semester, test_extract_empty_html)
    * class TestParseDepartments (test_parse_from_sample_semester, test_parse_departments_empty)
    * class TestParseSchedules (test_parse_schedule_full, test_parse_schedule_empty, test_parse_schedule_edge_cases)
- `tests/test_quota_service.py` (7034 B)
    * def quota_html()
    * class TestCourseKeyFormatter (test_format_course_key_standard, test_format_course_key_with_full_code, test_format_course_key_no_section)
    * class TestQuotaService (test_fetch_quota_success, test_fetch_quota_caching_and_bypass, test_fetch_quota_ttl_expiration, test_fetch_batch_quotas, test_fetch_batch_quotas_empty...)
- `tests/test_repository.py` (7881 B)
    * def repo()
    * class TestRepository (test_save_and_get_departments, test_save_courses_and_get_courses_with_filters, test_get_course_by_id, test_get_terms, test_scrape_runs_persistence...)
- `tests/test_resilience_edge_cases.py` (12936 B)
    * class TestMalformedHtmlResilience (test_empty_and_whitespace_html, test_truncated_and_unclosed_tags_in_schedule, test_schedule_with_broken_continuation_row, test_quota_with_missing_columns, test_html_without_tables)
    * class TestTurkishWindows1254Encoding (test_windows_1254_decoding_roundtrip, test_department_parsing_with_turkish_characters, test_schedules_with_turkish_instructor_and_course_name)
    * class TestDoubleDigitPeriodsAndIrregularDays (test_hours_partition_10_to_14, test_irregular_day_combinations, test_rooms_broadcasting_and_newlines, test_build_slots_full_integration)
    * class TestNonStandardQuotaStrings (test_closed_consent_quota, test_unlimited_quota, test_zero_capacity_slot, test_overenrolled_negative_availability, test_non_numeric_quota_strings)
    * class TestConcurrencyAndThreadSafety (test_concurrent_sqlite_writes_and_reads, test_concurrent_quota_cache_access, test_course_key_formatting_edge_cases)
- `tests/test_scheduler.py` (14664 B)
    * def semester_html()
    * def schedule_html()
    * class TestScrapeScheduler (test_scheduler_init_and_status, test_execute_scrape_cycle_full_flow, test_execute_scrape_cycle_emits_telemetry_logs_and_progress, test_execute_scrape_cycle_non_overlapping_guard, test_execute_scrape_cycle_error_handling...)
- `tests/test_slot_tokenizer.py` (6588 B)
    * class TestParseDays (test_single_letter_days, test_two_letter_lookahead_days, test_tba_and_whitespace, test_empty_and_none)
    * class TestParseHours (test_single_digit_hours, test_two_digit_algebraic_partition, test_single_digit_period_one_before_two_digit_period, test_space_separated_tokens, test_tba_and_empty...)
    * class TestParseRooms (test_single_room_replication, test_delimited_rooms, test_padding_and_slicing, test_entities_and_empty, test_zero_or_negative_slots)
    * class TestBuildSlots (test_standard_3_slot_course, test_two_digit_hours_with_multiple_rooms, test_tba_course, test_empty_day_returns_empty)
- `tests/test_webhooks.py` (9382 B)
    * def sample_delta()
    * def sample_summary()
    * class TestWebhookPayloadAndHmac (test_compute_hmac_signature, test_serialize_course_delta_event, test_serialize_scrape_run_summary)
    * class TestWebhookDispatcher (test_dispatch_with_hmac_signature, test_dispatch_without_secret, test_dispatch_retry_backoff_on_failure, test_dispatch_permanent_failure, test_dispatch_multiple_urls_concurrently...)
- `uv.lock` (78146 B)