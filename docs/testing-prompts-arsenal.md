# Testing Prompts Arsenal
# 30 Best Prompts: 15 Penetration Testing + 15 Performance Testing
# Curated from: TakSec, OWASP-AI-Security-Prompts, copyleftdev/ai-testing-prompts,
# VoltAgent pentester subagent, Semgrep/Claude security workflows, Promptfoo red team
# Updated: 2026-02-17

---

## SECTION A: PENETRATION TESTING PROMPTS (15)

### PT-01: Full OWASP Code Audit
```
Act as an expert application security engineer specializing in OWASP Top 10:2021.
Review the following code for ALL categories (A01-A10): Broken Access Control,
Cryptographic Failures, Injection, Insecure Design, Security Misconfiguration,
Vulnerable Components, Auth Failures, Data Integrity Failures, Logging Failures, SSRF.
For each finding: severity (Critical/High/Medium/Low), exact line number, vulnerable
code snippet, exploitation scenario, and concrete fix with code. Prioritize by
exploitability.

Code to review:
<paste code>
```

### PT-02: HTTP Request Attack Surface Analysis
```
Analyze this HTTP request captured from Burp Suite. Identify every possible attack
vector: injection points (SQL, NoSQL, command, LDAP, XPath), authentication weaknesses,
session handling flaws, IDOR opportunities, race conditions, and parameter pollution.
For each finding, provide a specific proof-of-concept request that demonstrates the
vulnerability. Format as a pentest report with severity ratings.

HTTP Request:
<paste request>
```

### PT-03: JavaScript Source Code Vulnerability Mining
```
Parse this JavaScript for: hardcoded secrets (API keys, tokens, passwords), XSS sinks
and sources, open redirects, prototype pollution, DOM clobbering, postMessage
vulnerabilities, insecure localStorage/sessionStorage usage, eval() or Function()
calls, and all file paths/API endpoints referenced. Be specific with line numbers.
Provide a working PoC exploit for each finding.

<paste JavaScript>
```

### PT-04: Authentication & Session Bypass
```
Given this authentication implementation, identify all possible bypass techniques:
credential stuffing vectors, brute force feasibility, session fixation, token
prediction, JWT manipulation (algorithm confusion, none algorithm, key confusion),
OAuth/OIDC misconfigurations, password reset poisoning, account enumeration via
timing/response differences, and 2FA bypass methods. Provide step-by-step
exploitation for each.

Auth code:
<paste code>
```

### PT-05: API Endpoint Security Assessment
```
Perform a comprehensive security assessment of this API endpoint. Check for:
BOLA/IDOR (manipulate IDs to access other users' data), broken function-level
auth (access admin endpoints as regular user), mass assignment (send extra fields
the server shouldn't accept), rate limiting gaps, injection in all parameters,
improper error handling leaking stack traces, missing security headers, and
SSRF via URL parameters. Generate curl commands for each test case.

API endpoint specification:
<paste API docs or code>
```

### PT-06: SQL/NoSQL Injection Deep Dive
```
Analyze this database interaction code for injection vulnerabilities. Test for:
classic SQL injection, blind SQL injection (boolean and time-based), second-order
injection, stored procedures injection, NoSQL operator injection ($gt, $ne, $regex),
ORM bypass techniques, and union-based data extraction. For each finding, provide
the exact malicious input string, the resulting query, and what data an attacker
could extract. Include both manual payloads and sqlmap/nosqlmap commands.

Database code:
<paste code>
```

### PT-07: Infrastructure & Configuration Audit
```
Review this server/application configuration for security misconfigurations:
default credentials, unnecessary services/ports, verbose error messages, directory
listing, missing security headers (CSP, HSTS, X-Frame-Options, X-Content-Type),
weak TLS configuration, exposed admin panels, debug mode in production, CORS
misconfigurations, and missing rate limiting. Provide the exact configuration
fixes with before/after examples.

Configuration:
<paste config files>
```

