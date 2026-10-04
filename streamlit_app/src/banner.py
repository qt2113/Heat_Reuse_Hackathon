"""Hero banner: a flat, drawn Chelsea skyline that illustrates the current scenario.

Not a map. Named silhouettes (Fulton Houses, Chelsea Market, 212 W 18th St, 155 W 11th St)
turn orange only when that building is connected; generic silhouettes turn orange,
nearest-to-the-data-center first, for the other connected buildings. Colors come from the
reference data-viz palette; neutrals use currentColor + opacity so the banner works on both
light and dark Streamlit themes.
"""
from __future__ import annotations

import base64
import html

BLUE, ORANGE = "#2a78d6", "#eb6834"
W, GROUND = 1200, 150           # viewBox width, street line (y)
DC_X, DC_W = 424, 140           # 111 8th Ave silhouette

# (x, width, height, match-substring or None, label or None)
SLOTS: list[tuple[int, int, int, str | None, str | None]] = [
    (10, 38, 56, None, None), (52, 50, 38, None, None),
    (110, 34, 88, "FULTON", "Fulton Houses"), (150, 34, 66, "FULTON", None), (190, 34, 88, "FULTON", None),
    (232, 26, 60, None, None), (264, 120, 40, "Chelsea Market", "Chelsea Market"), (390, 26, 72, None, None),
    (572, 30, 50, None, None), (608, 44, 96, "212 West 18th", "212 W 18th St"), (658, 50, 62, None, None),
    (714, 28, 84, None, None), (750, 46, 44, None, None), (802, 34, 70, None, None),
    (842, 70, 68, "155 West 11th", "155 W 11th St"), (918, 30, 52, None, None), (954, 44, 80, None, None),
    (1004, 56, 46, None, None), (1066, 32, 64, None, None), (1104, 44, 36, None, None), (1152, 40, 58, None, None),
]
# faint background towers (incl. an Empire State Building outline) for an unmistakable NYC read
FAR = [(70, 40, 80), (300, 50, 96), (520, 30, 120), (690, 44, 104), (880, 40, 92), (1120, 50, 86)]
EMPIRE_X = 1010


def _rect(x: float, y: float, w: float, h: float, fill: str, opacity: float = 1.0) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" fill-opacity="{opacity}"/>'


INK = {"light": "#31333f", "dark": "#fafafa"}   # Streamlit's default text colours

SVG_STYLE = """<style>
.sk-label{font:12px 'IBM Plex Sans',sans-serif;fill:INK;fill-opacity:.7}.sk-strong{fill-opacity:.9;font-weight:600}
.sk-pipe{fill:none;stroke:#eb6834;stroke-width:4;stroke-dasharray:10 8}
.sk-pipe-r{animation:r 1s linear infinite}.sk-pipe-l{animation:l 1s linear infinite}
@keyframes r{from{stroke-dashoffset:18}to{stroke-dashoffset:0}}
@keyframes l{from{stroke-dashoffset:-18}to{stroke-dashoffset:0}}
.sk-heat{animation:rise 2.4s ease-in-out infinite;opacity:0}.sk-heat1{animation-delay:.8s}.sk-heat2{animation-delay:1.6s}
@keyframes rise{0%{opacity:0;transform:translateY(6px)}50%{opacity:1}100%{opacity:0;transform:translateY(-6px)}}
@media (prefers-reduced-motion:reduce){.sk-pipe,.sk-heat{animation:none;opacity:1}}
</style>"""


