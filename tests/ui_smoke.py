"""UI smoke test: drive the SPA in the installed Edge, with a throwaway profile.

Needs the runner (`workflow-agent-runner`) and the SPA (`npm run dev` in spa/) running.

    uv run python tests/ui_smoke.py [--out DIR] [--headed]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

SPA = "http://localhost:5173"
TURN_TIMEOUT = 120_000


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("ui-smoke"), help="Folder for screenshots.")
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=not args.headed)
        page = browser.new_page(viewport={"width": 900, "height": 700})
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        page.goto(SPA)
        expect(page.get_by_text("Runner connected")).to_be_visible(timeout=10_000)
        page.screenshot(path=args.out / "1-connected.png")
        print("ok: connected")

        # The runner keeps its session between runs; start clean.
        page.get_by_role("button", name="New chat").click()
        expect(page.get_by_role("button", name="New chat")).to_be_enabled(timeout=30_000)
        expect(page.get_by_text("Ask for help designing a workflow.")).to_be_visible()
        print("ok: started a new chat")

        box = page.get_by_placeholder(re.compile("Message"))
        box.fill("Give me a two-item bullet list of map types, with the type names in bold.")
        box.press("Enter")
        expect(page.get_by_role("progressbar")).to_be_visible(timeout=10_000)
        page.screenshot(path=args.out / "2-working.png")
        print("ok: working bar shown")

        expect(page.get_by_text(re.compile(r"^Last turn: "))).to_be_visible(timeout=TURN_TIMEOUT)
        expect(page.get_by_role("progressbar")).to_be_hidden()
        expect(page.locator("li strong").first).to_be_visible()
        print("ok: reply rendered as markdown:", page.locator("li").all_inner_texts())

        box.fill("Line one\nLine two (sent with Shift+Enter between)")
        box.press("Enter")
        expect(page.get_by_text("Line two (sent with Shift+Enter between)", exact=False).first).to_be_visible()
        expect(page.get_by_role("progressbar")).to_be_hidden(timeout=TURN_TIMEOUT)
        page.screenshot(path=args.out / "3-replied.png")
        print("ok: second turn done:", page.get_by_text(re.compile(r"^Last turn: ")).inner_text())

        other = browser.new_page(viewport={"width": 900, "height": 700})
        other.goto(SPA)
        expect(other.get_by_text("Runner connected")).to_be_visible(timeout=10_000)
        expect(other.get_by_text("Line two (sent with Shift+Enter between)", exact=False).first).to_be_visible()
        bubbles = "div.MuiPaper-root p, div.MuiPaper-root li"
        assert other.locator(bubbles).all_inner_texts() == page.locator(bubbles).all_inner_texts(), "replay differs"
        print(f"ok: a new tab replayed the same {page.locator(bubbles).count()} paragraphs")
        other.close()

        box.fill("Write a 1500-word essay on the history of cartography.")
        box.press("Enter")
        page.get_by_role("button", name="Stop").click(timeout=10_000)
        expect(page.get_by_text("Stopped.", exact=True)).to_be_visible(timeout=10_000)
        expect(page.get_by_role("button", name="Send")).to_be_visible()
        expect(page.get_by_text(re.compile(r"^Last turn: stopped, "))).to_be_visible()
        page.screenshot(path=args.out / "4-stopped.png")
        print("ok: stop button interrupted the turn")

        links_before = page.locator("a[href^='http']").count()
        box.fill("Search the web: what is the newest released Python version? One sentence, with a source link.")
        box.press("Enter")
        expect(page.locator("a[href^='http']")).not_to_have_count(links_before, timeout=TURN_TIMEOUT)
        expect(page.get_by_role("progressbar")).to_be_hidden(timeout=TURN_TIMEOUT)
        page.screenshot(path=args.out / "5-web-search.png")
        print("ok: web search reply has links:", page.locator("a[href^='http']").evaluate_all("els => els.map(e => e.href)"))
        expect(page.locator("a[href^='http']:not([target='_blank'])")).to_have_count(0)
        print("ok: links open in a new tab")

        page.get_by_role("button", name="New chat").click()
        expect(page.get_by_text("Ask for help designing a workflow.")).to_be_visible(timeout=30_000)
        expect(page.get_by_role("button", name="New chat")).to_be_enabled()
        expect(page.get_by_text(re.compile(r"^Last turn: "))).to_have_count(0)
        page.screenshot(path=args.out / "6-new-chat.png")
        print("ok: new chat cleared the conversation")

        print("console errors:", errors or "none")
        browser.close()


if __name__ == "__main__":
    main()
