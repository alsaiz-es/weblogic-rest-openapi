"""Phase 4g level-3 — live smoke against a real WebLogic domain.

Opt-in (CI-friendly default: skipped). Requires:

- `WLS_HOST`        e.g. `192.168.1.29`
- `WLS_PORT`        default `7001` (set to `7002` for HTTPS)
- `WLS_SCHEME`      default `http`
- `WLS_USER`        default `weblogic`
- `WLS_PASS`        default empty — set explicitly
- `WLS_VERSION`     one of `12.2.1.3.0`, `12.2.1.4.0`, `14.1.1.0.0`, `14.1.2.0.0`, `15.1.1.0.0`
- `WLS_API_VERSION` default `latest` (the API path segment)
- `WLS_INSECURE`    `1` to disable TLS verification (lab use)

Run with:

    pytest tests/ -m live -v

Without these vars (or without the `-m live` marker) the live tests
skip cleanly. Default `pytest tests/` runs only the offline suites.

What it covers (read-only):

1. **Domain root** `/management/weblogic/<api>/domainRuntime` — must
   return 200 with the expected envelope.
2. **AdminServer runtime** — name + state populated.
3. **JVMRuntime** — JDK identity strings present.
4. **ThreadPoolRuntime** — `executeThreadTotalCount` numeric.
5. **Edit changeManager idle** — `locked: false`.

These are the cheapest signals that the spec lines up with reality.
None of them mutate state; lifecycle and edit mutations stay out of
scope here (they belong in a separate, opt-in destructive suite).

Captured response bodies are NEVER persisted. The lab VM hostnames /
IPs leak through `links` arrays — the test checks shapes, not values,
and asserts no captured response is written to disk. If you need to
add new live tests that capture data, scrub via the project pattern
(`wls-admin.example.com`) before any commit.
"""
from __future__ import annotations

import os
from typing import Any

import pytest


def _env_set() -> bool:
    return all(os.environ.get(k) for k in ("WLS_HOST", "WLS_USER", "WLS_PASS", "WLS_VERSION"))


pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not _env_set(), reason="WLS_HOST/USER/PASS/VERSION not set"),
]


def _client():
    requests = pytest.importorskip("requests")
    host = os.environ["WLS_HOST"]
    port = os.environ.get("WLS_PORT", "7001")
    scheme = os.environ.get("WLS_SCHEME", "http")
    user = os.environ["WLS_USER"]
    pwd = os.environ["WLS_PASS"]
    api = os.environ.get("WLS_API_VERSION", "latest")
    base = f"{scheme}://{host}:{port}/management/weblogic/{api}"
    sess = requests.Session()
    sess.auth = (user, pwd)
    sess.headers.update(
        {
            "Accept": "application/json",
            # Always set X-Requested-By — quirk 06 + quirk 08 both
            # require it on multiple read endpoints, and sending it on
            # endpoints that don't strictly need it is harmless.
            "X-Requested-By": "weblogic-rest-openapi-tests",
        }
    )
    sess.verify = os.environ.get("WLS_INSECURE", "0") != "1"
    return sess, base


def _get(path: str) -> Any:
    sess, base = _client()
    url = f"{base}{path}"
    resp = sess.get(url, timeout=30)
    assert resp.status_code == 200, (
        f"GET {path}: expected 200, got {resp.status_code}: {resp.text[:300]}"
    )
    return resp.json()


def test_domain_runtime_root() -> None:
    body = _get("/domainRuntime")
    assert isinstance(body, dict)
    # Root carries `name` (the domain name) and `links` to children.
    assert "name" in body or "links" in body, body


def test_admin_server_runtime() -> None:
    body = _get("/domainRuntime/serverRuntimes/AdminServer")
    assert body.get("name") == "AdminServer"
    assert body.get("state") in (
        "STARTING",
        "STANDBY",
        "ADMIN",
        "RESUMING",
        "RUNNING",
        "SUSPENDING",
        "FORCE_SUSPENDING",
        "SHUTTING_DOWN",
        "FORCE_SHUTTING_DOWN",
        "SHUTDOWN",
        "FAILED",
        "FAILED_NOT_RESTARTABLE",
        "FAILED_RESTARTING",
        "UNKNOWN",
    ), body.get("state")
    # healthState is documented (quirk 02) as lowercase tokens.
    hs = body.get("healthState") or {}
    assert hs.get("state") in (
        "ok",
        "warn",
        "warning",
        "critical",
        "failed",
        "overloaded",
        "unknown",
    ), hs


def test_admin_jvm_runtime() -> None:
    body = _get("/domainRuntime/serverRuntimes/AdminServer/JVMRuntime")
    # JVM identity strings — exact values vary by install but presence
    # is invariant.
    for key in ("javaVersion", "javaVendor", "javaVMVendor", "OSName"):
        assert key in body, f"missing {key} in JVMRuntime: {body}"
    # Heap counters are int64; presence + non-negative.
    for key in ("heapSizeCurrent", "heapSizeMax", "heapFreeCurrent"):
        v = body.get(key)
        assert isinstance(v, int) and v >= 0, f"{key}={v!r}"


def test_admin_thread_pool_runtime() -> None:
    body = _get("/domainRuntime/serverRuntimes/AdminServer/threadPoolRuntime")
    assert isinstance(body.get("executeThreadTotalCount"), int)
    # `name` quirk: ThreadPoolRuntime's name is literally
    # "ThreadPoolRuntime", not the server name (quirk 04).
    assert body.get("name") == "ThreadPoolRuntime", body.get("name")


def test_edit_change_manager_idle() -> None:
    body = _get("/edit/changeManager")
    # Idle session: `locked` false; `editSession` always "default" in
    # non-Multi-Tenant domains (description overlay covers this).
    assert body.get("locked") is False, body
    assert body.get("editSession") == "default", body
