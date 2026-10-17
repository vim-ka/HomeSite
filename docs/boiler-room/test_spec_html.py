"""Tests for spec_html.py — run: python3 -m pytest docs/boiler-room -q"""

import xml.etree.ElementTree as ET
from pathlib import Path

from check_docs import check, parse_spec
from spec_html import render

SPEC = Path(__file__).with_name("03-specification.md").read_text(encoding="utf-8")


def rows(html: str):
    body = html[html.index("<section>"):html.rindex("</section>") + len("</section>")]
    return ET.fromstring(f"<root>{body}</root>").iter("tr")


def test_every_position_becomes_a_row_with_its_status():
    html = render(SPEC)
    spec = parse_spec(SPEC)
    got = {tr.get("data-pos"): tr.get("data-status") for tr in rows(html) if tr.get("data-pos")}
    assert set(got) == set(spec)
    assert set(got.values()) <= {"есть", "купить", "уточнить"}


def test_summary_counts_match_the_rows():
    html = render(SPEC)
    statuses = [tr.get("data-status") for tr in rows(html) if tr.get("data-pos")]
    for status in ("есть", "купить", "уточнить"):
        assert f'data-count="{status}">{statuses.count(status)}<' in html


def test_markdown_emphasis_and_code_are_rendered_and_text_is_escaped():
    html = render("## Оборудование\n\n| Поз. | Обозн. | Наименование и характеристика | Тип, марка | Кол. | Ед. | Статус | Примечание |\n"
                  "|---|---|---|---|---|---|---|---|\n| 1 | A1 | Бак **24 л** <b>x</b> `calc.py` | — | 1 | шт. | купить | |\n")
    assert "<strong>24 л</strong>" in html and "<code>calc.py</code>" in html
    assert "&lt;b&gt;x&lt;/b&gt;" in html


def test_check_docs_flags_a_stale_html(tmp_path):
    from test_check_docs import make
    d, pinout = make(tmp_path)
    (d / "03-specification.html").write_text("<html>old</html>", encoding="utf-8")
    assert any("03-specification.html" in e for e in check(d, pinout))
