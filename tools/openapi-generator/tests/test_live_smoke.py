"""Phase 4g level-3 — live smoke against a real WebLogic domain.

Opt-in (CI-friendly default: skipped). Requires:

- `WLS_HOST`        e.g. `wls-admin.example.com`
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

What it covers:

- Tier 1 — basic invariants (root + AdminServer + JVM + threads +
  changeManager idle).
- Tier 2 — polymorphism + quirky-by-design surfaces with real
  schema validation against the response body, not just status:
  applicationRuntimes / componentRuntimes (discriminator routing),
  JDBCServiceRuntime + datasource collection, serverChannelRuntimes
  (quirk 07: `listenAddress`/`listenPort` deliberately absent),
  serverRuntimes collection (quirk 08: selective CSRF).

Captured response bodies are NEVER persisted. The lab VM hostnames /
IPs leak through `links` arrays — the test checks shapes, not values,
and writes nothing to disk.
"""
from __future__ import annotations

import os
import urllib.parse
from pathlib import Path
from typing import Any

import pytest
import yaml

from _oas_jsonschema import get_response_schema, validate_instance


REPO_ROOT = Path(__file__).resolve().parents[3]


def _env_set() -> bool:
    return all(os.environ.get(k) for k in ("WLS_HOST", "WLS_USER", "WLS_PASS", "WLS_VERSION"))


pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not _env_set(), reason="WLS_HOST/USER/PASS/VERSION not set"),
]


@pytest.fixture(scope="session")
def client():
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
            "X-Requested-By": "weblogic-rest-openapi-tests",
        }
    )
    sess.verify = os.environ.get("WLS_INSECURE", "0") != "1"
    return sess, base


@pytest.fixture(scope="session")
def spec() -> dict[str, Any]:
    version = os.environ["WLS_VERSION"]
    spec_path = REPO_ROOT / "specs" / "generated" / f"{version}.yaml"
    if not spec_path.is_file():
        pytest.skip(f"no spec at {spec_path} for WLS_VERSION={version}")
    with spec_path.open() as fh:
        return yaml.safe_load(fh)


@pytest.fixture(scope="session")
def components(spec: dict[str, Any]) -> dict[str, Any]:
    return (spec.get("components") or {}).get("schemas") or {}


def _get(client_, path: str, expected_status: int = 200) -> Any:
    sess, base = client_
    url = f"{base}{path}"
    resp = sess.get(url, timeout=30)
    assert resp.status_code == expected_status, (
        f"GET {path}: expected {expected_status}, got {resp.status_code}: {resp.text[:300]}"
    )
    if resp.status_code == 200:
        return resp.json()
    return resp


def _op_for(spec: dict[str, Any], path_template: str, method: str = "get") -> dict[str, Any] | None:
    """Look up a path operation by its unprefixed template."""
    full = f"/management/weblogic/{{version}}{path_template}"
    item = (spec.get("paths") or {}).get(full)
    if not isinstance(item, dict):
        return None
    op = item.get(method)
    return op if isinstance(op, dict) else None


def _validate(
    instance: Any,
    spec: dict[str, Any],
    components: dict[str, Any],
    path_template: str,
    method: str = "get",
    status: str = "200",
) -> None:
    op = _op_for(spec, path_template, method)
    assert op is not None, f"spec has no {method.upper()} {path_template}"
    raw = get_response_schema(op, status, components)
    assert raw is not None, f"no concrete {status} schema on {method.upper()} {path_template}"
    errors = validate_instance(raw, instance, components)
    if errors:
        msg = "\n".join(f"  - {m}" for m in errors[:8])
        pytest.fail(
            f"live response from {method.upper()} {path_template} fails to validate against "
            f"the {status} schema ({len(errors)} error{'s' if len(errors) != 1 else ''}):\n{msg}"
        )


# --- Tier 1: basic invariants -------------------------------------------


def test_domain_runtime_root(client) -> None:
    body = _get(client, "/domainRuntime")
    assert isinstance(body, dict)
    assert "name" in body or "links" in body, body


