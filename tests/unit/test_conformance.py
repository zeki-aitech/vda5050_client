"""
The pydantic models and the bundled JSON schemas against the official
VDA5050 2.1.0 schemas (validation/schemas/official-2.1.0/).

Each known difference is listed below with its reason; the tests fail when a
difference appears that is not listed, or a listed one disappears, so a
change to a model or a schema is seen and the list (and the README) kept
true.
"""

import json
from pathlib import Path

import pytest

from vda5050.models import Connection, Factsheet, InstantActions, Order, State, Visualization

SCHEMAS = Path(__file__).resolve().parents[2] / "src" / "vda5050" / "validation" / "schemas"
OFFICIAL = SCHEMAS / "official-2.1.0"

MODELS = {
    "connection": Connection,
    "factsheet": Factsheet,
    "instantActions": InstantActions,
    "order": Order,
    "state": State,
    "visualization": Visualization,
}

# Differences of the models from the official schemas, each a correction.
MODEL_DIFFERENCES = {
    # The specification's text has PAUSED; the 2.1.0 schema lacks it
    # (corrected upstream on 2025-02-20).
    "state/actionStates[]/actionStatus: ENUM ours-only ['PAUSED'] standard-only []",
    # The 2.1.0 schema puts the enum on the array instead of its items
    # (corrected upstream on 2025-02-20); ours is an array of the enum.
    "factsheet/protocolFeatures/agvActions[]/blockingTypes: "
    "ENUM ours-only [] standard-only ['HARD', 'NONE', 'SOFT']",
    # The text says string; the 2.1.0 schema says integer.
    "factsheet/agvGeometry/envelopes3d[]/description: TYPE ours string | standard integer",
    # The text gives the range [0, pi]; the 2.1.0 schema has minimum -pi.
    "order/nodes[]/nodePosition/allowedDeviationTheta: minimum ours 0.0 | standard -3.141592654",
    # The text: degree >= 1, weight >= 0; the 2.1.0 schema has no minimum.
    "state/edgeStates[]/trajectory/degree: minimum ours 1 | standard None",
    "state/edgeStates[]/trajectory/controlPoints[]/weight: minimum ours 0.0 | standard None",
    # The position object of state, reused; mapDescription is optional there.
    "visualization/agvPosition/mapDescription: EXTRA in ours (optional), not in the standard",
}

# Differences of the bundled schemas (used to validate) from the official
# ones, ignoring descriptions: the same corrections as the models.
SCHEMA_DIFFERENCES = {
    "factsheet": {
        "/properties/protocolFeatures/properties/agvActions/items/properties/blockingTypes/enum: "
        "only in official",
        "/properties/protocolFeatures/properties/agvActions/items/properties/blockingTypes/items: "
        "only in bundled",
        "/properties/agvGeometry/properties/envelopes3d/items/properties/description/type: "
        'bundled "string" | official "integer"',
    },
    "order": {
        "/properties/nodes/items/properties/nodePosition/properties/allowedDeviationTheta/minimum: "
        "bundled 0.0 | official -3.141592654",
    },
    "state": {
        "/properties/actionStates/items/properties/actionStatus/enum: "
        "bundled ['PAUSED'] extra, official [] extra",
    },
    "connection": set(),
    "instantActions": set(),
    "visualization": set(),
}


