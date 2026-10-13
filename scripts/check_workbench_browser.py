"""Optional real-browser checks for the non-authoritative author prototype.

Requires Playwright and Chromium in a separate developer tool environment.
Does not run participant research or certify WCAG conformance.
"""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, default=ROOT / "target/workbench-browser")
    args = parser.parse_args()
    args.artifacts.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1100}, accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(5000)
        errors = []
        remote_requests = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: remote_requests.append(request.url)
                if request.url.startswith(("http:", "https:")) else None)
        context.set_offline(True)
        page.goto((ROOT / "experiments/meaning-workbench/index.html").as_uri())
        page.keyboard.press("Tab")
        assert page.locator(".skip-link").evaluate("element => element === document.activeElement")
        page.locator("#language-name").focus()
        assert page.locator("#language-name").evaluate(
            "element => getComputedStyle(element).outlineStyle !== 'none'"
        ), "keyboard focus must be visible"
        page.screenshot(path=str(args.artifacts / "desktop.png"), full_page=True)

        page.locator("#language-brief").fill("为河谷城邦创作对白，并希望看出语言的历史。")
        canon = "河口城\n守卫的名字\n<script>window.injected = true</script>"
        page.locator("#canon").fill(canon)
        intentions = "1 | 城市位于河口\n1 | 地名需要保持\n2 | 指一位守卫\n2 | 名字应简短\n3 | 原始材料按字面保留，意义未定"
        page.locator("#canon-intents").fill(intentions)
        choices = {
            "speaker": "speaker", "referent": "known", "number": "one", "source": "seen",
            "time": "yesterday", "completion": "complete", "polarity": "positive", "speechAct": "inform",
        }
        for name, value in choices.items():
            page.locator(f"select[name='{name}']").select_option(value)
        page.locator("input[name='concept'][value='layered']").check()
        page.get_by_role("button", name="整理流程草稿").click()
        assert "确认 8/8" in page.locator("#status").inner_text()
        assert canon in page.locator("#preview").inner_text()
        assert intentions in page.locator("#preview").inner_text()
        assert "记录 5 项关联意图" in page.locator("#status").inner_text()
        assert page.evaluate("window.injected") is None
        with page.expect_download() as download:
            page.get_by_role("button", name="导出 Markdown").click()
        output = args.artifacts / "download.md"
        download.value.save_as(output)
        text = output.read_text(encoding="utf-8")
        assert canon in text and intentions in text and "不是语言手册" in text

        page.locator("#language-brief").fill("已修改的构想")
        assert page.locator("#download").is_disabled(), "editing must invalidate stale export"
        assert page.locator("#preview").is_hidden()
        page.locator("select[name='source']").select_option("reported")
        page.get_by_role("button", name="整理流程草稿").click()
        assert "需要澄清" in page.locator("#preview").inner_text()

        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.screenshot(path=str(args.artifacts / "mobile.png"), full_page=True)
        # 720 CSS px approximates the reflow width of a 1440 px window at 200%.
        page.set_viewport_size({"width": 720, "height": 550})
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert page.locator("#download").is_enabled()
        page.screenshot(path=str(args.artifacts / "reflow-720.png"), full_page=True)
        assert not errors, errors
        assert not remote_requests, remote_requests
        browser.close()
    print("Workbench browser checks passed: offline, export, invalidation, focus, 390/720px reflow.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
