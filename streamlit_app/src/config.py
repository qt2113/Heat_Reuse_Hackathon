"""Load config.yaml and expose assumption values.

Every numeric assumption in config.yaml is a dict ``{value, unit, range, source}``.
``Config.v("supply.q_src_mw")`` returns the bare value; ``Config.raw`` keeps everything
so the app can render the full assumptions table.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config.yaml"


class Config:
    """Thin wrapper around the parsed YAML with dotted-path access and overrides."""

    def __init__(self, raw: dict[str, Any]):
        self.raw = raw

    @classmethod
    def load(cls, path: Path | str = DEFAULT_CONFIG) -> "Config":
        with open(path) as f:
            return cls(yaml.safe_load(f))

    def get(self, path: str) -> Any:
        """Return the node at a dotted path (dict for assumptions)."""
        node: Any = self.raw
        for key in path.split("."):
            node = node[key]
        return node

    def v(self, path: str) -> Any:
        """Return the ``value`` of an assumption, or the node itself if it has none."""
        node = self.get(path)
        return node["value"] if isinstance(node, dict) and "value" in node else node

    def with_overrides(self, overrides: dict[str, Any]) -> "Config":
        """Copy with ``{dotted.path: new_value}`` applied to each assumption's value."""
        raw = copy.deepcopy(self.raw)
        new = Config(raw)
        for path, value in overrides.items():
            node = new.get(path)
            if isinstance(node, dict) and "value" in node:
                node["value"] = value
            else:
                parent_path, key = path.rsplit(".", 1)
                new.get(parent_path)[key] = value
        return new

    @property
    def cache_dir(self) -> Path:
        return ROOT / self.raw["data"]["cache_dir"]

    def by_type(self, path: str, prop_type: str) -> float:
        """Lookup in a ``{default, by_type}`` table (e.g. demand.dhw_share)."""
        table = self.get(path)
        return table["by_type"].get(prop_type, table["default"])
