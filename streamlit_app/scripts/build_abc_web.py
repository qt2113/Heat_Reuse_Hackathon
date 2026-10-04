"""Build web/abc.html: the exhibition page (map -> radar -> flip cards) on the TEAMMATE's exported results.

Only web/data.json (his model output, buildings, OSM streets) is embedded. No other dataset is used.

    python scripts/build_abc_web.py
"""
import json, pathlib

HERE = pathlib.Path(__file__).resolve().parents[1]
data = json.loads((HERE / "web/data.json").read_text(encoding="utf-8"))
tpl = (HERE / "web/template_abc.html").read_text(encoding="utf-8")
blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\/")
out = tpl.replace("/*__DATA__*/null", blob)
(HERE / "web/abc.html").write_text(out, encoding="utf-8")
print("abc.html", round(len(out) / 1024), "KB;", len(data["scenarios"]), "scenarios;", len(data["buildings"]), "buildings")
