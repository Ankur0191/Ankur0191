#!/usr/bin/env python3
"""Render a profile activity chart from GitHub's public contribution calendar.

The generated SVG is committed to the profile repository. README visitors load
that static file from GitHub instead of relying on a third-party chart server.
"""
from __future__ import annotations

import datetime as dt
import html
import math
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

USERNAME = "Ankur0191"
SOURCE_URL = f"https://github.com/users/{USERNAME}/contributions"
OUTPUT = Path(__file__).resolve().parents[1] / "activity-graph.svg"


class ContributionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.days: list[dict[str, object]] = []
        self.counts: dict[str, int] = {}
        self._tooltip_for: str | None = None
        self._tooltip_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: (value or "") for key, value in attrs}
        if tag == "td" and "ContributionCalendar-day" in attrs_dict.get("class", ""):
            date_value = attrs_dict.get("data-date", "")
            if date_value:
                self.days.append({
                    "date": date_value,
                    "level": int(attrs_dict.get("data-level", "0") or 0),
                    "id": attrs_dict.get("id", ""),
                })
        elif tag == "tool-tip":
            self._tooltip_for = attrs_dict.get("for", "")
            self._tooltip_text = []

    def handle_data(self, data: str) -> None:
        if self._tooltip_for:
            self._tooltip_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "tool-tip" or not self._tooltip_for:
            return
        tooltip = " ".join("".join(self._tooltip_text).split())
        match = re.search(r"\b(\d+|No)\s+contributions?\b", tooltip, re.IGNORECASE)
        if match:
            self.counts[self._tooltip_for] = (
                0 if match.group(1).lower() == "no" else int(match.group(1))
            )
        self._tooltip_for = None
        self._tooltip_text = []


def fetch_days() -> list[dict[str, object]]:
    request = Request(
        SOURCE_URL,
        headers={"User-Agent": "Ankur0191-profile-activity-graph/1.0"},
    )
    with urlopen(request, timeout=30) as response:
        page = response.read().decode("utf-8", errors="replace")

    parser = ContributionParser()
    parser.feed(page)
    if len(parser.days) < 300:
        raise RuntimeError(
            f"Expected a full public contribution calendar, parsed {len(parser.days)} days."
        )

    parsed: dict[str, dict[str, object]] = {}
    for day in parser.days:
        day_id = str(day["id"])
        level = int(day["level"])
        # Counts come from GitHub's own tooltip. Intensity remains available as
        # a visual fallback if GitHub changes tooltip wording.
        count = parser.counts.get(day_id, level)
        parsed[str(day["date"])] = {"date": str(day["date"]), "count": count, "level": level}

    latest = max(dt.date.fromisoformat(date) for date in parsed)
    start = latest - dt.timedelta(days=364)
    output: list[dict[str, object]] = []
    for offset in range(365):
        day_date = start + dt.timedelta(days=offset)
        key = day_date.isoformat()
        output.append(parsed.get(key, {"date": key, "count": 0, "level": 0}))
    return output


def render_svg(days: list[dict[str, object]]) -> str:
    width, height = 1120, 300
    left, right, top, bottom = 70, 32, 75, 42
    plot_w, plot_h = width - left - right, height - top - bottom
    counts = [int(day["count"]) for day in days]
    peak = max(counts, default=0)
    y_max = max(4, math.ceil(peak / 4) * 4)
    total = sum(counts)
    active_days = sum(value > 0 for value in counts)

    coords: list[tuple[float, float]] = []
    for index, value in enumerate(counts):
        x = left + index / max(1, len(counts) - 1) * plot_w
        y = top + plot_h - (value / y_max) * plot_h
        coords.append((x, y))

    line_path = " ".join(
        ("M" if index == 0 else "L") + f" {x:.2f},{y:.2f}"
        for index, (x, y) in enumerate(coords)
    )
    area_path = (
        f"M {coords[0][0]:.2f},{top + plot_h:.2f} "
        + " ".join(f"L {x:.2f},{y:.2f}" for x, y in coords)
        + f" L {coords[-1][0]:.2f},{top + plot_h:.2f} Z"
    )

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Ankur Mishra — GitHub contribution activity</title>',
        '<desc id="desc">A daily contribution timeline for the most recent 365 days, generated from GitHub public contribution data.</desc>',
        '<defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#22d3ee" stop-opacity=".32"/><stop offset="100%" stop-color="#6366f1" stop-opacity=".015"/></linearGradient><linearGradient id="line" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#818cf8"/><stop offset="55%" stop-color="#22d3ee"/><stop offset="100%" stop-color="#67e8f9"/></linearGradient></defs>',
        '<rect width="1120" height="300" rx="16" fill="#0b1220"/>',
        '<rect x=".5" y=".5" width="1119" height="299" rx="15.5" fill="none" stroke="#263449"/>',
        '<text x="30" y="32" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="12" letter-spacing="2" fill="#67e8f9">GITHUB / CONTRIBUTION ACTIVITY</text>',
        f'<text x="30" y="53" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="11" fill="#71839e">LAST 365 DAYS  ·  {active_days} ACTIVE DAYS  ·  {total:,} CONTRIBUTIONS</text>',
    ]

    # Horizontal guides and compact scale labels.
    for tick in range(5):
        value = round(y_max * tick / 4)
        y = top + plot_h - (tick / 4) * plot_h
        out.append(f'<line x1="{left}" y1="{y:.2f}" x2="{width-right}" y2="{y:.2f}" stroke="#263449" stroke-width="1"/>')
        out.append(f'<text x="{left-12}" y="{y+4:.2f}" text-anchor="end" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="10" fill="#71839e">{value}</text>')

    # Month labels and subtle vertical marks.
    for index, day in enumerate(days):
        date = dt.date.fromisoformat(str(day["date"]))
        if date.day == 1:
            x = left + index / max(1, len(days) - 1) * plot_w
            out.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top+plot_h}" stroke="#263449" stroke-width="1" stroke-dasharray="2 5"/>')
            out.append(f'<text x="{x+3:.2f}" y="{top-12}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="10" fill="#94a3b8">{html.escape(date.strftime("%b"))}</text>')

    out.append(f'<path d="{area_path}" fill="url(#area)"/>')
    out.append(f'<path d="{line_path}" fill="none" stroke="url(#line)" stroke-width="2.3" stroke-linejoin="round" stroke-linecap="round"/>')

    # Mark the peak without adding a legend or decorative clutter.
    if peak > 0:
        peak_idx = counts.index(peak)
        px, py = coords[peak_idx]
        peak_date = html.escape(str(days[peak_idx]["date"]))
        out.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="4" fill="#0b1220" stroke="#67e8f9" stroke-width="2"/>')
        out.append(f'<text x="{min(px + 9, width - 170):.2f}" y="{max(py - 10, top + 4):.2f}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="10" fill="#a5f3fc">peak · {peak_date} · {peak}</text>')

    out.append(f'<text x="{left}" y="{height-13}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="10" fill="#71839e">{html.escape(str(days[0]["date"]))}</text>')
    out.append(f'<text x="{width-right}" y="{height-13}" text-anchor="end" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="10" fill="#71839e">{html.escape(str(days[-1]["date"]))}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    days = fetch_days()
    svg = render_svg(days)
    OUTPUT.write_text(svg, encoding="utf-8")
    print(f"Updated {OUTPUT.name}: {len(days)} days of contribution activity.")


if __name__ == "__main__":
    main()
