# Dashboard V2 — Test Documentation

**File:** `~/Development/tools/test_dashboard_v2.py`
**Dashboard:** `~/Development/tools/dashboard_v2.py`
**Tests:** 83 | **Passing:** 83 | **Runtime:** ~1.6s
**Command:** `python3 -m pytest test_dashboard_v2.py -v`
**Last Updated:** 2026-02-07

---

## How to Run

```bash
# Full test suite with verbose output
cd ~/Development/tools
python3 -m pytest test_dashboard_v2.py -v

# Run a specific test category
python3 -m pytest test_dashboard_v2.py -v -k "TestPerformance"

# Run a single test
python3 -m pytest test_dashboard_v2.py -v -k "test_memory_no_leak_100_cycles"
```

---

## Test Categories (7 Classes, 83 Tests)

### 1. TestDataLoaderStress (12 tests)
Tests data loaders with missing, corrupt, huge, and adversarial input files.

| # | Test | What It Verifies |
|---|------|-----------------|
| 1 | `test_missing_resource_tracker` | Returns safe default when tracker file doesn't exist |
| 2 | `test_empty_resource_tracker` | Returns safe default on empty JSON file |
| 3 | `test_corrupt_json_resource_tracker` | Returns safe default on invalid JSON |
| 4 | `test_binary_garbage_resource_tracker_BUG` | **FIXED BUG**: UnicodeDecodeError on binary data now caught |
| 5 | `test_zero_byte_active_tasks` | Empty task file returns empty list |
| 6 | `test_huge_active_tasks_10mb` | 10MB file rejected by size guard (<1MB limit) |
| 7 | `test_10000_tasks` | 10,000 task lines parsed without crash |
| 8 | `test_rich_markup_injection_in_task_names` | Rich markup in task names escaped (no injection) |
| 9 | `test_special_chars_in_task_names` | Unicode, emoji, brackets handled safely |
| 10 | `test_kb_counting_with_empty_directories` | Empty KB dirs return 0 count |
| 11 | `test_kb_counting_with_mixed_file_types` | Only .md files counted |
| 12 | `test_circular_symlink_in_kb_directory` | Circular symlinks don't crash or hang |

### 2. TestPerformance (6 tests)
Timing, caching, and memory leak detection.

| # | Test | What It Verifies |
|---|------|-----------------|
| 1 | `test_load_tracker_data_under_1s` | Tracker data loads in <1s |
| 2 | `test_parse_active_tasks_under_1s` | Task parsing completes in <1s |
| 3 | `test_get_usage_stats_under_1s` | Usage calculation completes in <1s |
| 4 | `test_cache_faster_than_uncached` | Cached reads are faster than uncached |
| 5 | `test_memory_no_leak_100_cycles` | 100 render cycles stay under 50MB growth (tracemalloc) |
| 6 | `test_generate_layout_under_2s` | Full layout generation completes in <2s |

### 3. TestCrashResistance (21 tests)
Every render function tested with None, empty, garbage, and extreme inputs.

