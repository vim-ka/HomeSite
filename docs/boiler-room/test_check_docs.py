"""Tests for check_docs.py — run: python3 -m pytest docs/boiler-room -q"""

from pathlib import Path

import pytest

from check_docs import check, parse_relays, parse_spec, svg_refs

SPEC = """
## Оборудование

| Поз. | Обозн. | Наименование и характеристика | Тип, марка | Кол. | Ед. | Статус | Примечание |
|---|---|---|---|---|---|---|---|
| 1 | | Котёл газовый | пример | 1 | шт. | купить | |
| 2 | M1 | Насос радиаторов | уточнить | 1 | шт. | есть | |

## Материалы

| Поз. | Обозн. | Наименование и характеристика | Тип, марка | Кол. | Ед. | Статус | Примечание |
|---|---|---|---|---|---|---|---|
| 40 | | Труба 28×1,2 | | 10 | м | купить | |
"""

PINOUT = """
## Реле (16-канальный модуль)

| Канал | GPIO | Назначение |
|-------|------|------------|
| 0 | 13 | Котёл (вкл/выкл) |
| 1 | 12 | Насос радиаторов |
"""

WIRING = """
| Канал | GPIO | Обозн. | Нагрузка |
|---|---|---|---|
| 0 | 13 | K0 | Котёл |
| 1 | 12 | M1 | Насос радиаторов |
"""

SVG_OK = '<svg xmlns="http://www.w3.org/2000/svg"><g data-pos="1"/><g data-pos="2" data-ref="M1"/></svg>'


def make(tmp_path: Path, svg: str = SVG_OK, wiring: str = WIRING) -> tuple[Path, Path]:
    d = tmp_path / "boiler-room"
    d.mkdir()
    (d / "03-specification.md").write_text(SPEC, encoding="utf-8")
    (d / "07-wiring.md").write_text(wiring, encoding="utf-8")
    (d / "02-piping.svg").write_text(svg, encoding="utf-8")
    pinout = tmp_path / "PINOUT.md"
    pinout.write_text(PINOUT, encoding="utf-8")
    return d, pinout


def test_parse_spec_reads_positions_refs_and_sections():
    spec = parse_spec(SPEC)
    assert spec["1"] == {"ref": "", "section": "Оборудование"}
    assert spec["2"]["ref"] == "M1"
    assert spec["40"]["section"] == "Материалы"


def test_parse_relays_reads_channel_gpio_pairs():
    assert parse_relays(PINOUT) == {"0": "13", "1": "12"}
    assert parse_relays(WIRING) == {"0": "13", "1": "12"}


def test_svg_refs_collects_positions_and_refs():
    assert svg_refs(SVG_OK) == ({"1", "2"}, {"M1"})


def test_consistent_docs_pass(tmp_path):
    assert check(*make(tmp_path)) == []


def test_position_on_drawing_missing_from_spec(tmp_path):
    errors = check(*make(tmp_path, svg=SVG_OK.replace('data-pos="1"', 'data-pos="7"')))
    assert any("поз. 7" in e and "нет в спецификации" in e for e in errors)
    assert any("поз. 1" in e and "нет ни на одной схеме" in e for e in errors)


def test_materials_need_not_be_drawn(tmp_path):
    assert not any("поз. 40" in e for e in check(*make(tmp_path)))


def test_ref_on_drawing_missing_from_spec(tmp_path):
    errors = check(*make(tmp_path, svg=SVG_OK.replace('data-ref="M1"', 'data-ref="M9"')))
    assert any("M9" in e for e in errors)


def test_relay_gpio_mismatch_with_pinout(tmp_path):
    errors = check(*make(tmp_path, wiring=WIRING.replace("| 1 | 12 |", "| 1 | 14 |")))
    assert any("канал 1" in e and "PINOUT" in e for e in errors)


def test_broken_svg_is_reported_not_raised(tmp_path):
    errors = check(*make(tmp_path, svg="<svg><g></svg>"))
    assert any("02-piping.svg" in e and "XML" in e for e in errors)


def test_missing_spec_is_reported_not_raised(tmp_path):
    d, pinout = make(tmp_path)
    (d / "03-specification.md").unlink()
    assert check(d, pinout) == ["нет 03-specification.md"]


@pytest.mark.parametrize("value", ["35", "300"])
def test_calc_values_must_appear_in_spec(tmp_path, value):
    d, pinout = make(tmp_path)
    errors = check(d, pinout, calc={"dn_boiler": value})
    assert any("dn_boiler" in e for e in errors)
