"""Print config.yaml assumptions as Markdown tables (pasted into README between markers)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import ROOT, Config  # noqa: E402

START, END = "<!-- ASSUMPTIONS:START -->", "<!-- ASSUMPTIONS:END -->"


def scalar_rows(node: dict, path: str = "") -> list[str]:
    rows = []
    for k, v in node.items():
        p = f"{path}.{k}" if path else k
        if isinstance(v, dict) and "value" in v:
            rng = v.get("range", "")
            rows.append(f"| `{p}` | {v['value']} | {v.get('unit', '')} | {rng} | {v.get('source', '')} |")
        elif isinstance(v, dict) and "by_type" not in v:
            rows += scalar_rows(v, p)
    return rows


def table_rows(node: dict, path: str = "") -> list[str]:
    out = []
    for k, v in node.items():
        p = f"{path}.{k}" if path else k
        if isinstance(v, dict) and "by_type" in v:
            out.append(f"\n**`{p}`** — default {v['default']}. {v.get('source', '')}\n")
            out.append("| Property type | Value |\n|---|---|")
            out += [f"| {t} | {x} |" for t, x in v["by_type"].items()]
        elif isinstance(v, dict) and "value" not in v:
            out += table_rows(v, p)
    return out


def render(cfg: Config) -> str:
    head = "| Parameter | Value | Unit | Plausible range | Source / rationale |\n|---|---|---|---|---|"
    return "\n".join([head, *scalar_rows(cfg.raw), "", "### Lookup tables", *table_rows(cfg.raw)])


if __name__ == "__main__":
    md = render(Config.load())
    readme = ROOT / "README.md"
    if "--write" in sys.argv and readme.exists():
        text = readme.read_text()
        new = re.sub(re.escape(START) + ".*?" + re.escape(END), f"{START}\n{md}\n{END}", text, flags=re.S)
        readme.write_text(new)
        print("README assumptions section updated")
    else:
        print(md)