### PT-08: Supply Chain & Dependency Vulnerability Assessment
```
Audit these project dependencies for: known CVEs (check against NVD), outdated
packages with security patches available, typosquatting risks, packages with
suspicious maintainer changes, transitive dependency vulnerabilities, license
compliance issues, and packages that have been deprecated or abandoned. For each
finding, provide the CVE ID, severity score, affected version range, and the
minimum safe version to upgrade to.

Dependencies:
<paste requirements.txt / package.json / Cargo.toml>
```

### PT-09: File Upload & Path Traversal Exploitation
```
Analyze this file upload/download implementation for: unrestricted file type
uploads, path traversal (../ in filenames), null byte injection, double extension
bypass, MIME type mismatch exploitation, zip slip vulnerability, symlink attacks,
server-side file inclusion via uploaded files, and storage location security.
Provide specific filenames and payloads that bypass each protection. Include both
the attack and the proper fix.

File handling code:
<paste code>
```

### PT-10: XSS Payload Generation & WAF Bypass
```
Given this input reflection context (HTML attribute / JavaScript string / URL
parameter / CSS context / SVG), generate 15 XSS payloads that:
1. Don't use the word "alert" or "script" intact
2. Bypass common WAF rules (Cloudflare, ModSecurity, AWS WAF)
3. Work across Chrome, Firefox, Safari
4. Include DOM-based, reflected, and stored variants
5. Use encoding tricks (HTML entities, URL encoding, Unicode, JSFuck)
For each payload, explain why it bypasses the specific filter and which
browsers it works on.

Reflection context:
<paste vulnerable code showing where input is reflected>
```

### PT-11: Privilege Escalation Mapping
```
Given this application's role/permission model, map every possible privilege
escalation path: vertical escalation (user to admin), horizontal escalation
(user A accessing user B's data), and diagonal escalation (combining both).
Check for: missing authorization on endpoints, IDOR in resource access, role
parameter manipulation, JWT claim tampering, forced browsing to admin routes,
GraphQL introspection abuse, and API versioning exploits (v1 lacks auth that
v2 has). Provide the exact HTTP requests for each escalation.

Role model:
<paste role/permission code or docs>
```

### PT-12: Cryptographic Implementation Review
```
Review this cryptographic implementation for: weak algorithms (MD5, SHA1, DES,
RC4), insufficient key lengths, hardcoded keys/IVs, ECB mode usage, missing
HMAC on encrypted data, timing side-channels in comparisons, predictable
random number generation, improper certificate validation, key derivation
without proper salt/iterations (PBKDF2 < 600K, bcrypt < 12 rounds), and
nonce/IV reuse. For each finding, explain the exact attack (e.g., padding
oracle, birthday attack) and provide the secure alternative with code.

Crypto code:
<paste code>
```

### PT-13: Server-Side Request Forgery (SSRF) Exploitation
```
Analyze this code for SSRF vectors. Test for: direct SSRF via URL parameters,
blind SSRF via webhook/callback URLs, SSRF through file imports (PDF, SVG,
image processing), DNS rebinding attacks, IP address bypass techniques
(decimal, octal, hex, IPv6, 0.0.0.0, localhost aliases), cloud metadata
endpoint access (169.254.169.254, metadata.google.internal), internal port
scanning, and protocol smuggling (gopher://, dict://, file://). Provide
specific URLs and payloads for each vector.

Code:
<paste code handling URLs or external resources>
```

### PT-14: Race Condition & Business Logic Exploitation
```
Analyze this transaction/workflow code for race conditions and business logic
flaws: TOCTOU vulnerabilities, double-spend in payment processing, coupon/discount
code reuse, inventory manipulation (buy more than available), concurrent account
modification, parallel request exploitation, and sequence bypass (skip required
steps). For each finding, provide a PoC using parallel curl requests or a Python
script using asyncio/threading that demonstrates the race window.

Business logic code:
<paste code>
```

