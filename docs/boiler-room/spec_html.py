"""HTML version of the specification, generated from 03-specification.md (the source of truth).

Usage: python3 docs/boiler-room/spec_html.py   → writes 03-specification.html
check_docs.py reports the HTML as stale when it no longer matches the Markdown.
"""

import re
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATUSES = ("купить", "уточнить", "есть")


def inline(md: str) -> str:
    """Escape, then the few Markdown marks the specification uses: **bold**, `code`."""
    s = escape(md, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", s)


def parse(md: str):
    """(title, intro paragraphs, [(section, header cells, rows)])."""
    title, intro, sections = "", [], []
    para: list[str] = []
    for raw in md.splitlines():
        line = raw.strip()
        if line.startswith("# "):
            title = line[2:]
        elif line.startswith("## "):
            sections.append((line[3:], [], []))
        elif line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if re.fullmatch(r"[\s|:-]+", line):
                continue
            if not sections[-1][1]:
                sections[-1][1].extend(cells)
            else:
                sections[-1][2].append(cells)
        elif not sections:
            if line:
                para.append(line)
            elif para:
                intro.append(" ".join(para))
                para = []
    if para:
        intro.append(" ".join(para))
    return title, intro, sections


def render(md: str) -> str:
    title, intro, sections = parse(md)
    counts = {s: 0 for s in STATUSES}
    tables = []
    for name, head, rows in sections:
        st = head.index("Статус") if "Статус" in head else -1
        trs = []
        for cells in rows:
            status = cells[st] if st >= 0 else ""
            if status in counts:
                counts[status] += 1
            tds = "".join(
                f'<td><span class="chip" data-s="{escape(c)}">{escape(c)}</span></td>' if i == st
                else f'<td>{inline(c)}</td>' for i, c in enumerate(cells))
            trs.append(f'<tr data-pos="{escape(cells[0])}" data-status="{escape(status)}">{tds}</tr>')
        ths = "".join(f"<th>{escape(h)}</th>" for h in head)
        tables.append(f'<section><h2>{escape(name)}</h2><div class="scroll"><table>'
                      f'<thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table></div></section>')
    total = sum(counts.values())
    summary = "".join(
        f'<button type="button" class="filter" data-filter="{s}"><span class="chip" data-s="{s}">{s}</span>'
        f' <b data-count="{s}">{counts[s]}</b></button>' for s in STATUSES)
    intro_html = "".join(f"<p>{inline(p)}</p>" for p in intro)
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Спецификация котельной</title>
<style>
:root {{
  --bg: #ffffff; --fg: #1f2937; --muted: #6b7280; --line: #e5e7eb; --head: #f3f4f6; --accent: #b91c1c;
  --buy-bg: #fee2e2; --buy-fg: #991b1b; --check-bg: #fef3c7; --check-fg: #92400e; --have-bg: #dcfce7; --have-fg: #166534;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #111827; --fg: #e5e7eb; --muted: #9ca3af; --line: #374151; --head: #1f2937; --accent: #f87171;
    --buy-bg: #7f1d1d; --buy-fg: #fecaca; --check-bg: #78350f; --check-fg: #fde68a; --have-bg: #14532d; --have-fg: #bbf7d0;
  }}
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--fg);
       font: 14px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif; }}
main {{ max-width: 1280px; margin: 0 auto; padding: 24px 16px 48px; }}
h1 {{ font-size: 22px; margin: 0 0 8px; }}
h2 {{ font-size: 17px; margin: 28px 0 8px; }}
p {{ color: var(--muted); max-width: 90ch; margin: 0 0 8px; }}
code {{ font: 12px ui-monospace, SFMono-Regular, Consolas, monospace; background: var(--head); padding: 1px 4px; border-radius: 3px; }}
.bar {{ position: sticky; top: 0; z-index: 1; background: var(--bg); display: flex; flex-wrap: wrap; gap: 8px;
        align-items: center; padding: 10px 0; border-bottom: 1px solid var(--line); }}
.filter {{ font: inherit; color: inherit; background: var(--bg); border: 1px solid var(--line); border-radius: 999px;
           padding: 4px 10px; cursor: pointer; }}
.filter[aria-pressed="true"] {{ border-color: var(--fg); }}
.bar .total {{ color: var(--muted); margin-left: auto; }}
.scroll {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ text-align: left; vertical-align: top; padding: 6px 8px; border-bottom: 1px solid var(--line); }}
th {{ background: var(--head); font-weight: 600; white-space: nowrap; position: sticky; top: 0; }}
td:nth-child(1), td:nth-child(5), td:nth-child(6) {{ white-space: nowrap; }}
td:nth-child(2) {{ font-weight: 600; }}
td:nth-child(3) {{ min-width: 320px; }}
.chip {{ display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; white-space: nowrap; }}
.chip[data-s="купить"] {{ background: var(--buy-bg); color: var(--buy-fg); }}
.chip[data-s="уточнить"] {{ background: var(--check-bg); color: var(--check-fg); }}
.chip[data-s="есть"] {{ background: var(--have-bg); color: var(--have-fg); }}
tr.hidden, section.hidden {{ display: none; }}
@media print {{
  @page {{ size: A4 landscape; margin: 10mm; }}
  :root {{ --bg: #fff; --fg: #000; --muted: #333; --line: #bbb; --head: #eee; }}
  body {{ font-size: 10px; }}
  .bar button, .bar .total {{ display: none; }}
  th {{ position: static; }}
  tr {{ break-inside: avoid; }}
}}
</style>
</head>
<body>
<main>
<h1>{escape(title)}</h1>
{intro_html}
<div class="bar">{summary}<button type="button" class="filter" data-filter="" aria-pressed="true">все</button>
<span class="total">позиций: {total} · сгенерировано из 03-specification.md</span></div>
{"".join(tables)}
</main>
<script>
document.querySelectorAll(".filter").forEach((b) => b.addEventListener("click", () => {{
  const f = b.dataset.filter;
  document.querySelectorAll(".filter").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
  document.querySelectorAll("tbody tr").forEach((tr) => tr.classList.toggle("hidden", !!f && tr.dataset.status !== f));
  document.querySelectorAll("section").forEach((s) => s.classList.toggle("hidden", !s.querySelector("tbody tr:not(.hidden)")));
}}));
</script>
</body>
</html>
"""


def main() -> None:
    md = (HERE / "03-specification.md").read_text(encoding="utf-8")
    (HERE / "03-specification.html").write_text(render(md), encoding="utf-8")


if __name__ == "__main__":
    main()
