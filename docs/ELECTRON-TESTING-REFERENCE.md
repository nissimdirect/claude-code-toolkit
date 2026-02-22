# Electron App Testing Reference

> Consolidated from 25+ sources, 2026-02-21.
> Primary use: Entropic v2 Challenger (Electron + React + Python + ZMQ + mmap).
> Referenced by: `/quality` §11, `/test-electron` command, SDLC Flywheel Phase 3.

---

## 1. The 3 Official Approaches

### A. Playwright _electron (RECOMMENDED)

**Why:** Best balance of power, maintenance, and Electron-specific features.
**Support:** Experimental but stable. Electron v12+. Supported versions: 12.2.0+, 13.4.0+, 14+.

```bash
npm install --save-dev @playwright/test
```

```typescript
import { test, expect, _electron as electron } from '@playwright/test';

let app, window;

test.beforeAll(async () => {
  app = await electron.launch({
    args: ['.'],
    timeout: 60000,
    recordVideo: { dir: 'test-results/videos' },
  });
  window = await app.firstWindow();
  window.on('console', msg => console.log(`[renderer] ${msg.text()}`));
});

test.afterAll(async () => {
  await app.close();
});

// Renderer tests (Chromium Page API)
test('window loads with title', async () => {
  await expect(window).toHaveTitle(/Entropic/);
});

test('main content visible', async () => {
  await expect(window.locator('#timeline')).toBeVisible();
});

// Main process tests
test('app path is correct', async () => {
  const appPath = await app.evaluate(async ({ app }) => app.getAppPath());
  expect(appPath).toContain('entropic');
});

test('app is not packaged in dev', async () => {
  const isPacked = await app.evaluate(async ({ app }) => app.isPackaged);
  expect(isPacked).toBe(false);
});

// Screenshots for regression
test('visual regression baseline', async () => {
  await window.screenshot({ path: 'test-results/main-window.png' });
});
```

**Key launch options:**

| Option | Type | Purpose |
|--------|------|---------|
| `args` | string[] | CLI args passed to Electron |
| `executablePath` | string | Custom Electron binary path |
| `cwd` | string | Working directory |
| `env` | Object | Environment variables |
| `timeout` | number | Max launch wait (default 30000ms) |
| `colorScheme` | string | "light", "dark", "no-preference" |
| `locale` | string | User locale (e.g., "en-US") |
| `offline` | boolean | Simulate offline |
| `recordVideo` | Object | `{ dir: 'path', size: { width, height } }` |
| `recordHar` | Object | Record network as HAR file |

### B. WebdriverIO wdio-electron-service

**Why:** Auto-configures Chromedriver, auto-detects app path, direct Electron API access.

```bash
npm create wdio@latest ./
# Select "Desktop Testing - of Electron Applications"
```

```typescript
// wdio.conf.ts
export const config = {
  services: [['electron', {
    appEntryPoint: './path/to/bundled/main.js',
    appArgs: ['--test-mode'],
  }]],
  capabilities: [{ browserName: 'electron' }],
};
```

**Unique features:**
- `browser.electron.execute()` — run arbitrary code in main process
- API mocking with Vitest-like interface
- Parallel multiremote support

### C. Custom Test Driver (child_process + IPC)

**Why:** Lowest overhead, maximum flexibility.
**When:** Custom testing needs, minimal dependencies.

```javascript
const { spawn } = require('child_process');
const electron = spawn('npx', ['electron', '.'], {
  stdio: ['pipe', 'pipe', 'pipe', 'ipc'],
});
electron.on('message', (msg) => { /* handle test results */ });
electron.send({ type: 'run-test', name: 'smoke' });
```

---

## 2. Entropic v2 Challenger Testing Stack

| Layer | Tool | Files |
|-------|------|-------|
| React UI units | Vitest | `frontend/tests/unit/**/*.test.ts` |
| Electron E2E | Playwright _electron | `frontend/tests/e2e/**/*.spec.ts` |
| Python sidecar units | pytest | `backend/tests/test_*.py` |
| ZMQ protocol | pytest + pyzmq | `backend/tests/test_zmq.py` |
| mmap transport | pytest + C extension | `backend/tests/test_mmap.py` |
| Effect contracts | pytest | `backend/tests/test_effects/*.py` |
| Cross-process integration | Playwright + pytest | `tests/integration/*.spec.ts` |
| Nuitka binary parity | pytest | `backend/tests/test_nuitka.py` |
| Visual regression | Playwright screenshots | `test-results/*.png` |

### Phase 0A Tests (Minimum Viable)

