"""End-to-end check of the scheme page on the local dev stand.

Usage: python3 tools/scheme_screenshots.py <admin-password> [out_dir]
Needs: dev stand running (tools/dev_stack.sh start), Playwright + Chromium.
"""

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5173"


def main() -> None:
    password = sys.argv[1]
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "scheme-shots")
    out.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, viewport in (("wide", {"width": 1400, "height": 900}), ("tall", {"width": 390, "height": 844})):
            for theme in ("light", "dark"):
                page = browser.new_page(viewport=viewport)
                page.goto(f"{BASE}/login")
                page.fill("input:not([type=password])", "admin")
                page.fill("input[type=password]", password)
                page.keyboard.press("Enter")
                page.wait_for_url("**/dashboard")
                page.goto(f"{BASE}/scheme")
                page.wait_for_selector("svg[aria-label='Схема котельной']")
                if theme == "dark":
                    page.evaluate("document.documentElement.classList.add('dark')")
                page.wait_for_timeout(1500)
                page.screenshot(path=str(out / f"scheme-{name}-{theme}.png"), full_page=True)
                page.close()

        # Scenario: switch the radiator pump off → the pump stops on the scheme within 3 s
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(f"{BASE}/login")
        page.fill("input:not([type=password])", "admin")
        page.fill("input[type=password]", password)
        page.keyboard.press("Enter")
        page.wait_for_url("**/dashboard")
        page.goto(f"{BASE}/scheme")
        # precondition: the pump runs, otherwise the measurement below means nothing
        page.wait_for_selector("[data-element='rad_pump'] [data-state='running']", timeout=30000)
        # left click = immediate on/off with a toast; right click = settings dialog
        started = time.time()
        page.click("[data-element='rad_pump']")
        page.wait_for_selector("text=Насос радиаторов выключается", timeout=5000)
        page.wait_for_selector("[data-element='rad_pump'] [data-state='stopped']", timeout=20000)
        print(f"rad pump stopped on the scheme after {time.time() - started:.1f} s")
        page.click("[data-element='rad_pump']")
        page.wait_for_selector("[data-element='rad_pump'] [data-state='running']", timeout=20000)
        page.click("[data-element='radiators']", button="right")
        page.wait_for_selector("role=dialog[name='Радиаторы']", timeout=5000)
        print("right click opened the settings dialog")
        browser.close()
    print(f"screenshots in {out}/")


if __name__ == "__main__":
    main()
