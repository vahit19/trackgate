"""Records real agent runs for the questions the app suggests on each screen, so the page can replay
them when a viewer's network cannot reach the live agent. Each question is asked on the live app as a
fresh visitor; a run is kept only if every number in the answer passed the app's own check.
Output: panel/recorded_runs.json (then run scripts/build_panel.py).  Needs: playwright."""
import asyncio
import json
import os
import sys
import urllib.parse

from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = sys.argv[1] if len(sys.argv) > 1 else "https://vahitferyad.com/trackgate/"
VIEWS = ["dashboard", "games", "review", "gates"]


async def main():
    runs = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        for view in VIEWS:
            ctx = await b.new_context(viewport={"width": 1400, "height": 800})
            pg = await ctx.new_page()
            await pg.goto(BASE + "#/" + view)
            await pg.wait_for_selector("#qs .qbtn")
            qs = [await x.text_content() for x in await pg.query_selector_all("#qs .qbtn")]
            await ctx.close()
            for q in qs:
                if q in runs:
                    runs[q]["views"].append(view)
                    continue
                for attempt in range(3):
                    ctx = await b.new_context(viewport={"width": 1400, "height": 800})
                    pg = await ctx.new_page()
                    await pg.goto(BASE + "?ask=" + urllib.parse.quote(q) + "#/" + view)
                    await pg.wait_for_function("window.__tgLastRun", timeout=90000)
                    run = await pg.evaluate("window.__tgLastRun")
                    await ctx.close()
                    if run["ok"] and run["calls"]:
                        runs[q] = {"q": q, "views": [view], "calls": run["calls"], "text": run["text"]}
                        print(f"ok   [{view}] {q}  ({len(run['calls'])} tools)")
                        break
                    print(f"retry [{view}] {q}")
                else:
                    print(f"SKIP [{view}] {q}")
        await b.close()
    out = os.path.join(ROOT, "panel", "recorded_runs.json")
    json.dump(list(runs.values()), open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(len(runs), "runs ->", out)


if __name__ == "__main__":
    asyncio.run(main())