### PT-15: Comprehensive Red Team Report Generator
```
Given the following application description and architecture, generate a complete
red team assessment plan with: threat model (STRIDE per component), attack tree
for the 5 highest-impact scenarios, specific test cases for each attack path,
required tools and commands, expected evidence of compromise, lateral movement
opportunities post-compromise, data exfiltration scenarios, persistence mechanisms,
and detection gaps. Format as a professional pentest report with executive summary,
technical findings (CVSS scored), and prioritized remediation roadmap.

Application:
<paste architecture docs or description>
```

---

## SECTION B: PERFORMANCE TESTING PROMPTS (15)

### PF-01: Load Test Script Generator
```
Generate a complete load test script for this API endpoint using [locust/k6/artillery].
Include: gradual ramp-up (10 to 500 concurrent users over 10 minutes), sustained
peak load (500 users for 15 minutes), graceful ramp-down, realistic think times
between requests, parameterized test data (random usernames, varied payloads),
response time assertions (p95 < 500ms, p99 < 2s), error rate thresholds (< 1%),
and custom metrics collection. Output a single runnable file with comments.

Endpoint: <method> <url>
Headers: <headers>
Body: <sample payload>
Auth: <auth mechanism>
```

### PF-02: Performance Bottleneck Analysis
```
Analyze this code for performance bottlenecks. Check for: O(n^2) or worse
algorithms, N+1 query patterns, missing database indexes (based on query
patterns), unbounded memory growth, synchronous I/O in hot paths, missing
connection pooling, excessive object allocation in loops, string concatenation
in loops (use StringBuilder/join), missing caching opportunities, and
thread contention points. For each finding: quantify the impact at scale
(100 users, 1K users, 10K users), provide the optimized version, and
estimate the speedup factor.

Code to analyze:
<paste code>
```

### PF-03: Database Query Performance Audit
```
Analyze these database queries for performance issues. For each query:
1. Explain the execution plan (will it table scan or use index?)
2. Identify missing indexes and provide CREATE INDEX statements
3. Flag N+1 patterns and provide the JOIN-based alternative
4. Identify unnecessary columns in SELECT (replace * with specifics)
5. Check for implicit type conversions preventing index usage
6. Suggest query rewrites that reduce I/O
7. Estimate row counts at each step of the plan
8. Identify lock contention risks under concurrent access

Queries:
<paste SQL queries>

Schema:
<paste table definitions>
```

### PF-04: Memory Leak Detection
```
Review this code for memory leaks and excessive memory usage. Check for:
unclosed resources (file handles, DB connections, HTTP clients), event listener
accumulation, growing caches without eviction, circular references preventing
GC, large objects held in closures, buffer pools that never shrink, global
state accumulation over time, and thread-local variables never cleaned up.
For each finding: describe the leak mechanism, estimate memory growth rate
per hour under typical load, and provide the fix. Include a test that would
detect the leak using [valgrind/heaptrack/memory_profiler].

Code:
<paste code>
```

### PF-05: Concurrency & Thread Safety Stress Test
```
Design a stress test plan for this concurrent code. Generate test scenarios for:
1. Maximum throughput: How many ops/sec before degradation?
2. Lock contention: Which locks become bottlenecks first?
3. Deadlock detection: Exercise all lock ordering paths
4. Race conditions: Concurrent read-write on shared state
5. Thread pool exhaustion: What happens when all threads are busy?
6. Async queue backpressure: What happens when producers outpace consumers?
For each scenario: provide the test code, expected behavior, failure indicators,
and monitoring commands to observe the issue in real-time.

Concurrent code:
<paste code>
```

### PF-06: API Response Time Profiling
```
Given this API endpoint implementation, break down where time is spent:
1. Network/serialization overhead
2. Authentication/authorization checks
3. Input validation
4. Database queries (list each with estimated ms)
5. External service calls (list each with timeout config)
6. Business logic computation
7. Response serialization
For each phase: estimate the time range (best/typical/worst case), identify
which phases can be parallelized, suggest caching strategies with TTL
recommendations, and provide instrumentation code to measure each phase
in production.

Endpoint code:
<paste full request handler>
```

