"""Consistency check of the boiler room documentation.

Usage: python3 docs/boiler-room/check_docs.py

- every *.svg is well-formed XML;
- every position (data-pos) and designation (data-ref) on a drawing is in the specification;
- every specification position outside «Материалы» is on at least one drawing;
- the relay table in 07-wiring.md matches the relay table in firmware PINOUT.md (channel → GPIO);
- key numbers from calc.py appear in the specification.
"""

import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
PINOUT = HERE.parents[1] / "firmware" / "esp32-homesite" / "PINOUT.md"
# calc.py --json keys whose values the specification must quote
SPEC_CALC_KEYS = ("dn_boiler", "dn_rad", "dn_floor", "dn_ihb", "exp_heating_l", "exp_dhw_l")


def _rows(text: str):
    """Table rows as lists of stripped cells (header separator rows skipped)."""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("|") and not re.fullmatch(r"\|[\s|:-]+\|", line):
            yield [c.strip() for c in line.strip("|").split("|")]


def parse_spec(text: str) -> dict[str, dict[str, str]]:
    """Position → {ref, section} from the specification tables."""
    out: dict[str, dict[str, str]] = {}
    section = ""
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
        else:
            for cells in _rows(line):
                if cells and cells[0].isdigit():
                    out[cells[0]] = {"ref": cells[1] if len(cells) > 1 else "", "section": section}
    return out


def parse_relays(text: str) -> dict[str, str]:
    """Relay channel → GPIO from a table whose first two columns are «Канал | GPIO»."""
    out: dict[str, str] = {}
    in_table = False
    for cells in _rows(text):
        if cells[:2] == ["Канал", "GPIO"]:
            in_table = True
        elif in_table and cells[0].isdigit() and len(cells) > 1:
            out[cells[0]] = cells[1]
        elif in_table:
            in_table = False
    return out


def svg_refs(text: str) -> tuple[set[str], set[str]]:
    """(positions, designations) referenced by a drawing; raises ET.ParseError on bad XML."""
    root = ET.fromstring(text)
    pos, refs = set(), set()
    for el in root.iter():
        if p := el.get("data-pos"):
            pos.update(p.split())
        if r := el.get("data-ref"):
            refs.update(r.split())
    return pos, refs


def check(folder: Path, pinout: Path, calc: dict | None = None) -> list[str]:
    spec_file = folder / "03-specification.md"
    if not spec_file.exists():
        return ["нет 03-specification.md"]
    spec_text = spec_file.read_text(encoding="utf-8")
    spec = parse_spec(spec_text)
    spec_refs = {r for v in spec.values() for r in v["ref"].replace(",", " ").split()}
    errors: list[str] = []

    drawn: set[str] = set()
    for svg in sorted(folder.glob("*.svg")):
        try:
            pos, refs = svg_refs(svg.read_text(encoding="utf-8"))
        except ET.ParseError as e:
            errors.append(f"{svg.name}: битый XML ({e})")
            continue
        drawn |= pos
        errors += [f"{svg.name}: поз. {p} нет в спецификации" for p in sorted(pos - spec.keys(), key=int)]
        errors += [f"{svg.name}: {r} нет в спецификации" for r in sorted(refs - spec_refs)]
    for p, v in spec.items():
        if v["section"] != "Материалы" and p not in drawn:
            errors.append(f"поз. {p} ({v['section']}) нет ни на одной схеме")

    wiring = folder / "07-wiring.md"
    if wiring.exists():
        fw = parse_relays(pinout.read_text(encoding="utf-8"))
        for ch, gpio in parse_relays(wiring.read_text(encoding="utf-8")).items():
            if fw.get(ch) != gpio:
                errors.append(f"07-wiring.md: канал {ch} → GPIO {gpio}, а в PINOUT → {fw.get(ch, 'нет канала')}")

    for key, value in (calc or {}).items():
        if str(value) not in spec_text:
            errors.append(f"calc.py {key} = {value} не найдено в спецификации")
    return errors


def main() -> int:
    calc = None
    if (HERE / "calc.py").exists():
        out = subprocess.run([sys.executable, str(HERE / "calc.py"), "--json"], capture_output=True, text=True, check=True)
        data = json.loads(out.stdout)
        calc = {k: data[k] for k in SPEC_CALC_KEYS if k in data}
    errors = check(HERE, PINOUT, calc)
    for e in errors:
        print("ОШИБКА:", e)
    if errors:
        return 1
    spec = parse_spec((HERE / "03-specification.md").read_text(encoding="utf-8"))
    print(f"OK: {len(spec)} позиций, {len(list(HERE.glob('*.svg')))} схем")
    return 0


if __name__ == "__main__":
    sys.exit(main())