def test_admin_server_runtime(client) -> None:
    body = _get(client, "/domainRuntime/serverRuntimes/AdminServer")
    assert body.get("name") == "AdminServer"
    assert body.get("state") in (
        "STARTING", "STANDBY", "ADMIN", "RESUMING", "RUNNING",
        "SUSPENDING", "FORCE_SUSPENDING", "SHUTTING_DOWN",
        "FORCE_SHUTTING_DOWN", "SHUTDOWN", "FAILED",
        "FAILED_NOT_RESTARTABLE", "FAILED_RESTARTING", "UNKNOWN",
    ), body.get("state")
    hs = body.get("healthState") or {}
    assert hs.get("state") in (
        "ok", "warn", "warning", "critical", "failed", "overloaded", "unknown",
    ), hs


def test_admin_jvm_runtime(client) -> None:
    body = _get(client, "/domainRuntime/serverRuntimes/AdminServer/JVMRuntime")
    for key in ("javaVersion", "javaVendor", "javaVMVendor", "OSName"):
        assert key in body, f"missing {key}"
    for key in ("heapSizeCurrent", "heapSizeMax", "heapFreeCurrent"):
        v = body.get(key)
        assert isinstance(v, int) and v >= 0, f"{key}={v!r}"


def test_admin_thread_pool_runtime(client) -> None:
    body = _get(client, "/domainRuntime/serverRuntimes/AdminServer/threadPoolRuntime")
    assert isinstance(body.get("executeThreadTotalCount"), int)
    # Quirk 04: name is the bean type, not the server name.
    assert body.get("name") == "ThreadPoolRuntime", body.get("name")


def test_edit_change_manager_idle(client) -> None:
    body = _get(client, "/edit/changeManager")
    assert body.get("locked") is False, body
    assert body.get("editSession") == "default", body


# --- Tier 2: polymorphism with schema validation ------------------------


def test_application_runtimes_collection(client, spec, components) -> None:
    body = _get(client, "/domainRuntime/serverRuntimes/AdminServer/applicationRuntimes")
    items = body.get("items") or []
    assert items, "expected at least one ApplicationRuntime"
    _validate(
        body, spec, components,
        "/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes",
    )


def test_application_runtime_individual(client, spec, components) -> None:
    coll = _get(client, "/domainRuntime/serverRuntimes/AdminServer/applicationRuntimes")
    items = coll.get("items") or []
    if not items:
        pytest.skip("no applications deployed")
    name = items[0]["name"]
    encoded = urllib.parse.quote(name, safe="")
    body = _get(client, f"/domainRuntime/serverRuntimes/AdminServer/applicationRuntimes/{encoded}")
    _validate(
        body, spec, components,
        "/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes/{applicationName}",
    )


def test_component_runtimes_polymorphic(client, spec, components) -> None:
    """Polymorphic collection — each item carries a `type` discriminator
    that must route to one of WebApp/EJB/AppClient/Connector
    ComponentRuntime."""
    coll = _get(client, "/domainRuntime/serverRuntimes/AdminServer/applicationRuntimes")
    apps = coll.get("items") or []
    if not apps:
        pytest.skip("no applications deployed")
    # Walk apps until we find one with components. Internal apps like
    # `wls-management-services` always have at least a webapp module.
    selected_app = None
    selected_components: list[Any] = []
    for app in apps:
        encoded = urllib.parse.quote(app["name"], safe="")
        comp_body = _get(
            client,
            f"/domainRuntime/serverRuntimes/AdminServer/applicationRuntimes/{encoded}/componentRuntimes",
        )
        items = comp_body.get("items") or []
        if items:
            selected_app = app["name"]
            selected_components = items
            break
    if not selected_app:
        pytest.skip("no application has component runtimes (vanilla domain?)")

    coll_body = {"items": selected_components}
    if "links" in {**({"links": []} if False else {})}:  # noqa: keep shape
        pass
    # Validate the components collection shape via discriminator routing.
    _validate(
        {"items": selected_components},
        spec, components,
        "/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes/"
        "{applicationName}/componentRuntimes",
    )

    # Sanity: at least one item carries a known discriminator value.
    known = {
        "WebAppComponentRuntime",
        "EJBComponentRuntime",
        "AppClientComponentRuntime",
        "ConnectorComponentRuntime",
    }
    types = {c.get("type") for c in selected_components}
    assert types & known, f"no recognised component type in {types}"


def test_jdbc_service_runtime(client, spec, components) -> None:
    body = _get(client, "/domainRuntime/serverRuntimes/AdminServer/JDBCServiceRuntime")
    _validate(
        body, spec, components,
        "/domainRuntime/serverRuntimes/{serverName}/JDBCServiceRuntime",
    )


