"""app/rms/charts.py — server-side SVG chart helpers.

Zero dependencies. Pure Python + Jinja2-friendly output.
All charts return SVG strings with proper ARIA labels for accessibility.
Charts are designed to be inlined directly into HTML templates.

Design principles:
- Use semantic tokens via CSS custom properties so charts adapt to theme.
- viewBox-based responsive (no JS required).
- Animations gated by prefers-reduced-motion via CSS.
- Tabular fallback for screen readers via role="img" + aria-label.
"""

from __future__ import annotations

from datetime import datetime
from typing import Sequence


def _esc(text: str) -> str:
    """Escape XML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def sparkline(
    values: Sequence[float],
    *,
    width: int = 120,
    height: int = 32,
    label: str = "",
    color: str = "var(--color-accent)",
) -> str:
    """Tiny line chart for inline use in metric cards.

    Values are normalised to fit the chart height.
    """
    if not values or len(values) < 2:
        return ""

    min_v = min(values)
    max_v = max(values)
    range_v = max(max_v - min_v, 1e-9)

    n = len(values)
    step_x = width / (n - 1) if n > 1 else width

    points = []
    for i, v in enumerate(values):
        x = i * step_x
        y = height - ((v - min_v) / range_v) * (height - 4) - 2
        points.append(f"{x:.2f},{y:.2f}")

    path_d = "M " + " L ".join(points)
    aria = f' role="img" aria-label="{_esc(label)}"' if label else ' role="img"'

    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}"{aria} '
        f'preserveAspectRatio="none" class="sparkline">'
        f'<path d="{path_d}" fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{points[-1].split(",")[0]}" cy="{points[-1].split(",")[1]}" r="2" fill="{color}"/>'
        f"</svg>"
    )


def line_chart(
    values: Sequence[tuple[str, float]],
    *,
    width: int = 600,
    height: int = 220,
    label: str = "",
    y_format: str = "{:,.0f}",
    color: str = "var(--color-accent)",
    show_dots: bool = True,
) -> str:
    """Line chart with x-axis labels (e.g. dates) and y-axis values.

    values: list of (x_label, y_value) tuples.
    """
    if not values:
        return '<p class="text-muted">Sin datos</p>'

    n = len(values)
    min_y = min(v for _, v in values)
    max_y = max(v for _, v in values)
    range_y = max(max_y - min_y, 1e-9)

    padding = {"top": 16, "right": 16, "bottom": 32, "left": 56}
    plot_w = width - padding["left"] - padding["right"]
    plot_h = height - padding["top"] - padding["bottom"]

    step_x = plot_w / (n - 1) if n > 1 else plot_w

    # Compute points
    points = []
    for i, (_, v) in enumerate(values):
        x = padding["left"] + i * step_x
        y = padding["top"] + plot_h - ((v - min_y) / range_y) * plot_h
        points.append((x, y))

    # Path
    path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in points)

    # Y-axis grid (4 lines)
    grid_lines = []
    y_labels = []
    for i in range(5):
        y_val = min_y + (max_y - min_y) * i / 4
        y_pos = padding["top"] + plot_h - (i / 4) * plot_h
        grid_lines.append(
            f'<line x1="{padding["left"]}" y1="{y_pos:.1f}" '
            f'x2="{width - padding["right"]}" y2="{y_pos:.1f}" '
            f'stroke="var(--color-border)" stroke-dasharray="2,2" stroke-width="0.5"/>'
        )
        y_labels.append(
            f'<text x="{padding["left"] - 4}" y="{y_pos + 4:.1f}" '
            f'font-size="10" fill="var(--color-text-muted)" text-anchor="end">'
            f"{_esc(y_format.format(y_val))}</text>"
        )

    # X-axis labels (show every nth to avoid crowding)
    step = max(1, n // 8)
    x_labels = []
    for i in range(0, n, step):
        x = padding["left"] + i * step_x
        y = height - padding["bottom"] + 14
        x_labels.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-size="10" '
            f'fill="var(--color-text-muted)" text-anchor="middle">{_esc(values[i][0])}</text>'
        )

    # Data points (dots)
    dots_svg = ""
    if show_dots:
        dots_svg = "".join(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}"/>' for x, y in points
        )

    aria = f' role="img" aria-label="{_esc(label)}"' if label else ' role="img"'

    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}"{aria}>'
        f"<title>{_esc(label)}</title>"
        + "".join(grid_lines)
        + "".join(y_labels)
        + "".join(x_labels)
        + f'<path d="{path_d}" fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round"/>' + dots_svg + "</svg>"
    )


def bar_chart(
    values: Sequence[tuple[str, float]],
    *,
    width: int = 600,
    height: int = 220,
    label: str = "",
    color: str = "var(--color-accent)",
    horizontal: bool = False,
) -> str:
    """Bar chart for rankings (e.g. top products).

    values: list of (label, value) tuples.
    """
    if not values:
        return '<p class="text-muted">Sin datos</p>'

    max_v = max(v for _, v in values)
    n = len(values)

    if horizontal:
        # Horizontal bars (good for top-N lists)
        bar_h = 24
        gap = 8
        total_h = n * (bar_h + gap)
        padding = {"top": 8, "right": 60, "bottom": 8, "left": 120}
        actual_w = max(width, 200)
        plot_w = actual_w - padding["left"] - padding["right"]

        bars = []
        for i, (name, v) in enumerate(values):
            y = padding["top"] + i * (bar_h + gap)
            bar_w = (v / max_v) * plot_w if max_v > 0 else 0
            bars.append(
                f'<text x="{padding["left"] - 4}" y="{y + bar_h / 2 + 4:.1f}" '
                f'font-size="11" fill="var(--color-text)" text-anchor="end">{_esc(name)}</text>'
                f'<rect x="{padding["left"]}" y="{y}" width="{bar_w:.1f}" height="{bar_h}" '
                f'fill="{color}" rx="3"/>'
                f'<text x="{padding["left"] + bar_w + 4:.1f}" y="{y + bar_h / 2 + 4:.1f}" '
                f'font-size="10" fill="var(--color-text-muted)">{int(v):,}</text>'
            )

        aria = f' role="img" aria-label="{_esc(label)}"' if label else ' role="img"'
        return (
            f'<svg viewBox="0 0 {actual_w} {total_h}" width="100%" height="{total_h}"{aria}>'
            f"<title>{_esc(label)}</title>" + "".join(bars) + "</svg>"
        )

    # Vertical bars
    padding = {"top": 16, "right": 16, "bottom": 32, "left": 40}
    plot_w = width - padding["left"] - padding["right"]
    plot_h = height - padding["top"] - padding["bottom"]
    bar_w = (plot_w / n) * 0.7
    gap_w = (plot_w / n) * 0.3

    bars = []
    for i, (name, v) in enumerate(values):
        x = padding["left"] + i * (bar_w + gap_w) + gap_w / 2
        h = (v / max_v) * plot_h if max_v > 0 else 0
        y = padding["top"] + plot_h - h
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" '
            f'fill="{color}" rx="3"/>'
        )
        # x-axis label (show every nth)
        if i % max(1, n // 6) == 0:
            bars.append(
                f'<text x="{x + bar_w / 2:.1f}" y="{height - 8}" font-size="10" '
                f'fill="var(--color-text-muted)" text-anchor="middle">{_esc(name)}</text>'
            )

    aria = f' role="img" aria-label="{_esc(label)}"' if label else ' role="img"'
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}"{aria}>'
        f"<title>{_esc(label)}</title>" + "".join(bars) + "</svg>"
    )


def pie_donut(
    values: Sequence[tuple[str, float]],
    *,
    size: int = 160,
    label: str = "",
    colors: Sequence[str] | None = None,
) -> str:
    """Donut chart for proportional data (e.g. payment methods).

    values: list of (label, value) tuples.
    """
    if not values:
        return '<p class="text-muted">Sin datos</p>'

    total = sum(v for _, v in values)
    if total <= 0:
        return '<p class="text-muted">Sin datos</p>'

    if colors is None:
        colors = [
            "var(--color-accent)",
            "var(--color-info)",
            "var(--color-success)",
            "var(--color-warn)",
            "var(--color-danger)",
        ]

    cx = cy = size / 2
    r_outer = size / 2 - 4
    r_inner = r_outer * 0.55

    # Build the donut using SVG arcs
    segments = []
    legend_items = []
    angle = -90  # Start at top
    cumulative = 0.0

    import math

    for i, (name, v) in enumerate(values):
        fraction = v / total
        sweep = fraction * 360
        end_angle = angle + sweep
        cumulative += sweep

        # Compute arc endpoints
        a1 = math.radians(angle)
        a2 = math.radians(end_angle)

        x1_outer = cx + r_outer * math.cos(a1)
        y1_outer = cy + r_outer * math.sin(a1)
        x2_outer = cx + r_outer * math.cos(a2)
        y2_outer = cy + r_outer * math.sin(a2)
        x1_inner = cx + r_inner * math.cos(a1)
        y1_inner = cy + r_inner * math.sin(a1)
        x2_inner = cx + r_inner * math.cos(a2)
        y2_inner = cy + r_inner * math.sin(a2)

        # For arcs > 180° we need the large-arc flag
        large_arc = 1 if sweep > 180 else 0

        color = colors[i % len(colors)]
        path = (
            f"M {x1_outer:.2f} {y1_outer:.2f} "
            f"A {r_outer:.2f} {r_outer:.2f} 0 {large_arc} 1 {x2_outer:.2f} {y2_outer:.2f} "
            f"L {x2_inner:.2f} {y2_inner:.2f} "
            f"A {r_inner:.2f} {r_inner:.2f} 0 {large_arc} 0 {x1_inner:.2f} {y1_inner:.2f} Z"
        )

        segments.append(
            f'<path d="{path}" fill="{color}"><title>{_esc(name)}: {int(v):,} '
            f"({fraction * 100:.1f}%)</title></path>"
        )

        legend_items.append(
            f'<div class="legend-item">'
            f'<span class="legend-swatch" style="background:{color}"></span>'
            f'<span class="legend-label">{_esc(name)}</span>'
            f'<span class="legend-value">{fraction * 100:.1f}%</span>'
            f"</div>"
        )

        angle = end_angle

    # Center text
    center_label = label or f"{int(total):,}"

    aria = f' role="img" aria-label="{_esc(label or "donut chart")}"' if label else ' role="img"'
    return (
        f'<div class="donut-wrap">'
        f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}"{aria}>'
        f"<title>{_esc(label or 'Donut')}</title>"
        f'<circle cx="{cx}" cy="{cy}" r="{r_inner}" fill="var(--color-surface)"/>'
        + "".join(segments)
        + f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" '
        f'font-size="14" font-weight="600" fill="var(--color-text)">{_esc(center_label)}</text>'
        + "</svg>"
        + '<div class="legend">'
        + "".join(legend_items)
        + "</div>"
        + "</div>"
    )


def fmt_short_date(dt: datetime) -> str:
    """Format a date as 'DD/MM' for chart x-axis labels."""
    return dt.strftime("%d/%m")
