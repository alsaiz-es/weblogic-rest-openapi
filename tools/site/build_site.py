#!/usr/bin/env python3
"""Static reference site for the generated WebLogic REST OpenAPI specs.

Why this exists
---------------
The specs are 5–9 MB YAML files. Search engines don't index them, and
Swagger UI / Redoc render everything client-side from that one huge file,
so none of the content (MBean names, property names, REST paths, quirks)
can be found by search. Someone stuck on `JDBCDataSourceRuntime.state`
or on a 400 from `POST /domainRuntime/search` never lands here.

This script emits plain, crawlable HTML from the same specs:

- one page per MBean, merged across the five WebLogic versions (the newest
  version that has the bean is the body; older versions show up as a
  per-version property diff). One page per bean instead of one per
  bean × version on purpose: five near-identical pages would compete with
  each other for the same queries;
- one page per quirk, from `overlays/quirks/*.yaml`;
- an index, a landing page, a Swagger UI viewer (noindex) and sitemap.xml.

No robots.txt: on a project site (`<user>.github.io/<repo>/`) crawlers
only read robots.txt at the host root, which we don't control. Submit
`sitemap.xml` in Google Search Console instead.

Usage
-----
    python tools/site/build_site.py --out _site \\
        --base-url https://alsaiz-es.github.io/weblogic-rest-openapi

Dependencies: PyYAML, Markdown. Links between generated pages are checked
at the end; a broken internal link fails the build.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import markdown
import yaml

try:  # libyaml is ~10x faster on 9 MB documents
    _Loader = yaml.CSafeLoader
except AttributeError:  # pragma: no cover
    _Loader = yaml.SafeLoader

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PREFIX = "/management/weblogic/{version}"
REPO_URL = "https://github.com/alsaiz-es/weblogic-rest-openapi"
RAW_URL = "https://raw.githubusercontent.com/alsaiz-es/weblogic-rest-openapi/main"

# Envelope plumbing: rendered inline, never as pages.
NO_PAGE = {"Identity", "Link", "EnvelopeBase"}

# Schemas the generator synthesizes (request/response envelopes, error
# bodies). They have no Java MBean behind them, so no "…MBean" alias.
SYNTHETIC = NO_PAGE | {
    "ErrorResponse", "HealthSymptom", "HealthState", "EditErrorDetail",
    "EditErrorResponse", "BulkSearchRequest", "BulkSearchResponse",
    "WLDFLogRecordSearchRequest", "WLDFLogRecord",
    "WLDFLogRecordSearchResponse", "ChangeManagerState",
}


def vkey(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def short_v(v: str) -> str:
    """12.2.1.4.0 -> 12.2.1.4, 14.1.2.0.0 -> 14.1.2"""
    parts = v.split(".")
    while len(parts) > 3 and parts[-1] == "0":
        parts.pop()
    return ".".join(parts)


def ref_name(ref: str) -> str:
    return ref.rsplit("/", 1)[1]


def esc(s) -> str:
    return html.escape(str(s), quote=True)


# --------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------

_CODE = re.compile(r"(```.*?```|`+[^`]*?`+)", re.S)
_md = markdown.Markdown(extensions=["fenced_code", "tables", "sane_lists"])


def md(text: str | None, inline: bool = False) -> str:
    """Markdown -> HTML, with raw `<` neutralised outside code.

    Harvested descriptions are full of literal angle brackets
    (`<beanName>.xml`, `<name, value> pairs`). Markdown passes those
    through as HTML tags and the browser swallows the text — so `<` is
    escaped everywhere except inside code spans, where Markdown already
    escapes it (escaping there too would print `&lt;` literally).
    """
    if not text:
        return ""
    parts = _CODE.split(text)
    for i in range(0, len(parts), 2):
        parts[i] = parts[i].replace("<", "&lt;")
    out = _md.reset().convert("".join(parts))
    if inline and out.startswith("<p>") and out.endswith("</p>") and out.count("<p>") == 1:
        out = out[3:-4]
    return out


def first_paragraph(text: str | None) -> str:
    return (text or "").strip().split("\n\n", 1)[0]


def plain(text: str | None, limit: int = 155) -> str:
    """First sentence(s) of a Markdown description as plain text."""
    if not text:
        return ""
    t = re.sub(r"\*\*Operational note:\*\*.*", "", text, flags=re.S)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"[`*#>]", "", t)  # keep `_`: FORCE_SUSPENDING is a value
    t = " ".join(t.split())
    if len(t) <= limit:
        return t
    cut = t[:limit]
    dot = cut.rfind(". ")
    if dot > limit * 0.5:
        return cut[: dot + 1]
    return cut.rsplit(" ", 1)[0] + "…"


# --------------------------------------------------------------------------
# Spec model
# --------------------------------------------------------------------------

class Spec:
    def __init__(self, version: str, doc: dict):
        self.version = version
        self.doc = doc
        self.schemas: dict = doc["components"]["schemas"]
        self.paths: dict = doc["paths"]
        # schema name -> [(path, "item" | "collection")]
        self.returns: dict[str, list[tuple[str, str]]] = defaultdict(list)
        self.children: dict[str, list[str]] = defaultdict(list)
        for p, item in self.paths.items():
            self.children[p.rsplit("/", 1)[0]].append(p)
            get = item.get("get")
            if not get:
                continue
            hit = response_schema(get)
            if hit:
                self.returns[hit[0]].append((p, hit[1]))
        self._flat: dict[str, tuple] = {}

    def kind(self, name: str) -> str | None:
        d = self.schemas.get(name)
        if d is None:
            return None
        if "enum" in d and "properties" not in d and "allOf" not in d:
            return "enum"
        if "oneOf" in d and "discriminator" in d:
            return "poly"
        return "object"

    def flatten(self, name: str) -> tuple[str | None, dict]:
        """(description, {prop: (definition, inherited_from | None)})."""
        if name in self._flat:
            return self._flat[name]
        d = self.schemas.get(name, {})
        desc = d.get("description")
        props: dict = {}
        for part in d.get("allOf", []):
            if "$ref" in part:
                rn = ref_name(part["$ref"])
                if rn == "EnvelopeBase":
                    continue
                _, sub = self.flatten(rn)
                for pn, (pd, origin) in sub.items():
                    props.setdefault(pn, (pd, origin or rn))
            else:
                desc = desc or part.get("description")
                for pn, pd in (part.get("properties") or {}).items():
                    props[pn] = (pd, None)
        for pn, pd in (d.get("properties") or {}).items():
            props[pn] = (pd, None)
        self._flat[name] = (desc, props)
        return desc, props


def response_schema(op: dict) -> tuple[str, str] | None:
    r = (op.get("responses") or {}).get("200")
    if not isinstance(r, dict):
        return None
    sch = ((r.get("content") or {}).get("application/json") or {}).get("schema") or {}
    if "$ref" in sch:
        return ref_name(sch["$ref"]), "item"
    items = ((sch.get("properties") or {}).get("items") or {}).get("items") or {}
    if "$ref" in items:
        return ref_name(items["$ref"]), "collection"
    return None


def response_example(op: dict):
    r = (op.get("responses") or {}).get("200")
    if not isinstance(r, dict):
        return None
    content = (r.get("content") or {}).get("application/json") or {}
    for ex in (content.get("examples") or {}).values():
        if isinstance(ex, dict) and "value" in ex:
            return ex.get("summary"), ex["value"]
    if "example" in content:
        return None, content["example"]
    return None


def load_specs(spec_dir: Path) -> list[Spec]:
    specs = []
    for f in sorted(spec_dir.glob("*.yaml"), key=lambda p: vkey(p.stem)):
        print(f"  loading {f.name}", file=sys.stderr)
        with f.open() as fh:
            specs.append(Spec(f.stem, yaml.load(fh, Loader=_Loader)))
    if not specs:
        sys.exit(f"no specs found in {spec_dir}")
    return specs


# --------------------------------------------------------------------------
# Site model: which schemas get a page, and where
# --------------------------------------------------------------------------

class Site:
    def __init__(self, specs: list[Spec], quirks: list[dict], base_url: str):
        self.specs = specs
        self.newest = specs[-1]
        self.base_url = base_url.rstrip("/")
        self.quirks = quirks
        self.poly: set[str] = set()
        all_names: dict[str, None] = {}
        for s in specs:
            for n in s.schemas:
                all_names.setdefault(n)
                if s.kind(n) == "poly":
                    self.poly.add(n)
        # A polymorphic `X` and its `XBase` (where the harvested body was
        # moved) are the same bean to a reader: one page, under `X`.
        self.pages: dict[str, None] = {}
        for n in sorted(all_names, key=str.lower):
            if n in NO_PAGE or self.alias_of(n) != n:
                continue
            kinds = {s.kind(n) for s in specs if n in s.schemas}
            if kinds <= {"enum"}:
                continue
            self.pages[n] = None
        self.quirks_by_schema: dict[str, list[dict]] = defaultdict(list)
        self.quirks_by_prop: dict[tuple[str, str], list[dict]] = defaultdict(list)
        self.quirk_targets: dict[str, list[tuple[str, str]]] = {}
        self._map_quirks()

    # -- naming ---------------------------------------------------------
    def alias_of(self, name: str) -> str:
        if name.endswith("Base") and name[:-4] in self.poly:
            return name[:-4]
        return name

    def page_for(self, name: str) -> str | None:
        a = self.alias_of(name)
        return a if a in self.pages else None

    def java_name(self, name: str) -> str | None:
        """Oracle's interface name, for search ("JVMRuntimeMBean").

        The generator builds schema names by dropping `MBean`
        (schema_builder.normalize_schema_name); descriptor beans keep their
        `…Bean` name (nothing to add); polymorphic parents move their body
        to `<Parent>Base`; manual subtypes, synthesized `…Default`
        subtypes and the generator's own envelopes have no Java
        counterpart. Checked against the harvested set of
        oracle/weblogic-remote-console for all five versions.
        """
        if name in SYNTHETIC or name.endswith(("Default", "Bean")):
            return None
        if any(s.schemas.get(name, {}).get("x-weblogic-manual-schema") for s in self.specs):
            return None
        if name.endswith("Base"):
            return name[:-4] + "MBean"
        return name + "MBean"

    def home(self, name: str) -> Spec:
        """Newest spec that defines the bean (or its Base)."""
        for s in reversed(self.specs):
            if name in s.schemas:
                return s
        raise KeyError(name)

    def body_name(self, name: str, spec: Spec) -> str:
        """Schema whose properties make up the page body."""
        if spec.kind(name) == "poly" and name + "Base" in spec.schemas:
            return name + "Base"
        return name

    # -- quirks ---------------------------------------------------------
    def _owner_of_path(self, rel: str) -> tuple[str | None, str | None]:
        full = SPEC_PREFIX + rel
        for s in reversed(self.specs):
            if full not in s.paths:
                continue
            p = full
            while p.startswith(SPEC_PREFIX):
                get = s.paths.get(p, {}).get("get")
                hit = response_schema(get) if get else None
                if hit:
                    return self.page_for(hit[0]), full
                p = p.rsplit("/", 1)[0]
            return None, full
        return None, None

    def _map_quirks(self) -> None:
        for q in self.quirks:
            targets = []
            for a in q.get("attachments", []):
                t = a.get("type")
                if t == "property":
                    page = self.page_for(a["schema"])
                    self.quirks_by_prop[(self.alias_of(a["schema"]), a["property"])].append(q)
                    if page:
                        self.quirks_by_schema[page].append(q)
                        targets.append((page, f"{a['schema']}.{a['property']}", f"#p-{a['property']}"))
                elif t == "schema":
                    page = self.page_for(a["schema"])
                    if page:
                        self.quirks_by_schema[page].append(q)
                        targets.append((page, a["schema"], ""))
                elif t == "path":
                    page, full = self._owner_of_path(a["path"])
                    label = f"{a.get('method', '').upper()} {a['path']}".strip()
                    if page:
                        self.quirks_by_schema[page].append(q)
                    targets.append((page, label, "#operations" if page else ""))
            self.quirk_targets[q["id"]] = targets
        for k in self.quirks_by_schema:
            seen, uniq = set(), []
            for q in self.quirks_by_schema[k]:
                if q["id"] not in seen:
                    seen.add(q["id"])
                    uniq.append(q)
            self.quirks_by_schema[k] = uniq


def load_quirks(qdir: Path) -> list[dict]:
    out = []
    for f in sorted(qdir.glob("*.yaml")):
        q = yaml.safe_load(f.read_text())
        if q and q.get("id"):
            out.append(q)
    return out


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------

CSS = """
:root{--bg:#fff;--fg:#1d2330;--muted:#5d6675;--line:#e3e6eb;--card:#f6f7f9;
--accent:#b8381e;--link:#1b5fb4;--code:#f1f2f5;--warn:#fff4e5;--warnline:#f0b35a}
@media (prefers-color-scheme:dark){:root{--bg:#14171c;--fg:#e4e7ec;--muted:#9aa3b2;
--line:#2b313b;--card:#1b1f26;--accent:#ff8a65;--link:#7fb3ff;--code:#222832;
--warn:#2b2216;--warnline:#8a6424}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--link);text-decoration:none}a:hover{text-decoration:underline}
header.top{border-bottom:1px solid var(--line);background:var(--card)}
header.top .in,main,footer .in{max-width:1120px;margin:0 auto;padding:0 20px}
header.top .in{display:flex;gap:20px;align-items:center;flex-wrap:wrap;min-height:54px}
header.top .brand{font-weight:700;color:var(--fg)}
header.top .brand span{color:var(--accent)}
header.top nav{display:flex;gap:16px;flex-wrap:wrap;font-size:14px}
main{padding-top:18px;padding-bottom:40px}
h1{font-size:28px;line-height:1.25;margin:10px 0 6px}
h1 small{display:block;font-size:15px;font-weight:400;color:var(--muted);margin-top:6px}
h2{font-size:20px;margin:34px 0 10px;padding-top:8px;border-top:1px solid var(--line)}
h3{font-size:16px;margin:22px 0 8px}
code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13px}
code{background:var(--code);padding:1px 5px;border-radius:4px}
pre{background:var(--code);padding:12px 14px;border-radius:6px;overflow-x:auto;line-height:1.45}
pre code{background:none;padding:0}
.crumbs{font-size:13px;color:var(--muted)}
.lead{font-size:16px}
.muted{color:var(--muted)}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}
.chip{font-size:12px;padding:2px 8px;border-radius:12px;border:1px solid var(--line);background:var(--card)}
.chip.off{opacity:.45;text-decoration:line-through}
.badge{display:inline-block;font-size:11px;padding:0 6px;border-radius:4px;border:1px solid var(--line);
color:var(--muted);margin:2px 4px 2px 0;white-space:nowrap}
.badge.q{border-color:var(--warnline);color:var(--accent)}
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:6px}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;vertical-align:top;padding:8px 10px;border-bottom:1px solid var(--line)}
th{background:var(--card);font-weight:600;white-space:nowrap}
tr:last-child td{border-bottom:none}
td.pn{white-space:nowrap;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px}
td.pn a.anchor{color:var(--fg)}
td p{margin:0 0 6px}td p:last-child{margin:0}
td ul{margin:4px 0;padding-left:18px}
tr:target td{background:var(--warn)}
.quirk{border:1px solid var(--warnline);background:var(--warn);border-radius:6px;padding:10px 14px;margin:10px 0}
.quirk h3{margin:0 0 4px;font-size:15px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.card{border:1px solid var(--line);border-radius:8px;padding:14px;background:var(--card)}
.card b{display:block;font-size:22px}
ul.idx{list-style:none;padding:0;columns:2 340px;column-gap:28px}
ul.idx li{break-inside:avoid;padding:4px 0;border-bottom:1px dashed var(--line)}
ul.idx li span{display:block;font-size:12.5px;color:var(--muted)}
input.filter{width:100%;max-width:420px;padding:8px 10px;border:1px solid var(--line);border-radius:6px;
background:var(--bg);color:var(--fg);font-size:15px}
details summary{cursor:pointer;color:var(--link);margin:8px 0}
.method{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;font-weight:700}
.m-get{color:#2e7d32}.m-post{color:#b26a00}.m-delete{color:#c62828}
@media (prefers-color-scheme:dark){.m-get{color:#81c784}.m-post{color:#ffb74d}.m-delete{color:#ef9a9a}}
footer{border-top:1px solid var(--line);font-size:13px;color:var(--muted)}
footer .in{padding:18px 20px}
"""

FILTER_JS = """
<script>
(function(){var i=document.getElementById('f');if(!i)return;
var li=[].slice.call(document.querySelectorAll('ul.idx li'));
i.addEventListener('input',function(){var q=i.value.trim().toLowerCase();
li.forEach(function(e){e.style.display=!q||e.textContent.toLowerCase().indexOf(q)>=0?'':'none'})});})();
</script>
"""


class Page:
    def __init__(self, path: str, title: str, description: str, body: str,
                 *, noindex: bool = False, head_extra: str = "", sitemap: bool = True):
        self.path = path  # relative to site root, e.g. "mbeans/JVMRuntime.html"
        self.title = title
        self.description = description
        self.body = body
        self.noindex = noindex
        self.head_extra = head_extra
        self.sitemap = sitemap and not noindex

    @property
    def depth(self) -> int:
        return self.path.count("/")


def render(page: Page, site: Site) -> str:
    up = "../" * page.depth
    url = f"{site.base_url}/{page.path}".replace("/index.html", "/")
    robots = '<meta name="robots" content="noindex">' if page.noindex else ""
    nav = (f'<a href="{up}mbeans/index.html">MBeans</a>'
           f'<a href="{up}quirks/index.html">Quirks</a>'
           f'<a href="{up}index.html#download">Download</a>'
           f'<a href="{up}viewer.html">Swagger UI</a>'
           f'<a href="{REPO_URL}">GitHub</a>')
    body = page.body.replace("{{UP}}", up)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(page.title)}</title>
<meta name="description" content="{esc(page.description)}">
<link rel="canonical" href="{esc(url)}">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(page.title)}">
<meta property="og:description" content="{esc(page.description)}">
<meta property="og:url" content="{esc(url)}">
{robots}{page.head_extra}
<style>{CSS}</style>
</head>
<body>
<header class="top"><div class="in">
<a class="brand" href="{up}index.html">WebLogic REST <span>OpenAPI</span></a>
<nav>{nav}</nav>
</div></header>
<main>
{body}
</main>
<footer><div class="in">
Unofficial reference generated from the
<a href="{REPO_URL}">weblogic-rest-openapi</a> specifications.
Not affiliated with, endorsed by, or supported by Oracle Corporation.
Oracle and WebLogic are trademarks of Oracle Corporation.
</div></footer>
</body>
</html>
"""


# -- fragments ---------------------------------------------------------------

def link(name: str, site: Site, label: str | None = None) -> str:
    page = site.page_for(name)
    label = esc(label or name)
    if page:
        return f'<a href="{{{{UP}}}}mbeans/{esc(page)}.html"><code>{label}</code></a>'
    return f"<code>{label}</code>"


def enum_html(values: list) -> str:
    vals = [f"<code>{esc(v)}</code>" for v in values if v is not None]
    if len(vals) <= 12:
        return " ".join(vals)
    return (" ".join(vals[:8]) +
            f' <details><summary>+{len(vals) - 8} more</summary>{" ".join(vals[8:])}</details>')


def type_html(pd: dict, spec: Spec, site: Site) -> str:
    if not isinstance(pd, dict):
        return ""
    if "$ref" in pd:
        return ref_html(ref_name(pd["$ref"]), spec, site)
    if "allOf" in pd and len(pd["allOf"]) == 1 and "$ref" in pd["allOf"][0]:
        return ref_html(ref_name(pd["allOf"][0]["$ref"]), spec, site)
    if "oneOf" in pd:
        return " | ".join(type_html(x, spec, site) for x in pd["oneOf"])
    t = pd.get("type", "object")
    if t == "array":
        return type_html(pd.get("items") or {}, spec, site) + "[]"
    s = esc(t)
    if pd.get("format"):
        s += f' <span class="muted">({esc(pd["format"])})</span>'
    if pd.get("enum"):
        s += "<br>" + enum_html(pd["enum"])
    return s


def ref_html(name: str, spec: Spec, site: Site) -> str:
    d = spec.schemas.get(name, {})
    if spec.kind(name) == "enum":
        return f"<code>{esc(name)}</code><br>{enum_html(d.get('enum', []))}"
    return link(name, site)


def flags_html(pd: dict, quirks: list[dict], up_quirk: str) -> str:
    out = []
    if pd.get("readOnly"):
        out.append("read-only")
    if pd.get("nullable"):
        out.append("nullable")
    if pd.get("deprecated"):
        out.append("deprecated")
    if pd.get("x-weblogic-restart-needed"):
        out.append("restart required")
    if pd.get("x-weblogic-redeploy-needed"):
        out.append("redeploy required")
    if pd.get("x-weblogic-date-as-long"):
        out.append("date as long")
    role = pd.get("x-weblogic-required-role")
    if role:
        out.append("role: " + ", ".join(role if isinstance(role, list) else [role]))
    html_ = "".join(f'<span class="badge">{esc(f)}</span>' for f in out)
    for q in quirks:
        html_ += f'<a class="badge q" href="{up_quirk}{esc(q["id"])}.html">quirk</a>'
    return html_


def curl_get(path: str) -> str:
    url = "http://localhost:7001" + path.replace("{version}", "latest")
    return ("curl -s -u weblogic:PASSWORD \\\n"
            "  -H 'Accept: application/json' \\\n"
            f"  '{url}'")


def curl_post(path: str, body) -> str:
    url = "http://localhost:7001" + path.replace("{version}", "latest")
    return ("curl -s -u weblogic:PASSWORD \\\n"
            "  -H 'X-Requested-By: MyClient' \\\n"
            "  -H 'Accept: application/json' \\\n"
            "  -H 'Content-Type: application/json' \\\n"
            f"  -X POST -d '{json.dumps(body)}' \\\n"
            f"  '{url}'")


def show_path(p: str) -> str:
    return p.replace("{version}", "latest")


# -- MBean page ----------------------------------------------------------------

def mbean_page(name: str, site: Site) -> Page:
    home = site.home(name)
    body_name = site.body_name(name, home)
    desc, props = home.flatten(body_name)
    if not desc:
        desc = home.schemas.get(name, {}).get("description")
    java = site.java_name(name)
    present = [s for s in site.specs if name in s.schemas]
    vrange = (short_v(present[0].version) if len(present) == 1
              else f"{short_v(present[0].version)}–{short_v(present[-1].version)}")
    is_poly = home.kind(name) == "poly"
    manual = home.schemas.get(name, {}).get("x-weblogic-manual-schema")

    parts = []
    parts.append(f'<div class="crumbs"><a href="{{{{UP}}}}index.html">Home</a> › '
                 f'<a href="{{{{UP}}}}mbeans/index.html">MBeans</a> › {esc(name)}</div>')
    sub = f"<code>{esc(java)}</code> · " if java else ""
    parts.append(f"<h1>{esc(name)}<small>{sub}WebLogic Server REST Management API · "
                 f"WebLogic {esc(vrange)}</small></h1>")

    chips = []
    for s in site.specs:
        on = name in s.schemas
        chips.append(f'<span class="chip{"" if on else " off"}" '
                     f'title="{"present" if on else "absent"} in {esc(s.version)}">'
                     f'{esc(short_v(s.version))}</span>')
    parts.append(f'<div class="chips">{"".join(chips)}</div>')
    if desc:
        parts.append(f'<div class="lead">{md(desc)}</div>')
    if manual:
        src = home.schemas[name].get("x-weblogic-source")
        parts.append('<p class="muted">Hand-authored schema (no harvested Oracle definition exists'
                     f' for this subtype){": " + md(str(src), inline=True) if src else ""}.</p>')

    quirks = site.quirks_by_schema.get(name, [])
    if quirks:
        parts.append('<h2 id="quirks">Known quirks</h2>')
        for q in quirks:
            parts.append(f'<div class="quirk"><h3><a href="{{{{UP}}}}quirks/{esc(q["id"])}.html">'
                         f'{md(q["title"], inline=True)}</a></h3>'
                         f'{md(first_paragraph((q.get("inject") or {}).get("description_append")))}</div>')

    if is_poly:
        sch = home.schemas[name]
        mapping = (sch.get("discriminator") or {}).get("mapping") or {}
        rows = []
        for disc, ref in sorted(mapping.items(), key=lambda kv: ref_name(kv[1]).lower()):
            rows.append(f"<tr><td>{link(ref_name(ref), site)}</td><td><code>{esc(disc)}</code></td></tr>")
        if rows:
            parts.append('<h2 id="subtypes">Subtypes</h2>')
            parts.append('<p>The concrete subtype is selected by the <code>type</code> property.</p>')
            parts.append('<div class="tw"><table><tr><th>Schema</th><th><code>type</code> value</th></tr>'
                         + "".join(rows) + "</table></div>")

    # operations
    ops_html, example_src = operations_html(name, home, site)
    if ops_html:
        parts.append(ops_html)

    # properties
    if props:
        prop_quirks = {pn: site.quirks_by_prop.get((name, pn), []) for pn in props}
        rows = []
        for pn in sorted(props, key=str.lower):
            pd, origin = props[pn]
            origin_html = ""
            if origin and site.alias_of(origin) != name:
                origin_html = f'<div class="muted" style="font-size:12px">from {link(origin, site)}</div>'
            rows.append(
                f'<tr id="p-{esc(pn)}"><td class="pn"><a class="anchor" href="#p-{esc(pn)}">{esc(pn)}</a>'
                f'{origin_html}</td>'
                f'<td>{type_html(pd, home, site)}</td>'
                f'<td>{flags_html(pd, prop_quirks.get(pn, []), "{{UP}}quirks/")}{md(pd.get("description"))}</td></tr>')
        label = "Base properties" if is_poly else "Properties"
        parts.append(f'<h2 id="properties">{label} <span class="muted">({len(props)}, WebLogic '
                     f'{esc(short_v(home.version))})</span></h2>')
        parts.append('<div class="tw"><table><tr><th>Name</th><th>Type</th><th>Description</th></tr>'
                     + "".join(rows) + "</table></div>")

    # version differences
    vd = version_diff_html(name, site)
    if vd:
        parts.append(vd)

    # example
    ex = example_src
    if ex:
        summary, value, v = ex
        txt = json.dumps(value, indent=2, ensure_ascii=False)
        if len(txt) > 8000:
            txt = txt[:8000] + "\n… (truncated)"
        parts.append(f'<h2 id="example">Example response</h2>'
                     f'<p class="muted">Captured from a live WebLogic {esc(short_v(v))} domain'
                     f'{": " + esc(summary.rstrip(".")) if summary else ""}.</p>'
                     f"<pre><code>{esc(txt)}</code></pre>")

    parts.append(f'<p class="muted" style="margin-top:30px">Source: <code>components.schemas.{esc(name)}</code> in '
                 f'<a href="{RAW_URL}/specs/generated/{esc(home.version)}.yaml">{esc(home.version)}.yaml</a>.</p>')

    first = plain(desc, 120) if desc else ""
    title = f"{name} — WebLogic REST Management API"
    if java and java != name:
        title = f"{name} ({java}) — WebLogic REST API"
    meta = (f"{name}{' (' + java + ')' if java and java != name else ''} in the WebLogic REST "
            f"Management API, WebLogic {vrange}: "
            + (first or f"{len(props)} properties, REST paths and operations."))
    return Page(f"mbeans/{name}.html", title, meta[:300], "\n".join(parts))


def operations_html(name: str, spec: Spec, site: Site):
    """REST paths that return the bean, their operations and actions."""
    names = {name, name + "Base"}
    entries = []
    for n in names:
        entries.extend(spec.returns.get(n, []))
    example = None
    if not entries:
        # still look for an example elsewhere
        return "", find_example(name, site)
    rows = []
    seen = set()
    get_path = post_action = None
    for p, kind in sorted(entries):
        for method in ("get", "post", "delete"):
            op = spec.paths[p].get(method)
            if not op or (p, method) in seen:
                continue
            seen.add((p, method))
            rows.append((p, method, op))
            if method == "get" and kind == "item" and not get_path:
                get_path = p
        for child in spec.children.get(p, []):
            item = spec.paths[child]
            if "get" in item:
                continue
            for method in ("post", "delete"):
                op = item.get(method)
                if op and (child, method) not in seen:
                    seen.add((child, method))
                    rows.append((child, method, op))
                    if method == "post" and post_action is None:
                        rb = ((op.get("requestBody") or {}).get("content") or {}).get("application/json") or {}
                        if "example" in rb:
                            post_action = (child, rb["example"])
    if not get_path:
        get_path = sorted(entries)[0][0]

    def row(p, method, op):
        qbadge = ""
        if op.get("x-weblogic-quirks"):
            qbadge = '<span class="badge q">quirk</span>'
        return (f'<tr><td><span class="method m-{method}">{method.upper()}</span></td>'
                f"<td><code>{esc(show_path(p))}</code></td>"
                f"<td>{qbadge}{md(op.get('summary'), inline=True)}</td></tr>")

    head = '<div class="tw"><table><tr><th></th><th>Path</th><th>Operation</th></tr>'
    LIMIT = 30
    table = head + "".join(row(*r) for r in rows[:LIMIT]) + "</table></div>"
    if len(rows) > LIMIT:
        table += (f"<details><summary>{len(rows) - LIMIT} more operations</summary>"
                  + head + "".join(row(*r) for r in rows[LIMIT:]) + "</table></div></details>")
    out = ['<h2 id="operations">REST paths and operations</h2>',
           f'<p class="muted">WebLogic {esc(short_v(spec.version))}. Paths are shown with '
           '<code>latest</code> as the version segment; an explicit version the server '
           'supports (e.g. <code>14.1.2.0.0</code>) works too. Every <code>POST</code> '
           'needs the <code>X-Requested-By</code> header.</p>',
           table,
           "<h3>Read it with curl</h3>",
           f"<pre><code>{esc(curl_get(get_path))}</code></pre>"]
    if post_action:
        out += ["<h3>Invoke an action</h3>",
                f"<pre><code>{esc(curl_post(*post_action))}</code></pre>"]

    for p, kind in sorted(entries):
        if kind == "item":
            ex = response_example(spec.paths[p]["get"])
            if ex:
                example = (ex[0], ex[1], spec.version)
                break
    return "\n".join(out), example or find_example(name, site)


def find_example(name: str, site: Site):
    for s in reversed(site.specs):
        for n in (name, name + "Base"):
            for p, kind in s.returns.get(n, []):
                if kind != "item":
                    continue
                ex = response_example(s.paths[p]["get"])
                if ex:
                    return ex[0], ex[1], s.version
    return None


def version_diff_html(name: str, site: Site) -> str:
    rows = []
    prev = None
    changed = False
    for s in site.specs:
        v = esc(short_v(s.version))
        if name not in s.schemas:
            changed = True
            rows.append(f'<tr><td>{v}</td><td class="muted">not present</td><td></td></tr>')
            continue
        _, props = s.flatten(site.body_name(name, s))
        cur = set(props)
        if prev is None:
            change = '<span class="muted">first version with this bean</span>'
        else:
            added = sorted(cur - prev, key=str.lower)
            removed = sorted(prev - cur, key=str.lower)
            bits = []
            if added:
                bits.append("added " + ", ".join(f"<code>{esc(a)}</code>" for a in added))
            if removed:
                bits.append("removed " + ", ".join(f"<code>{esc(r)}</code>" for r in removed))
            changed = changed or bool(bits)
            change = "; ".join(bits) or '<span class="muted">no property changes</span>'
        rows.append(f"<tr><td>{v}</td><td>{len(cur)}</td><td>{change}</td></tr>")
        prev = cur
    if not changed:
        return ('<h2 id="versions">Version differences</h2>'
                '<p>Same property set in every covered version '
                f'({", ".join(esc(short_v(s.version)) for s in site.specs)}).</p>')
    return ('<h2 id="versions">Version differences</h2>'
            '<div class="tw"><table><tr><th>WebLogic</th><th>Properties</th><th>Change vs previous version</th></tr>'
            + "".join(rows) + "</table></div>")


# -- index pages -------------------------------------------------------------

def mbean_index(site: Site) -> Page:
    groups: dict[str, list[str]] = {"runtime": [], "config": [], "other": []}
    for n in site.pages:
        s = site.home(n)
        paths = [p for k in (n, n + "Base") for p, _ in s.returns.get(k, [])]
        if any("/domainRuntime" in p for p in paths):
            groups["runtime"].append(n)
        elif any("/edit" in p for p in paths):
            groups["config"].append(n)
        else:
            groups["other"].append(n)

    def item(n):
        s = site.home(n)
        d, _ = s.flatten(site.body_name(n, s))
        d = d or s.schemas.get(n, {}).get("description")
        return (f'<li><a href="{esc(n)}.html"><code>{esc(n)}</code></a>'
                f'<span>{esc(plain(d, 95))}</span></li>')

    titles = {
        "runtime": ("Runtime MBeans", "Monitoring and actions under <code>/domainRuntime</code>."),
        "config": ("Configuration MBeans", "Domain configuration under <code>/edit</code> "
                   "(wrap changes in <code>startEdit</code> / <code>activate</code>)."),
        "other": ("Embedded and polymorphic types", "Types that appear inside other beans "
                  "rather than at a REST path of their own."),
    }
    parts = ['<div class="crumbs"><a href="../index.html">Home</a> › MBeans</div>',
             f"<h1>WebLogic REST API MBean reference<small>{len(site.pages)} beans across WebLogic "
             f"{esc(short_v(site.specs[0].version))}–{esc(short_v(site.newest.version))}</small></h1>",
             '<p><input class="filter" id="f" type="search" placeholder="Filter: JVMRuntime, JDBC, Coherence…"'
             ' aria-label="Filter MBeans"></p>']
    for key in ("runtime", "config", "other"):
        if not groups[key]:
            continue
        t, sub = titles[key]
        parts.append(f'<h2>{t} <span class="muted">({len(groups[key])})</span></h2><p class="muted">{sub}</p>')
        parts.append('<ul class="idx">' + "".join(item(n) for n in groups[key]) + "</ul>")
    parts.append(FILTER_JS)
    return Page("mbeans/index.html",
                "WebLogic REST Management API — MBean reference (runtime and configuration)",
                f"All {len(site.pages)} MBeans exposed by the WebLogic Server REST Management API "
                f"(/management/weblogic), with properties, REST paths, actions and per-version "
                f"differences for WebLogic 12.2.1.3 to 15.1.1.",
                "\n".join(parts))


def quirk_pages(site: Site) -> list[Page]:
    pages = []
    items = []
    for q in site.quirks:
        inj = q.get("inject") or {}
        vers = ", ".join(short_v(v) for v in q.get("applies_to_versions", []))
        targets = site.quirk_targets.get(q["id"], [])
        tl = []
        for page, label, anchor in targets:
            if page:
                tl.append(f'<li><a href="../mbeans/{esc(page)}.html{anchor}"><code>{esc(label)}</code></a></li>')
            else:
                tl.append(f"<li><code>{esc(label)}</code></li>")
        ext = q.get("external_doc")
        ext_html = ""
        if ext:
            ext_html = (f'<p>Full write-up, with how it was observed: '
                        f'<a href="{REPO_URL}/blob/main/{esc(ext)}">{esc(ext)}</a></p>')
        body = [f'<div class="crumbs"><a href="../index.html">Home</a> › '
                f'<a href="index.html">Quirks</a> › {esc(q["id"])}</div>',
                f"<h1>{md(q['title'], inline=True)}<small>WebLogic REST Management API quirk · "
                f"WebLogic {esc(vers)}</small></h1>",
                md(inj.get("description_append"))]
        if tl:
            body.append("<h2>Where it applies</h2><ul>" + "".join(tl) + "</ul>")
        else:
            body.append("<h2>Where it applies</h2><p>Across the whole API.</p>")
        body.append(ext_html)
        title_plain = plain(q["title"], 200)
        pages.append(Page(f"quirks/{q['id']}.html",
                          f"{title_plain} — WebLogic REST API quirk",
                          plain(inj.get("description_append"), 155) or title_plain,
                          "\n".join(body)))
        items.append(f'<li><a href="{esc(q["id"])}.html">{md(q["title"], inline=True)}</a>'
                     f'<span>WebLogic {esc(vers)}</span></li>')
    idx = ['<div class="crumbs"><a href="../index.html">Home</a> › Quirks</div>',
           "<h1>WebLogic REST API quirks<small>Behaviour that contradicts Oracle's documentation "
           "or the API's own naming, observed against live domains</small></h1>",
           "<p>Each one is modelled in the spec as an <code>x-weblogic-quirks</code> entry on the affected "
           "schema, property or path.</p>",
           '<ul class="idx" style="columns:1">' + "".join(items) + "</ul>"]
    pages.append(Page("quirks/index.html",
                      "WebLogic REST Management API quirks and undocumented behaviour",
                      "Undocumented WebLogic REST API behaviour: X-Requested-By on GET serverRuntimes, "
                      "state casing, edit-tree error envelopes, JDBC create returning 400, and more.",
                      "\n".join(idx)))
    return pages


def landing(site: Site, gsv: str | None) -> Page:
    rows = []
    for s in site.specs:
        rows.append(
            f"<tr><td>WebLogic {esc(short_v(s.version))}</td>"
            f"<td>{len(s.schemas)}</td><td>{len(s.paths)}</td>"
            f'<td><a href="specs/{esc(s.version)}.yaml">{esc(s.version)}.yaml</a> · '
            f'<a href="{RAW_URL}/specs/generated/{esc(s.version)}.yaml">raw on GitHub</a> · '
            f'<a href="viewer.html?v={esc(s.version)}">Swagger UI</a></td></tr>')
    quirk_items = "".join(
        f'<li><a href="quirks/{esc(q["id"])}.html">{md(q["title"], inline=True)}</a></li>'
        for q in site.quirks[:8])
    popular = [n for n in ("ServerRuntime", "JVMRuntime", "JDBCDataSourceRuntime", "ThreadPoolRuntime",
                           "ApplicationRuntime", "JMSServerRuntime", "Server", "JDBCSystemResource",
                           "AppDeployment", "Cluster") if n in site.pages]
    pop = " ".join(f'<a href="mbeans/{esc(n)}.html"><code>{esc(n)}</code></a>' for n in popular)
    vr = f"{short_v(site.specs[0].version)}–{short_v(site.newest.version)}"
    v_list = ", ".join(short_v(s.version) for s in site.specs)
    body = f"""
<h1>WebLogic REST Management API — OpenAPI 3.0 / Swagger specification
<small>Unofficial, machine-readable spec for <code>/management/weblogic</code> on WebLogic Server {esc(v_list)}</small></h1>
<p class="lead">Oracle WebLogic Server exposes a REST management interface for monitoring, configuration,
deployment and lifecycle, but Oracle does not publish an OpenAPI (Swagger) description of it.
This project generates one per WebLogic version from Oracle's own open-source MBean catalog
(<a href="https://github.com/oracle/weblogic-remote-console">weblogic-remote-console</a>),
then corrects it with behaviour observed against live domains.</p>
<div class="grid">
<div class="card"><b>{len(site.specs)}</b>WebLogic versions ({esc(vr)})</div>
<div class="card"><b>{len(site.pages)}</b><a href="mbeans/index.html">MBeans documented</a></div>
<div class="card"><b>{len(site.quirks)}</b><a href="quirks/index.html">documented quirks</a></div>
</div>
<h2>Most used beans</h2>
<p>{pop}</p>
<h2 id="download">Download the specification</h2>
<div class="tw"><table><tr><th>Version</th><th>Schemas</th><th>Paths</th><th>Files</th></tr>
{''.join(rows)}</table></div>
<h2>Use it</h2>
<h3>Browse it in Swagger UI</h3>
<pre><code>docker run -p 8080:8080 -e SWAGGER_JSON=/spec.yaml \\
  -v "$(pwd)/14.1.2.0.0.yaml:/spec.yaml" swaggerapi/swagger-ui</code></pre>
<h3>Generate a client</h3>
<pre><code>npx @openapitools/openapi-generator-cli generate \\
  -i 14.1.2.0.0.yaml -g python -o ./weblogic-client</code></pre>
<h3>Call the API</h3>
<pre><code>{esc(curl_get(SPEC_PREFIX + "/domainRuntime/serverRuntimes/{serverName}"))}</code></pre>
<h2>Known quirks</h2>
<p>Behaviour that surprises anyone writing a client, each one verified against a live domain:</p>
<ul>{quirk_items}</ul>
<p><a href="quirks/index.html">All {len(site.quirks)} quirks →</a></p>
<h2>How it is built</h2>
<p>Schemas, paths and actions are generated from the harvested MBean YAMLs that Oracle ships in
weblogic-remote-console (~830 MBeans per version), then refined with editorial overlays: quirks,
operational notes, nullability fixes found while validating live responses, and hand-authored
polymorphic subtypes. Every spec passes <code>openapi-spec-validator</code>, Spectral and
<code>openapi-generator</code>. Details and source: <a href="{REPO_URL}">github.com/alsaiz-es/weblogic-rest-openapi</a>.</p>
"""
    ld = {
        "@context": "https://schema.org",
        "@type": "SoftwareSourceCode",
        "name": "WebLogic REST Management API — OpenAPI specification",
        "description": "Unofficial OpenAPI 3.0 specification for the Oracle WebLogic Server REST Management API.",
        "codeRepository": REPO_URL,
        "programmingLanguage": "OpenAPI",
        "url": site.base_url + "/",
    }
    head = f'<script type="application/ld+json">{json.dumps(ld)}</script>'
    if gsv:
        head += f'\n<meta name="google-site-verification" content="{esc(gsv)}">'
    return Page("index.html",
                f"WebLogic REST API OpenAPI / Swagger specification ({vr})",
                f"Unofficial OpenAPI 3.0 (Swagger) specification for the Oracle WebLogic Server REST "
                f"Management API, WebLogic {v_list}: MBeans, REST paths, actions and documented quirks.",
                body, head_extra=head)


def viewer(site: Site) -> Page:
    opts = "".join(f'<option value="{esc(s.version)}">{esc(s.version)}</option>' for s in reversed(site.specs))
    body = f"""
<p><label>Version <select id="v">{opts}</select></label>
<span class="muted"> The 12.2.1.x specs are ~9 MB; the first render takes a few seconds.</span></p>
<div id="swagger-ui"></div>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
(function(){{
  var sel=document.getElementById('v');
  var q=new URLSearchParams(location.search).get('v');
  if(q) sel.value=q;
  function load(){{ SwaggerUIBundle({{url:'specs/'+sel.value+'.yaml',dom_id:'#swagger-ui',deepLinking:true}}); }}
  sel.addEventListener('change',function(){{history.replaceState(null,'','?v='+sel.value);load();}});
  load();
}})();
</script>
"""
    return Page("viewer.html", "WebLogic REST API — Swagger UI", "Interactive Swagger UI for the WebLogic REST spec.",
                body, noindex=True)


def not_found() -> Page:
    return Page("404.html", "Not found — WebLogic REST OpenAPI", "Page not found.",
                '<h1>Page not found</h1><p><a href="{{UP}}index.html">Home</a> · '
                '<a href="{{UP}}mbeans/index.html">MBean reference</a></p>', noindex=True)


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------

def check_links(out: Path) -> list[str]:
    bad = []
    href = re.compile(r'href="([^"#?]+)(?:[#?][^"]*)?"')
    for f in out.rglob("*.html"):
        for target in href.findall(f.read_text()):
            if re.match(r"^[a-z]+:", target) or target.startswith("//"):
                continue
            if not (f.parent / target).resolve().exists():
                bad.append(f"{f.relative_to(out)} -> {target}")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default="_site")
    ap.add_argument("--base-url", default="https://alsaiz-es.github.io/weblogic-rest-openapi")
    ap.add_argument("--specs", default=str(REPO_ROOT / "specs" / "generated"))
    ap.add_argument("--quirks", default=str(REPO_ROOT / "overlays" / "quirks"))
    ap.add_argument("--google-site-verification", default=None,
                    help="token for the <meta name=google-site-verification> tag on the home page")
    args = ap.parse_args()

    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    (out / "mbeans").mkdir(parents=True)
    (out / "quirks").mkdir()
    (out / "specs").mkdir()

    specs = load_specs(Path(args.specs))
    site = Site(specs, load_quirks(Path(args.quirks)), args.base_url)

    pages = [landing(site, args.google_site_verification), mbean_index(site), viewer(site), not_found()]
    pages += quirk_pages(site)
    pages += [mbean_page(n, site) for n in site.pages]

    for p in pages:
        dest = out / p.path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(render(p, site), encoding="utf-8")
    for s in specs:
        shutil.copy(Path(args.specs) / f"{s.version}.yaml", out / "specs" / f"{s.version}.yaml")

    urls = [f"{site.base_url}/{p.path}".replace("/index.html", "/") for p in pages if p.sitemap]
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{esc(u)}</loc></url>\n" for u in urls)
        + "</urlset>\n", encoding="utf-8")

    bad = check_links(out)
    print(f"{len(pages)} pages ({len(site.pages)} MBeans, {len(site.quirks)} quirks), "
          f"{len(urls)} URLs in sitemap.xml -> {out}", file=sys.stderr)
    if bad:
        print(f"{len(bad)} broken internal links:", file=sys.stderr)
        for b in bad[:30]:
            print("  " + b, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
