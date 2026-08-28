# AGENTS.md

## Core Principles & Project Architecture

- **Public Surface Boundary**: All frontend and consumer access occurs strictly via typed `/api/v1/*` endpoints. Legacy `/api/*` is retired.
- **Authentication**: Bcrypt-only password verification (`verify_password`). Secrets fail-fast outside dev/test environments.
- **Data Integrity**: Department course replacement in `save_courses_and_slots` is scoped strictly to succeeded departments (`scraped_departments`) to prevent data loss on transient crawl failures.
- **Clean Lifespan Teardown**: FastAPI `lifespan` must gracefully clean up and await `cleanup_shared_resources()` on server SIGTERM / shutdown.
- **Zero Pollution / Minimal Diff**: Compute before reading whole files (>100 lines never). Use `mimori slice` and targeted edits.

---

## Surgical Testing Protocol

The full test suite (`uv run pytest`) contains 258+ tests and takes ~60s because integration tests simulating network retries and portal errors (`test_scheduler.py`) take ~37s.

**Always use surgical testing during development and single-function fixes**:

1. **Compute Lineage**: Run `mimori slice <path>[:<symbol>]` to identify the 1-hop Ancestor test modules.
2. **Execute Targeted Test**: Run the matching test file (~0.2s–2.4s) or exact test node (<0.3s).
3. **CI / Pre-Push**: The full regression test suite is run before pushing or creating pull requests.

### Subsystem → Test Matrix

| Subsystem Modified | Direct Surgical Target | Typical Runtime |
| :--- | :--- | :--- |
| **API Endpoints & Auth** (`src/boun_scrape/api/`) | `uv run pytest tests/test_api.py tests/test_api_auth_enforcement.py` | ~2.4s |
| **Domain Models & DTOs** (`src/boun_scrape/domain/`) | `uv run pytest tests/test_domain.py tests/test_delta.py` | ~0.3s |
| **HTML Parser & Tokens** (`src/boun_scrape/scraper/parser.py`) | `uv run pytest tests/test_parser.py tests/test_slot_tokenizer.py` | ~0.2s |
| **HTTP Client & Jitter** (`src/boun_scrape/scraper/client.py`) | `uv run pytest tests/test_client_and_flow.py` | ~1.8s |
| **Database & Repository** (`src/boun_scrape/storage/`) | `uv run pytest tests/test_repository.py` | ~0.9s |
| **Quota Service** (`src/boun_scrape/scraper/quota.py`) | `uv run pytest tests/test_quota_service.py` | ~0.5s |
| **Webhooks & Feeds** (`src/boun_scrape/feeds/webhooks.py`) | `uv run pytest tests/test_webhooks.py` | ~0.4s |
| **Config & Secrets** (`src/boun_scrape/config.py`) | `uv run pytest tests/test_config.py` | ~0.1s |
| **CLI Commands** (`src/boun_scrape/cli/`) | `uv run pytest tests/test_cli.py` | ~0.8s |

### Quick Targeting Commands

```bash
# Target single method
uv run pytest tests/test_api.py::TestApiEndpoints::test_scheduler_daemon_start_and_stop

# Target by keyword/topic
uv run pytest -k "daemon or cron"

# Re-run only previously failed tests
uv run pytest --lf

# Fast-fail on first error
uv run pytest -x tests/test_api.py
```
