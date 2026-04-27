"""Dump the generated ServerRuntime schema as OpenAPI YAML and validate it."""
from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path

from openapi_spec_validator import validate
from ruamel.yaml import YAML

from schema_builder import build_component_schema

OUT = Path(__file__).resolve().parents[1] / "out"
OUT.mkdir(exist_ok=True)


def main() -> int:
    out = build_component_schema("ServerRuntimeMBean", "14.1.2.0.0")
    schema_name = out["schemaName"]
    schema = out["schema"]

    placeholders: dict[str, dict[str, object]] = {}

    def collect_refs(node: object) -> None:
        if isinstance(node, dict):
            if "$ref" in node and isinstance(node["$ref"], str) and node["$ref"].startswith(
                "#/components/schemas/"
            ):
                placeholders[node["$ref"].rsplit("/", 1)[-1]] = {"type": "object"}
            for v in node.values():
                collect_refs(v)
        elif isinstance(node, list):
            for v in node:
                collect_refs(v)

    collect_refs(schema)
    placeholders[schema_name] = schema

    doc = {
        "openapi": "3.0.3",
        "info": {"title": "WLS Phase 4a sample", "version": "0.0.0"},
        "paths": {},
        "components": {"schemas": placeholders},
    }

    yaml = YAML()
    yaml.default_flow_style = False
    yaml.width = 120

    schema_path = OUT / f"{schema_name}.generated.yaml"
    with schema_path.open("w") as fh:
        yaml.dump({schema_name: schema}, fh)

    doc_path = OUT / f"{schema_name}.openapi.yaml"
    buf = StringIO()
    yaml.dump(doc, buf)
    doc_path.write_text(buf.getvalue())

    try:
        validate(doc)
        ok = True
        msg = "valid OpenAPI 3.0"
    except Exception as e:  # noqa: BLE001
        ok = False
        msg = f"INVALID: {e}"

    print(f"wrote {schema_path.relative_to(OUT.parent)}")
    print(f"wrote {doc_path.relative_to(OUT.parent)}")
    print(f"openapi-spec-validator: {msg}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