def load(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


# ── the models ────────────────────────────────────────────────────


def _follow(ref: str, root: dict) -> dict:
    node = root
    for part in ref.lstrip("#/").split("/"):
        node = node[part]
    return node


def resolve_model(node, root):
    """Inline $ref and flatten Optional (anyOf [X, null]) of a pydantic schema."""
    if isinstance(node, dict):
        if "$ref" in node:
            merged = dict(resolve_model(_follow(node["$ref"], root), root))
            merged.update({k: v for k, v in node.items() if k != "$ref"})
            return resolve_model(merged, root)
        if "anyOf" in node:
            alternatives = [a for a in node["anyOf"] if a.get("type") != "null"]
            if len(alternatives) == 1:
                return dict(resolve_model(alternatives[0], root))
        if "allOf" in node and len(node["allOf"]) == 1:
            merged = dict(resolve_model(node["allOf"][0], root))
            merged.update({k: v for k, v in node.items() if k != "allOf"})
            return resolve_model(merged, root)
        return {k: resolve_model(v, root) for k, v in node.items() if k != "$defs"}
    if isinstance(node, list):
        return [resolve_model(v, root) for v in node]
    return node


def resolve_official(node, root):
    if isinstance(node, dict):
        if "$ref" in node and node["$ref"].startswith("#"):
            return resolve_official(_follow(node["$ref"], root), root)
        return {k: resolve_official(v, root) for k, v in node.items()}
    if isinstance(node, list):
        return [resolve_official(v, root) for v in node]
    return node


def _type(node: dict):
    t = node.get("type")
    if t is None and "anyOf" in node:
        t = [a.get("type") for a in node["anyOf"] if a.get("type") != "null"]
    if isinstance(t, list):
        return "|".join(sorted(str(x) for x in t))
    if t is None and "enum" in node:
        t = "string"
    return t


def compare(ours: dict, std: dict, path: str, out: list) -> None:
    to, ts = _type(ours), _type(std)
    numbers = {to, ts} == {"number", "integer"}
    if numbers:
        out.append(f"{path}: TYPE ours {to} | standard {ts}")
    elif to != ts and not (ts == "string" and ours.get("format") == "date-time"):
        out.append(f"{path}: TYPE ours {to} | standard {ts}")
    if "enum" in std or "enum" in ours:
        eo, es = set(map(str, ours.get("enum", []))), set(map(str, std.get("enum", [])))
        if eo != es:
            out.append(f"{path}: ENUM ours-only {sorted(eo - es)} standard-only {sorted(es - eo)}")
    for key in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
                "minItems", "maxItems"):
        if ours.get(key) != std.get(key):
            out.append(f"{path}: {key} ours {ours.get(key)} | standard {std.get(key)}")
    if ts == "object" or "properties" in std:
        po, ps = ours.get("properties", {}), std.get("properties", {})
        ro, rs = set(ours.get("required", [])), set(std.get("required", []))
        for k in sorted(set(ps) - set(po)):
            out.append(f"{path}/{k}: MISSING in ours "
                       f"({'required' if k in rs else 'optional'} in the standard)")
        for k in sorted(set(po) - set(ps)):
            out.append(f"{path}/{k}: EXTRA in ours "
                       f"({'required' if k in ro else 'optional'}), not in the standard")
        for k in sorted(set(po) & set(ps)):
            if (k in ro) != (k in rs):
                out.append(f"{path}/{k}: ours {'required' if k in ro else 'optional'} | "
                           f"standard {'required' if k in rs else 'optional'}")
            compare(po[k], ps[k], f"{path}/{k}", out)
    if ts == "array" and "items" in std and "items" in ours:
        compare(ours["items"], std["items"], path + "[]", out)


def model_differences() -> set:
    out: list = []
    for name, model in MODELS.items():
        std = load(OFFICIAL / f"{name}.schema.json")
        raw = model.model_json_schema(by_alias=True)
        compare(resolve_model(raw, raw), resolve_official(std, std), name, out)
    return set(out)


def test_models_differ_from_the_official_schemas_only_where_listed():
    found = model_differences()
    assert found - MODEL_DIFFERENCES == set(), "new differences"
    assert MODEL_DIFFERENCES - found == set(), "listed differences that are gone"


def test_the_comparison_sees_differences():
    """Positive control: a model with a field made optional is caught."""
    std = load(OFFICIAL / "connection.schema.json")
    raw = Connection.model_json_schema()
    raw["required"].remove("connectionState")
    out: list = []
    compare(resolve_model(raw, raw), resolve_official(std, std), "connection", out)
    assert out == ["connection/connectionState: ours optional | standard required"]


# ── the bundled schemas ───────────────────────────────────────────

ANNOTATIONS = {"description", "examples", "title", "$id", "$schema", "$comment"}


def strip(node, in_properties: bool = False):
    """Drop annotations, but not properties that happen to be named like one."""
    if isinstance(node, dict):
        return {k: strip(v, in_properties=(k == "properties" and not in_properties))
                for k, v in node.items() if in_properties or k not in ANNOTATIONS}
    if isinstance(node, list):
        return [strip(v) for v in node]
    return node


def diff(a, b, path: str = "") -> list:
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append(f"{path}/{k}: only in official")
            elif k not in b:
                out.append(f"{path}/{k}: only in bundled")
            else:
                out += diff(a[k], b[k], f"{path}/{k}")
    elif (isinstance(a, list) and isinstance(b, list)
          and all(not isinstance(v, (dict, list)) for v in a + b)):
        if sorted(map(str, a)) != sorted(map(str, b)):
            out.append(f"{path}: bundled {sorted(set(map(str, a)) - set(map(str, b)))} extra, "
                       f"official {sorted(set(map(str, b)) - set(map(str, a)))} extra")
    elif a != b:
        out.append(f"{path}: bundled {json.dumps(a)} | official {json.dumps(b)}")
    return out


@pytest.mark.parametrize("name", sorted(MODELS))
def test_bundled_schema_differs_from_the_official_only_where_listed(name):
    bundled = strip(load(SCHEMAS / f"{name}.schema.json"))
    official = strip(load(OFFICIAL / f"{name}.schema.json"))
    assert set(diff(bundled, official)) == SCHEMA_DIFFERENCES[name]


def test_strip_keeps_a_property_named_description():
    schema = {"properties": {"description": {"type": "string", "description": "x"}}}
    assert strip(schema) == {"properties": {"description": {"type": "string"}}}