### PF-07: Frontend Performance Audit
```
Analyze this web application for frontend performance issues. Check:
1. Bundle size analysis: identify largest imports, tree-shaking opportunities
2. Render-blocking resources: CSS/JS blocking first paint
3. Image optimization: format, compression, lazy loading, srcset
4. Layout shifts: elements causing CLS > 0.1
5. JavaScript execution: long tasks > 50ms, main thread blocking
6. Network waterfall: unnecessary sequential requests, missing preload/prefetch
7. Caching strategy: Cache-Control headers, service worker, CDN config
8. Web Vitals estimates: LCP, FID/INP, CLS
Provide specific fixes with expected impact on each Core Web Vital metric.

<paste HTML/JS/CSS or URL>
```

### PF-08: Capacity Planning & Scaling Analysis
```
Given this application architecture and current metrics, create a capacity
planning model:
1. Current baseline: requests/sec, response time, CPU/memory per instance
2. Identify the scaling bottleneck (DB? App server? External API? Network?)
3. Calculate: at what traffic level does each component saturate?
4. Horizontal vs vertical scaling analysis for each component
5. Cost projection: infrastructure cost at 2x, 5x, 10x current traffic
6. Auto-scaling policy recommendations (thresholds, cooldowns, limits)
7. Database scaling strategy (read replicas, sharding, connection pooling)
8. Caching layer sizing (Redis/Memcached memory requirements at each scale)

Architecture:
<paste architecture diagram or description>
Current metrics:
<paste monitoring data>
```

### PF-09: Chaos Engineering Test Plan
```
Design a chaos engineering test plan for this system. For each experiment:
1. Steady state hypothesis (what "normal" looks like in metrics)
2. Experiment: what failure to inject (network partition, CPU spike, disk full,
   dependency timeout, DNS failure, certificate expiry, clock skew)
3. Expected system behavior (graceful degradation, failover, circuit break)
4. Abort conditions (when to stop the experiment)
5. Monitoring: which dashboards/alerts to watch
6. Blast radius containment (how to limit impact)
7. Rollback procedure
Generate the actual fault injection commands (tc netem, stress-ng, toxiproxy,
kill -STOP, iptables) for each experiment.

System architecture:
<paste architecture>
```

### PF-10: Real-Time Audio/Video Processing Benchmark
```
Design a performance benchmark for this real-time media processing pipeline.
Test for:
1. Latency: measure end-to-end processing time per frame/buffer
   - Target: < 10ms for audio (at 44.1kHz/512 buffer), < 33ms for video (30fps)
2. Throughput: maximum concurrent streams before dropping frames
3. CPU usage: per-effect/per-stage breakdown, SIMD utilization
4. Memory stability: confirm zero allocation in audio callback / render loop
5. Buffer underrun frequency under sustained load
6. Graceful degradation: quality vs latency tradeoff under overload
7. Platform variance: test on target hardware (M1/M2/Intel, GPU vs CPU)
Provide the benchmarking harness code with nanosecond-precision timing,
statistical analysis (mean, p50, p95, p99, jitter), and pass/fail criteria.

Pipeline code:
<paste processing code>
```

### PF-11: Network Performance & Resilience Test
```
Design a network performance test suite for this distributed system:
1. Latency sensitivity: response quality at 50ms, 100ms, 500ms, 1s, 5s RTT
2. Bandwidth constraints: behavior at 1Mbps, 10Mbps, 100Mbps
3. Packet loss: behavior at 0.1%, 1%, 5%, 10% loss rates
4. Connection limits: max concurrent connections before rejection
5. Reconnection behavior: time to recover after network interruption
6. DNS resolution failure: fallback behavior
7. TLS handshake overhead: connection reuse effectiveness
8. Compression effectiveness: payload size reduction and CPU tradeoff
Generate tc netem commands for each scenario and provide a monitoring script
that captures metrics during each test.

System endpoints:
<paste endpoints and expected traffic patterns>
```