| # | Test | What It Verifies |
|---|------|-----------------|
| 1 | `test_render_kb_panel_empty_stats` | Empty stats dict renders without crash |
| 2 | `test_render_kb_panel_single_entry` | Single KB entry renders correctly |
| 3 | `test_render_kb_panel_with_zero_count_entry_BUG` | **FIXED BUG**: All-zero counts no longer cause ZeroDivisionError |
| 4 | `test_render_usage_panel_huge_numbers` | 999,999 responses render without overflow |
| 5 | `test_render_usage_panel_negative_numbers` | Negative values handled gracefully |
| 6 | `test_render_usage_panel_zero_limits` | Zero limits don't cause division by zero |
| 7 | `test_render_sessions_panel_corrupt_data_BUG` | **FIXED BUG**: Mixed types in sort no longer crash |
| 8 | `test_render_sessions_panel_all_valid_data` | Valid data renders correctly (baseline) |
| 9 | `test_render_sessions_panel_no_sessions_key` | Missing sessions key returns empty table |
| 10 | `test_render_task_panel_none_tasks` | None/empty task list shows placeholder |
| 11 | `test_render_task_panel_garbage_task_data_BUG` | **FIXED BUG**: Missing status key no longer crashes |
| 12 | `test_render_next_action_panel_with_none_inputs` | Empty warnings list handled |
| 13 | `test_render_next_action_panel_many_warnings` | 50 warnings truncated to 2 displayed |
| 14 | `test_render_jobs_panel_empty` | No jobs shows "None running" |
| 15 | `test_render_jobs_panel_many_completed` | 20 completed jobs truncated to 5 |
| 16 | `test_render_system_panel_missing_keys` | Missing memory keys use "N/A" |
| 17 | `test_render_system_panel_bad_disk_pct` | Non-numeric disk percent handled |
| 18 | `test_parse_active_tasks_missing_file` | Missing file returns empty list |
| 19 | `test_parse_active_tasks_permission_denied` | Permission error returns empty list |
| 20 | `test_validate_kb_counts_empty_stats` | Empty stats validation passes |
| 21 | `test_validate_kb_counts_mismatched_stats` | Mismatched stats generate warnings |
| 22 | `test_get_usage_stats_empty_daily` | Empty daily data returns zeros |
| 23 | `test_get_usage_stats_bad_date_keys` | Malformed date keys skipped |
| 24 | `test_get_environmental_impact_zero` | Zero responses = zero impact |
| 25 | `test_get_environmental_impact_maxint` | Huge response count doesn't overflow |
| 26 | `test_get_environmental_impact_negative` | Negative values handled |
| 27 | `test_get_next_action_empty_tasks` | No tasks = "add focus" suggestion |
| 28 | `test_get_next_action_all_done` | All done = "check roadmap" suggestion |
| 29 | `test_get_next_action_all_blocked` | All blocked = surfaces blocker |
| 30 | `test_get_next_action_wip_task` | WIP task = "continue" suggestion |

### 4. TestConcurrency (3 tests)
Thread safety for cache, error log, and full layout generation.

| # | Test | What It Verifies |
|---|------|-----------------|
| 1 | `test_concurrent_generate_layout` | 2 threads x 5 cycles of generate_layout() don't crash |
| 2 | `test_concurrent_cache_access` | 4 threads writing to cache simultaneously |
| 3 | `test_concurrent_error_log_writing` | 4 threads writing to error log with atomic writes |

**Note:** `safe_glob` uses SIGALRM (main-thread only). Concurrency test mocks `safe_glob` at module level to avoid `ValueError: signal only works in main thread`.

### 5. TestEdgeCases (22 tests)
Time boundaries, disk limits, service extremes, TTL behavior, and more.

| # | Test | What It Verifies |
|---|------|-----------------|
| 1 | `test_first_day_of_month` | Month calculations correct on day 1 |
| 2 | `test_monday_week_boundary` | Week calculations correct on Monday |
| 3 | `test_disk_at_99_percent` | 99% disk shows red color |
| 4 | `test_no_background_services` | Zero services shows "No services detected" |
| 5 | `test_50_background_services` | 50 services render without crash |
| 6 | `test_launchctl_timeout` | launchctl timeout returns empty list |
| 7 | `test_ps_aux_timeout` | ps aux timeout returns empty jobs |
| 8 | `test_error_log_truncation` | Error log capped at 100 entries |
| 9 | `test_error_log_corrupt_existing` | Corrupt existing log replaced cleanly |
| 10 | `test_get_error_summary_no_file` | Missing error log returns zero count |
| 11 | `test_get_error_summary_corrupt_file` | Corrupt error log returns zero count |
| 12 | `test_validate_usage_stale_tracker` | 48h-old tracker generates warning |
| 13 | `test_validate_usage_suspicious_count` | 10x daily limit triggers warning |
| 14 | `test_cached_function_respects_ttl` | Cache expires after TTL seconds |
| 15 | `test_safe_glob_returns_list_on_nonexistent_path` | Non-existent path returns [] |
| 16 | `test_system_memory_all_commands_fail` | All subprocess failures return "N/A" |
| 17 | `test_render_sessions_panel_timestamp_zero` | Epoch 0 timestamp shows "Old" |
| 18 | `test_render_sessions_panel_future_timestamp` | Future timestamp handled |
| 19 | `test_scraping_jobs_no_python_processes` | No python processes = no active jobs |
| 20 | `test_friday_footer_text` | Friday shows weekly review prompt |
| 21 | `test_validate_usage_no_tracker_file` | Missing tracker file generates warning |
| 22 | `test_render_usage_panel_with_warnings` | Usage warnings render in panel |