def skyline_svg(connected_names: list[str], theme: str = "dark") -> str:
    """Standalone SVG skyline; orange = connected. ``connected_names`` are LL84 property names.
    Rendered as an <img> (st.html strips inline SVG), so colours are explicit per theme."""
    ink = INK.get(theme, INK["dark"])
    names = [n.upper() for n in connected_names]
    is_named_on = {i: any(s[3].upper() in n for n in names) for i, s in enumerate(SLOTS) if s[3]}
    named_hits = {s[3] for i, s in enumerate(SLOTS) if s[3] and is_named_on[i]}
    others = len(connected_names) - sum(any(k.upper() in n for k in named_hits) for n in names)
    generic = sorted((i for i, s in enumerate(SLOTS) if not s[3]),
                     key=lambda i: abs(SLOTS[i][0] + SLOTS[i][1] / 2 - (DC_X + DC_W / 2)))
    on = {i for i, v in is_named_on.items() if v} | set(generic[:max(0, others)])

    parts = []
    for x, w, h in FAR:
        parts.append(_rect(x, GROUND - h, w, h, ink, 0.06))
    ex = EMPIRE_X  # stepped tower + spire
    for dx, w, h in [(0, 34, 112), (7, 20, 128), (12, 10, 140)]:
        parts.append(_rect(ex + dx, GROUND - h, w, h, ink, 0.08))
    parts.append(_rect(ex + 16, GROUND - 158, 2, 18, ink, 0.08))

    for i, (x, w, h, _, label) in enumerate(SLOTS):
        hot = i in on
        parts.append(_rect(x, GROUND - h, w, h, ORANGE if hot else ink, 0.95 if hot else 0.16))
        if hot:   # lit windows
            for wy in range(GROUND - h + 8, GROUND - 6, 14):
                for wx in range(x + 5, x + w - 8, 12):
                    parts.append(_rect(wx, wy, 5, 5, "#fff3ea", 0.75))
        if label:
            parts.append(f'<text x="{x}" y="{GROUND - h - 6}" class="sk-label">{html.escape(label)}</text>')

    # 111 8th Ave: stepped art-deco block with banding + rising heat
    for dx, w, h in [(0, DC_W, 104), (12, DC_W - 24, 118), (28, DC_W - 56, 130)]:
        parts.append(_rect(DC_X + dx, GROUND - h, w, h, BLUE))
    for y in range(GROUND - 96, GROUND - 4, 12):
        parts.append(_rect(DC_X + 10, y, DC_W - 20, 3, "#ffffff", 0.35))
    parts.append(f'<text x="{DC_X + 28}" y="{GROUND - 138}" class="sk-label sk-strong">111 8th Ave · data center</text>')
    for k, dx in enumerate((48, 70, 92)):
        parts.append(f'<path class="sk-heat sk-heat{k}" d="M{DC_X + dx} {GROUND - 150} q-6 -8 0 -16 q6 -8 0 -16" '
                     f'fill="none" stroke="{ORANGE}" stroke-width="2.5" stroke-linecap="round"/>')

    # street + pipe (dashes flow outward via CSS animation)
    parts.append(_rect(0, GROUND, W, 10, ink, 0.22))
    hot_x = [SLOTS[i][0] + SLOTS[i][1] / 2 for i in on]
    centre = DC_X + DC_W / 2
    left = min([x for x in hot_x if x < centre], default=centre)
    right = max([x for x in hot_x if x > centre], default=centre)
    drops = "".join(f" M{x:.0f} {GROUND + 20} V{GROUND}" for x in hot_x)
    if hot_x:
        parts.append(f'<path class="sk-pipe sk-pipe-l" d="M{centre:.0f} {GROUND + 20} H{left:.0f}"/>')
        parts.append(f'<path class="sk-pipe sk-pipe-r" d="M{centre:.0f} {GROUND + 20} H{right:.0f}{drops}"/>')
        parts.append(f'<path class="sk-pipe" d="M{centre:.0f} {GROUND} V{GROUND + 20}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {GROUND + 30}">'
            + SVG_STYLE.replace("INK", ink) + "".join(parts) + "</svg>")


CSS = """
<style>
.hero{border:1px solid rgba(128,128,128,.25);border-radius:14px;padding:18px 22px 6px;margin-bottom:6px}
.hero-top{display:flex;flex-wrap:wrap;gap:16px;justify-content:space-between;align-items:flex-start}
.hero h1{font-size:2.1rem;line-height:1.15;margin:0;padding:0}
.hero .sub{opacity:.72;margin-top:4px;font-size:.95rem}
.hero .tag{display:inline-block;font-size:.8rem;border:1px solid #eb6834;color:#eb6834;border-radius:999px;padding:1px 10px;margin-bottom:6px}
.chips{display:flex;gap:10px;flex-wrap:wrap}
.chip{border:1px solid rgba(128,128,128,.3);border-radius:10px;padding:6px 14px;min-width:110px}
.chip .k{font-size:.78rem;opacity:.7}.chip .v{font-size:1.25rem;font-weight:600}
</style>
"""


def hero_html(preset_label: str, kpi: dict, connected_names: list[str], theme: str = "dark") -> str:
    """Full banner: title, scenario tag, three headline chips, skyline."""
    chips = [("Heat delivered", f"{kpi['served_mwh'] / 1000:,.1f} GWh/yr"),
             ("CO₂ cut", f"{kpi['co2_net_t']:,.0f} t/yr"),
             ("Net value", f"${kpi['net_usd'] / 1e6:,.2f}M/yr")]
    chip_html = "".join(f'<div class="chip"><div class="k">{k}</div><div class="v">{v}</div></div>' for k, v in chips)
    return (CSS + '<div class="hero"><div class="hero-top"><div>'
            f'<span class="tag">{html.escape(preset_label)}</span>'
            '<h1>Heat Reusage Network Visualizer</h1></div>'
            f'<div class="chips">{chip_html}</div></div>'
            + skyline_img(connected_names, theme, kpi["buildings"]) + "</div>")


def skyline_img(connected_names: list[str], theme: str, n: int) -> str:
    data = base64.b64encode(skyline_svg(connected_names, theme).encode()).decode()
    return (f'<img src="data:image/svg+xml;base64,{data}" style="width:100%;display:block;margin-top:6px" '
            f'alt="Skyline: {n} buildings connected to 111 8th Ave (orange)"/>')