### PF-12: Startup & Cold Start Optimization
```
Profile this application's startup sequence and identify optimization
opportunities:
1. Dependency loading order and time per module
2. Configuration parsing and validation time
3. Database connection pool initialization
4. Cache warming requirements and time
5. Health check readiness timeline
6. First-request latency vs steady-state latency
7. Lazy loading opportunities (what can be deferred?)
8. Parallel initialization opportunities (what's independent?)
Target: reduce cold start from current to under [X] seconds.
Provide the optimized initialization code and measurement instrumentation.

Startup code:
<paste application entry point and initialization>
```

### PF-13: Resource Exhaustion Testing
```
Design tests to find resource exhaustion vulnerabilities in this application:
1. Memory: send requests that maximize server memory (large payloads,
   many parameters, deeply nested JSON, zip bombs)
2. CPU: craft inputs that trigger worst-case algorithm complexity
   (regex catastrophic backtracking, hash collision, sort adversarial input)
3. Disk: log flooding, temp file accumulation, upload storage
4. File descriptors: connection exhaustion, unclosed handles
5. Thread/goroutine: unbounded spawning from user input
6. Database connections: pool exhaustion via slow queries
For each: provide the exact malicious input, expected system behavior with
and without protection, and the defensive fix (timeouts, limits, circuit
breakers). This is for authorized defensive testing.

Application code:
<paste code>
```

### PF-14: Caching Strategy Validation
```
Audit this application's caching implementation for:
1. Cache hit ratio estimation: what % of requests can be served from cache?
2. Cache invalidation correctness: stale data scenarios
3. Thundering herd: what happens when a popular cache key expires?
4. Cache poisoning: can an attacker influence cached responses?
5. Memory sizing: is the cache sized correctly for the working set?
6. Eviction policy: is LRU/LFU/TTL appropriate for this access pattern?
7. Cold cache performance: first-request experience after restart
8. Multi-layer caching: CDN + application + database query cache coherence
For each issue: quantify the performance impact and provide the fix.
Include a cache simulation script that models hit rates with different
configurations.

Caching code:
<paste code>
```

### PF-15: End-to-End Performance Regression Test Suite
```
Generate a complete performance regression test suite for this application
that runs in CI/CD. Requirements:
1. Baseline capture: record p50/p95/p99 latency, throughput, error rate
   for each critical endpoint
2. Comparison logic: fail if any metric degrades > 10% from baseline
3. Test data management: deterministic seed data, cleanup after run
4. Isolated environment: no shared state between test runs
5. Reports: generate HTML report with charts comparing current vs baseline
6. History: store results for trend analysis over last 30 builds
7. Alerting: flag gradual degradation (< threshold per build but trending up)
Output: complete CI pipeline config (GitHub Actions), test scripts,
baseline storage format, and comparison logic.

Application endpoints:
<paste critical paths to monitor>
Current baseline metrics:
<paste if available>
```

### PF-16: Electron Desktop App E2E Test Suite
```
Design a complete E2E test suite for this Electron desktop application using
Playwright's _electron API. Cover:
1. App launch and window creation (electron.launch → firstWindow)
2. Main process API access (electronApp.evaluate for app.getAppPath, etc.)
3. Renderer DOM interactions (click, type, assert on UI elements)
4. IPC communication between main and renderer processes
5. Multi-window scenarios (dialog boxes, settings panels, secondary windows)
6. Menu bar and system tray interactions
7. File system operations (open/save dialogs, drag-and-drop)
8. Application lifecycle (minimize, maximize, close, force quit)
9. Security context (nodeIntegration, contextIsolation, CSP compliance)
10. Platform-specific behavior (macOS menu bar, Windows taskbar)
Include test.setTimeout configuration, console routing to Node terminal,
screenshot capture for visual regression, and video recording setup.
Target: Electron v12+, Playwright experimental _electron API.

Application code/structure:
<paste Electron app code or package.json + main process file>
```