def test_jdbc_datasource_collection(client, spec, components) -> None:
    body = _get(
        client,
        "/domainRuntime/serverRuntimes/AdminServer/JDBCServiceRuntime/JDBCDataSourceRuntimeMBeans",
    )
    _validate(
        body, spec, components,
        "/domainRuntime/serverRuntimes/{serverName}/JDBCServiceRuntime/"
        "JDBCDataSourceRuntimeMBeans",
    )


def test_jdbc_datasource_individual_polymorphic(client, spec, components) -> None:
    """JDBCDataSourceRuntime has 4 polymorphic subtypes (Default,
    Oracle, UCP, Abstract). Discriminator routes by `type`."""
    coll = _get(
        client,
        "/domainRuntime/serverRuntimes/AdminServer/JDBCServiceRuntime/JDBCDataSourceRuntimeMBeans",
    )
    items = coll.get("items") or []
    if not items:
        pytest.skip("no JDBC datasources configured")
    name = items[0]["name"]
    encoded = urllib.parse.quote(name, safe="")
    body = _get(
        client,
        f"/domainRuntime/serverRuntimes/AdminServer/JDBCServiceRuntime/"
        f"JDBCDataSourceRuntimeMBeans/{encoded}",
    )
    _validate(
        body, spec, components,
        "/domainRuntime/serverRuntimes/{serverName}/JDBCServiceRuntime/"
        "JDBCDataSourceRuntimeMBeans/{dataSourceName}",
    )


# --- Tier 2: quirks confirmed live --------------------------------------


def test_server_channel_runtimes_quirk_07(client, spec, components) -> None:
    """Quirk 07: `listenAddress`, `listenPort`, `protocol`,
    `publicAddress`, `publicPort` are NOT exposed on the REST
    projection of `ServerChannelRuntimeMBean`. Only `publicURL`
    surfaces the network triplet. Confirm both: schema validates
    AND the absent-fields claim holds against live data."""
    body = _get(client, "/domainRuntime/serverRuntimes/AdminServer/serverChannelRuntimes")
    _validate(
        body, spec, components,
        "/domainRuntime/serverRuntimes/{serverName}/serverChannelRuntimes",
    )
    items = body.get("items") or []
    assert items, "no channels on AdminServer (every WLS install has at least Default[t3])"
    forbidden = {"listenAddress", "listenPort", "protocol", "publicAddress", "publicPort"}
    leaks = {f for c in items for f in (forbidden & c.keys())}
    assert not leaks, (
        f"quirk 07 contradicted: REST projection now exposes {leaks!r} on a channel runtime. "
        "Update overlays/quirks/07-channel-missing-fields.yaml."
    )
    # Positive invariant: every channel must have publicURL (the
    # documented surrogate for the missing triplet).
    missing_url = [c.get("name") for c in items if not c.get("publicURL")]
    assert not missing_url, f"channels without publicURL: {missing_url}"


def test_server_channel_individual_with_brackets(client, spec, components) -> None:
    """Channel names contain bracket characters (`Default[t3]`) — must
    be percent-encoded in the URL. Validates the channel runtime
    schema against the live response."""
    body = _get(
        client,
        f"/domainRuntime/serverRuntimes/AdminServer/serverChannelRuntimes/"
        f"{urllib.parse.quote('Default[t3]', safe='')}",
    )
    _validate(
        body, spec, components,
        "/domainRuntime/serverRuntimes/{serverName}/serverChannelRuntimes/{channelName}",
    )
    assert body.get("publicURL", "").startswith("t3://"), body.get("publicURL")


def test_server_runtimes_collection_quirk_08(client, spec, components) -> None:
    """Quirk 08: `GET /domainRuntime/serverRuntimes` requires
    `X-Requested-By` when at least one managed server is RUNNING.
    The session fixture always sends the header — verify the
    happy-path: 200 + AdminServer present + schema valid."""
    body = _get(client, "/domainRuntime/serverRuntimes")
    items = body.get("items") or []
    names = {it.get("name") for it in items}
    assert "AdminServer" in names, f"AdminServer absent from collection: {names}"
    _validate(
        body, spec, components,
        "/domainRuntime/serverRuntimes",
    )