### 6. TestSignalSafety (4 tests)
SIGALRM handler lifecycle in `safe_glob`.

| # | Test | What It Verifies |
|---|------|-----------------|
| 1 | `test_safe_glob_restores_signal_handler` | Original SIGALRM handler restored after glob |
| 2 | `test_safe_glob_restores_handler_on_timeout` | Handler restored even after timeout exception |
| 3 | `test_safe_glob_cancels_alarm_on_success` | signal.alarm(0) called after successful glob |
| 4 | `test_safe_glob_does_not_mask_other_exceptions` | Non-glob exceptions propagate normally |

### 7. TestIntegrationSmoke (6 tests)
Full pipeline end-to-end tests.

| # | Test | What It Verifies |
|---|------|-----------------|
| 1 | `test_generate_layout_with_all_valid_data` | Full dashboard with mocked valid data |
| 2 | `test_generate_layout_with_nothing` | Dashboard renders with zero data |
| 3 | `test_generate_layout_with_kb_data` | KB stats populate correctly in layout |
| 4 | `test_main_loop_error_counting_logic` | Error counter increments on exception |
| 5 | `test_main_loop_resets_on_success` | Error counter resets on success |
| 6 | `test_full_pipeline_with_services_and_jobs` | All panels populate together |

---

## Bugs Found and Fixed

### Round 1 (Initial Reviews)

| Bug | Severity | Fix |
|-----|----------|-----|
| KB glob 3000+ files every 5s | HIGH (perf) | Cached with 60s TTL |
| Validation re-globbed same files | MEDIUM (perf) | Validate checks dir existence only |
| 6 subprocess calls every 5s uncached | MEDIUM (perf) | Cached: services 30s, memory 15s, jobs 10s |
| `max(stats.values())` crash on empty dict | HIGH (crash) | Guard: `max(...) if stats else 1` |
| Display overflow at 10,000+ responses | MEDIUM (UX) | Dynamic width formatting |
| Layout jumping between renders | LOW (UX) | Fixed `size=5` always |
| Division by zero in pct calculation | HIGH (crash) | Guard: `if DAILY_LIMIT else 0` |
| Glob DoS on crafted filesystem | HIGH (security) | `safe_glob()` with SIGALRM timeout |
| Main loop crash = no dashboard | HIGH (reliability) | Try/except per cycle, 5 retries |

### Round 2 (Deep Reviews)

| Bug | Severity | Fix |
|-----|----------|-----|
| Rich Markup Injection via task names | HIGH (security) | `rich_escape(task['name'])` |
| SIGALRM re-entrancy from external signal | MEDIUM (safety) | `_in_safe_glob` guard flag |
| Corrupted JSON from crash during write | MEDIUM (data) | Atomic writes: tempfile + os.replace |
| Large ACTIVE-TASKS.md memory exhaustion | MEDIUM (safety) | File size check (1MB limit) |
| Crafted resource tracker TypeError | LOW (crash) | `isinstance(daily, dict)` guard |
| safe_glob OSError on broken paths | LOW (crash) | Added OSError exception handling |