### PF-17: Python Sidecar + ZMQ IPC Communication Test
```
Design a test suite for an Electron app with a Python sidecar communicating
over ZeroMQ. Cover:
1. Sidecar startup: Python process launches, binds ZMQ socket, responds to PING
2. Command protocol: REQ/REP message format validation, JSON schema compliance
3. Heartbeat/watchdog: miss counting, restart trigger after N misses, state recovery
4. Shared memory (mmap): ring buffer read/write, zero-copy frame transport,
   latency measurement (target: <0.1ms for mmap, <16ms for full pipeline)
5. Effect processing: pure function contract, deterministic output with seed,
   no global state mutation, parameter boundary testing (min/max/zero)
6. Error handling: malformed commands, Python exception propagation to frontend,
   graceful degradation on sidecar crash
7. Compiled binary parity: Nuitka-compiled binary produces identical output
   to Python source (hash frame output for comparison)
8. Concurrent processing: multiple effect requests queued, ordering preserved
9. Memory stability: process 1000 frames, verify no memory growth (RSS tracking)
10. Graceful shutdown: SHUTDOWN command → cleanup → process exit code 0
Include pytest fixtures for ZMQ socket setup/teardown, frame generation helpers,
and timing measurement decorators.

Sidecar code:
<paste Python sidecar + ZMQ server code>
```

---

## Usage Guide

### For /cto skill:
- Use PT-01 through PT-15 when reviewing code security
- Use PF-01 through PF-15 when reviewing performance

### For /qa-redteam skill:
- PT-01 (OWASP audit) is the default starting prompt
- PT-15 (red team report) for comprehensive assessments
- PT-10 (XSS) + PT-06 (injection) for web apps
- PT-14 (race conditions) for transaction-heavy code

### For /quality skill:
- PF-02 (bottleneck analysis) during pre-ship review
- PF-15 (regression suite) for CI/CD setup
- PF-10 (audio/video benchmark) for Entropic/Cymatics
- PF-16 (Electron E2E) for Entropic v2 Challenger desktop app
- PF-17 (Python sidecar/ZMQ) for Entropic v2 Challenger IPC testing

### For /test-electron command:
- PF-16 (Electron E2E) — primary prompt for desktop app testing
- PF-17 (Python sidecar/ZMQ) — IPC and sidecar communication testing
- PF-10 (audio/video benchmark) — frame processing latency validation
- PF-12 (startup optimization) — Electron cold start profiling

### For /ship skill:
- PF-07 (frontend audit) before deploying web apps
- PF-12 (startup optimization) for new services
- PF-15 (regression suite) to prevent performance regressions

---

## Sources

- [TakSec/chatgpt-prompts-bug-bounty](https://github.com/TakSec/chatgpt-prompts-bug-bounty)
- [OWASP-AI-Security-Prompts](https://github.com/Alexanderdunlop/OWASP-AI-Security-Prompts)
- [copyleftdev/ai-testing-prompts](https://github.com/copyleftdev/ai-testing-prompts)
- [VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents)
- [Semgrep: Finding vulnerabilities with Claude Code](https://semgrep.dev/blog/2025/finding-vulnerabilities-in-modern-web-apps-using-claude-code-and-openai-codex/)
- [Promptfoo: Red Team Claude](https://www.promptfoo.dev/blog/red-team-claude/)
- [agamm/claude-code-owasp](https://github.com/agamm/claude-code-owasp)
- [PFLB: AI Load Testing Tools](https://pflb.us/blog/top-ai-load-testing-tools/)
- [TestGrid: Performance Testing Tools](https://testgrid.io/blog/performance-testing-tools/)