```
frontend/tests/e2e/
  app-launch.spec.ts        # Electron launches, window appears
  watchdog.spec.ts           # Python sidecar heartbeat, restart on 3 misses

backend/tests/
  test_zmq_server.py         # PING→PONG, unknown→error, SHUTDOWN→clean exit
  test_nuitka_smoke.py       # Compiled binary responds to PING
```

### Phase 0B Tests (Validation)

```
backend/tests/
  test_frame_transport.py    # mmap latency < 16ms, ring buffer correctness
  test_pyav_codec.py         # PyAV H.264 decode/encode roundtrip
  test_effect_container.py   # mask/mix pipeline, JSON schema validation
  test_determinism.py        # Hash(seed + effect + frame) = identical output
```

---

## 3. CI/CD Configuration

### GitHub Actions (macOS ARM64)

```yaml
name: Test
on: [push, pull_request]

jobs:
  test-frontend:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - run: npm ci
      - run: npx playwright install
      - run: npx playwright test
        timeout-minutes: 10
      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: test-results
          path: test-results/

  test-backend:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -e ".[test]"
      - run: python -m pytest backend/tests/ -v --tb=short
```

**Why macos-latest:** Electron needs a display environment. macOS runners have Quartz. Linux would need `xvfb-run`.

---

## 4. Critical Gotchas

1. **`_electron` is experimental** — underscore prefix signals this. API stable but may change.
2. **nodeCliInspect fuse must NOT be disabled** — Playwright uses it to attach.
3. **Kill background Electron processes** before test run: `pkill -f electron || true`
4. **Security settings for test mode** — use env var `CI=1` to enable `nodeIntegration` + disable `contextIsolation` in test builds only. Never in production.
5. **Timeout defaults** — 30s is too short for Electron launch. Use `test.setTimeout(60000)`.
6. **Video output is .webm** — convert: `ffmpeg -i file.webm file.mp4`
7. **Console routing** — renderer console.log is invisible without `window.on('console', ...)`.
8. **Spectron is deprecated** — was the old official tool, version-coupled, replaced by Playwright + WDIO.
9. **Nuitka binary path differs from source** — test both paths in CI.
10. **Port conflicts** — ZMQ sockets must use unique ports per test instance.

---

## 5. Vision-Based Agent Testing (Future)

For visual effects that DOM selectors can't reach (canvas rendering, WebGL, custom painters):

### AskUI Vision Agent
```python
from askui import VisionAgent

with VisionAgent() as agent:
    agent.act("Open Entropic, load a video, apply the wormhole effect")
    result = agent.get("Does the preview show the wormhole distortion?")
```

**When to use:** Testing visual correctness of effects, timeline interactions, canvas-based UI.
**When NOT to use:** Standard DOM interactions (Playwright handles these better).
**Benchmarks:** 94.8% success rate on AndroidWorld (vs 80% human baseline).
**Cost:** Requires AskUI workspace credentials + API key.

---

## 6. Testing Prompts Arsenal Cross-Reference

| Prompt | Use Case |
|--------|----------|
| PF-10 | Real-time audio/video processing benchmark (frame latency) |
| PF-12 | Electron cold start optimization |
| PF-16 | Electron desktop app E2E test suite design |
| PF-17 | Python sidecar + ZMQ IPC communication test |
| PF-15 | CI/CD performance regression suite |
| PT-03 | JavaScript vulnerability mining (renderer process) |
| PT-08 | Dependency audit (Electron + npm + Python) |

---

## Sources

- [Electron Official: Automated Testing](https://www.electronjs.org/docs/latest/tutorial/automated-testing)
- [Playwright Electron API](https://playwright.dev/docs/api/class-electron)
- [WebdriverIO Electron Service](https://webdriver.io/docs/desktop-testing/electron/)
- [Simon Willison: Playwright + Electron + GitHub Actions](https://til.simonwillison.net/electron/testing-electron-playwright)
- [CircleCI: Electron Testing with CI](https://circleci.com/blog/electron-testing/)
- [electron-playwright-example (multi-window)](https://github.com/spaceagetv/electron-playwright-example)
- [AskUI: Agentic AI Desktop Test Automation](https://www.askui.com/blog-posts/agentic-ai-desktop-test-automation)
- [AskUI: Vision Agent Getting Started](https://www.askui.com/blog-posts/getting-started-vision-agents)
- [Mabl: AI Agent Frameworks for E2E Testing](https://www.mabl.com/blog/ai-agent-frameworks-end-to-end-test-automation)
- [Firebase: AI-Powered App Testing Agent](https://firebase.blog/posts/2025/04/app-testing-agent/)

*Updated: 2026-02-21 | 32 reference docs total*