### Round 3 (Test Suite Discoveries)

| Bug | Severity | Fix |
|-----|----------|-----|
| Binary file corruption crashes tracker load | HIGH (crash) | Added UnicodeDecodeError to except |
| ZeroDivisionError on all-zero KB counts | MEDIUM (crash) | `max(..., default=1) or 1` |
| TypeError sorting sessions with mixed types | MEDIUM (crash) | Safe float coercion in sort key |
| KeyError on missing task status key | MEDIUM (crash) | `task.get("status", "???")` |
| TypeError in datetime.fromtimestamp on string | MEDIUM (crash) | Added TypeError to except clause |

### CTO Performance Fixes (Final Round)

| Fix | Impact |
|-----|--------|
| Cached `load_tracker_data` (10s TTL) | Eliminates file read every 5s |
| Cached `parse_active_tasks` (15s TTL) | Eliminates file parse every 5s |
| Cached `get_error_summary` (30s TTL) | Eliminates file read every 5s |
| PID lockfile at startup | Prevents dual-dashboard corruption |
| Subprocess timeouts reduced 5s -> 2s | Worst-case cycle: 55s -> ~31s |

---

## Test Fixtures

| Fixture | Scope | What It Does |
|---------|-------|-------------|
| `isolate_home` | function | Patches all 4 module-level Path constants + `Path.home()` to temp dir |
| `fake_tracker` | function | Writes valid tracker JSON to isolated home |
| `fake_tasks` | function | Writes valid ACTIVE-TASKS.md to isolated home |
| `clear_cache` | function (autouse) | Clears `_cache` and `_cache_ttl` before/after every test |

**Critical design note:** The dashboard resolves `RESOURCE_TRACKER`, `ACTIVE_TASKS`, `ERROR_LOG`, and `SCRAPING_QUEUE` at import time via `Path.home()`. The `isolate_home` fixture must monkeypatch ALL FOUR module-level constants directly, not just `Path.home()`.

---

## Security Measures

| Measure | Location | Protection |
|---------|----------|-----------|
| Rich markup escape | `render_task_panel` | Prevents markup injection via task names |
| SIGALRM glob timeout | `safe_glob` | Prevents glob DoS on crafted filesystems |
| Re-entrancy guard | `_glob_timeout_handler` | Ignores spurious SIGALRM signals |
| Atomic JSON writes | `log_error` | Prevents corruption on crash during write |
| File size guard | `_parse_active_tasks` | Rejects files >1MB to prevent OOM |
| Type guards | Multiple | Prevents TypeError/KeyError on corrupt data |
| PID lockfile | `main` | Prevents dual-instance data corruption |
| Subprocess list-form | All subprocess calls | No shell=True = no command injection |
| Error log cap | `log_error` | Capped at 100 entries (~30KB max) |

---

## Known Limitations

1. **SIGALRM is main-thread only**: `safe_glob` cannot be called from threads. If Rich's `Live()` refresh thread ever calls `generate_layout()` directly, it will raise `ValueError`. Current design is safe because `Live.update()` is called from the main thread.

2. **Cache is not thread-safe**: The `_cache` dict uses plain dict operations. This is acceptable because the dashboard is single-threaded by design.

3. **Error log reads are not cached during `log_error`**: Writing to error log reads the file first. Under heavy error conditions, this could be slow. Mitigated by the 100-entry cap.

---

## Related Files

| File | Purpose |
|------|---------|
| `dashboard_v2.py` | The dashboard itself (~980 lines) |
| `test_dashboard_v2.py` | This test suite (83 tests) |
| `DASHBOARD-V2-PRD.md` | Product requirements (in Obsidian) |
| `DASHBOARD-V2-TEST-DOCS.md` | This documentation |
| `dashboard_errors.json` | Runtime error log (~/.claude/.locks/) |
| `.resource-tracker.json` | Usage tracking data (~/.claude/.locks/) |
