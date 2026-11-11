"""Builds the TrackGate tour video: Microsoft neural voice-over, title and end cards, and a real screen
recording of the app (deploy/site/index.html) driven by Playwright, with the analyst answering live
through a local copy of the analyst API (deploy/trackgate_api.py on localhost:8095).
Output: deploy/site/trackgate-tour.mp4.  Needs: edge-tts, playwright, pillow, imageio-ffmpeg."""
import asyncio
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

import edge_tts
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "video", "build")
PAGE = os.path.join(ROOT, "deploy", "site", "index.html")
FINAL = os.path.join(ROOT, "deploy", "site", "trackgate-tour.mp4")
FF = imageio_ffmpeg.get_ffmpeg_exe()
W, H = 1600, 900
VOICE = "en-US-AndrewNeural"
FONT_B = "C:/Windows/Fonts/segoeuib.ttf"
FONT_R = "C:/Windows/Fonts/segoeui.ttf"

SCENES = [
    ("hook", "Two tracking providers. The same World Cup games. The same player, at the same moment, more than five metres apart, thirteen percent of the time.", None),
    ("overview", "Leagues are moving tracking data toward officiating. The NHL has said it will not roll it out until it is a hundred percent confident the data is accurate. TrackGate is that acceptance test.", "The acceptance test for tracking data"),
    ("games", "It lines up two feeds of the same games, fits each feed's clock and orientation from the data, and measures how far apart they are, game by game, with confidence intervals. Where the provider says a position is estimated, almost half are more than five metres off.", "Two feeds, matched player by player"),
    ("review", "The worst moments go to a review queue. A person opens that second of video and records which feed is right. Every decision goes into the report.", "People decide which feed is right"),
    ("analyst", "An AI analyst does the legwork. It reads the games, opens the worst moment, and answers in plain words. Every number it states is checked against the data.", "An AI analyst that works the app"),
    ("gate", "Set the pass mark, and the verdict updates for every game. On ten World Cup games, none pass at five percent, and six still fail at ten.", "Your pass mark, every game"),
    ("end", "TrackGate runs inside your network, on your own feeds: optical against chip, automated stats against human operators. Pilot it on your data.", None),
]


def dur(path):
    out = subprocess.run([FF, "-i", path], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


async def voice():
    d = {}
    for key, text, _ in SCENES:
        p = os.path.join(OUT, f"{key}.mp3")
        for attempt in range(4):  # the TTS service drops a request now and then
            try:
                await edge_tts.Communicate(text, VOICE, rate="+4%").save(p)
                break
            except edge_tts.exceptions.NoAudioReceived:
                if attempt == 3:
                    raise
                await asyncio.sleep(2)
        d[key] = dur(p)
    return d


def font(path, size):
    return ImageFont.truetype(path, size)


def backdrop():
    im = Image.new("RGB", (W, H), (5, 9, 14))
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    g = ImageDraw.Draw(glow)
    g.ellipse((-300, -380, 700, 520), fill=(16, 120, 90))
    g.ellipse((1000, -300, 1900, 500), fill=(30, 70, 140))
    g.ellipse((500, 520, 1300, 1300), fill=(60, 36, 120))
    glow = glow.filter(ImageFilter.GaussianBlur(160))
    im = Image.blend(im, glow, 0.55)
    d = ImageDraw.Draw(im)
    c = (40, 70, 70)
    d.rectangle((120, 110, W - 120, H - 110), outline=c, width=2)
    d.line((W // 2, 110, W // 2, H - 110), fill=c, width=2)
    d.ellipse((W // 2 - 110, H // 2 - 110, W // 2 + 110, H // 2 + 110), outline=c, width=2)
    return im


def logo(d, x, y, s=1.0):
    r = int(26 * s)
    d.rounded_rectangle((x, y, x + 2 * r, y + 2 * r), radius=int(9 * s), fill=(31, 210, 155))
    cx, cy = x + r, y + r
    d.ellipse((cx - 13 * s, cy - 13 * s, cx + 13 * s, cy + 13 * s), outline=(4, 19, 14), width=int(4 * s))
    d.line((cx, cy - 13 * s, cx, cy + 13 * s), fill=(4, 19, 14), width=int(4 * s))
    d.line((cx - 13 * s, cy, cx + 13 * s, cy), fill=(4, 19, 14), width=int(4 * s))
    d.text((x + 2 * r + 14, y + r), "TRACKGATE", font=font(FONT_B, int(30 * s)), fill=(234, 242, 247), anchor="lm")


def card_hook(path):
    im = backdrop()
    d = ImageDraw.Draw(im)
    logo(d, 150, 140)
    d.text((150, 300), "Same player. Same moment.", font=font(FONT_B, 76), fill=(234, 242, 247))
    d.text((150, 395), "Two providers, metres apart.", font=font(FONT_B, 76), fill=(255, 90, 106))
    stats = [("455,579", "player positions compared"), ("13.1%", "more than 5 m apart"), ("48.8%", "when PFF says 'estimated'")]
    for i, (v, l) in enumerate(stats):
        x = 150 + i * 430
        d.rounded_rectangle((x, 540, x + 400, 690), radius=18, fill=(14, 24, 32), outline=(60, 90, 100), width=2)
        d.text((x + 26, 560), v, font=font(FONT_B, 56), fill=(255, 181, 71) if i else (234, 242, 247))
        d.text((x + 26, 640), l, font=font(FONT_R, 24), fill=(147, 167, 180))
    d.text((150, 745), "2022 FIFA World Cup · PFF FC broadcast tracking vs StatsBomb 360 · 10 games", font=font(FONT_R, 24), fill=(95, 115, 130))
    im.save(path)


def card_end(path):
    im = backdrop()
    d = ImageDraw.Draw(im)
    logo(d, 150, 160, 1.3)
    d.text((150, 300), "Acceptance tests for tracking data.", font=font(FONT_B, 64), fill=(234, 242, 247))
    d.text((150, 385), "Runs inside your network, on your own feeds.", font=font(FONT_R, 36), fill=(147, 167, 180))
    rows = [("Open the app", "vahit19.github.io/trackgate"), ("Pilot on your data", "vahit.feryat@gmail.com")]
    for i, (k, v) in enumerate(rows):
        y = 500 + i * 100
        d.text((150, y), k, font=font(FONT_R, 26), fill=(95, 115, 130))
        d.text((480, y - 6), v, font=font(FONT_B, 40), fill=(31, 210, 155) if i == 0 else (108, 196, 255))
    d.text((150, 740), "Vahit Feryad, PhD · vahitferyad.com", font=font(FONT_R, 24), fill=(95, 115, 130))
    im.save(path)


def caption(path, text):
    f = font(FONT_B, 30)
    tw = int(f.getlength(text))
    im = Image.new("RGBA", (tw + 70, 66), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, tw + 69, 65), radius=16, fill=(6, 14, 20, 225), outline=(31, 210, 155, 255), width=2)
    d.ellipse((22, 27, 34, 39), fill=(31, 210, 155, 255))
    d.text((48, 33), text, font=f, fill=(234, 242, 247, 255), anchor="lm")
    im.save(path)


CURSOR = """
(() => { const c = document.createElement('div'); c.id = 'fakecursor';
  c.style.cssText = 'position:fixed;z-index:99999;left:0;top:0;width:22px;height:22px;pointer-events:none;transform:translate(-3px,-2px);transition:transform .05s';
  c.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24"><path d="M3 2l7 19 2.6-7.4L20 11z" fill="#fff" stroke="#000" stroke-width="1.4"/></svg>';
  const add = () => document.body && document.body.appendChild(c);
  document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', add) : add();
  addEventListener('mousemove', (e) => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
  addEventListener('mousedown', (e) => { const r = document.createElement('div');
    r.style.cssText = `position:fixed;z-index:99998;left:${e.clientX - 18}px;top:${e.clientY - 18}px;width:36px;height:36px;border-radius:50%;border:2px solid #1fd29b;pointer-events:none;transition:all .45s ease-out;opacity:.9`;
    document.body.appendChild(r); requestAnimationFrame(() => { r.style.transform = 'scale(1.8)'; r.style.opacity = '0'; }); setTimeout(() => r.remove(), 500); }, true); })();
"""


async def record(d):
    marks = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")  # the installed Chrome; no browser download
        ctx = await b.new_context(viewport={"width": W, "height": H})
        await ctx.add_init_script(CURSOR)

        async def relay(route):
            req = route.request
            url = "http://127.0.0.1:8095/trackgate/api/" + req.url.split("/trackgate/api/")[1]
            r = urllib.request.Request(url, data=req.post_data_buffer if req.method == "POST" else None, method=req.method, headers={"Content-Type": "text/plain"})
            body = await asyncio.to_thread(lambda: urllib.request.urlopen(r, timeout=90).read())
            await route.fulfill(status=200, body=body, headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"})
        await ctx.route("**/trackgate/api/**", relay)
        page = await ctx.new_page()
        # Chrome's own screencast: a JPEG per repainted frame with its timestamp (no Playwright ffmpeg needed)
        frames, fdir = [], os.path.join(OUT, "frames")
        os.makedirs(fdir, exist_ok=True)
        for f in os.listdir(fdir):
            os.remove(os.path.join(fdir, f))
        cdp = await ctx.new_cdp_session(page)

        def on_frame(ev):
            fp = os.path.join(fdir, f"{len(frames):06d}.jpg")
            open(fp, "wb").write(__import__("base64").b64decode(ev["data"]))
            frames.append((ev["metadata"]["timestamp"], fp))
            asyncio.ensure_future(cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]}))
        cdp.on("Page.screencastFrame", on_frame)
        await cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 85, "maxWidth": W, "maxHeight": H, "everyNthFrame": 1})
        t0 = time.time()
        await page.goto("file:///" + PAGE.replace("\\", "/"))
        await page.wait_for_function("document.getElementById('agentState').textContent.startsWith('Online')", timeout=20000)
        await page.wait_for_timeout(1500)
        m = page.mouse

        async def move(sel, steps=25, click=True, nth=0):
            box = await page.locator(sel).nth(nth).bounding_box()
            await m.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=steps)
            if click:
                await page.wait_for_timeout(150)
                await m.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)

        async def scene(key, fn, nav=None):
            if nav:  # switch screens first, so each cut opens on its own screen
                await move(f".side a[data-v={nav}]", steps=12)
                await page.locator("#main").evaluate("e => e.scrollTop = 0")
                await page.wait_for_timeout(350)
            marks[key] = time.time() - t0
            start = time.time()
            await fn()
            left = d[key] + 0.4 - (time.time() - start)
            if left > 0:
                await page.wait_for_timeout(int(left * 1000))
            marks[key + "_end"] = time.time() - t0

        async def overview():
            await m.move(700, 300, steps=10)
            await page.wait_for_timeout(1200)
            await move("#dBanner", click=False)
            await page.wait_for_timeout(1800)
            await move("#dKpis .kpi >> nth=2", click=False)
            await page.wait_for_timeout(1500)
            await move("#dBars .brow", click=False)
            await page.wait_for_timeout(1200)
            await move("#dPitch", click=False)

        async def games():
            await page.wait_for_timeout(1200)
            await move("#gBody tr", nth=1)
            await page.wait_for_timeout(1200)
            await page.locator("#gdHist").scroll_into_view_if_needed()
            await move("#gdHist", click=False)
            await page.wait_for_timeout(2200)
            await move("#gdSplit", click=False)

        async def review():
            await page.wait_for_timeout(1300)
            await move("#rDec .dbtn >> nth=0")
            await page.wait_for_timeout(1300)
            await move("#rDec .dbtn >> nth=3")
            await page.wait_for_timeout(1300)
            await move("#rDec .dbtn >> nth=1")
            await page.wait_for_timeout(900)
            await move("#rVideo", click=False)

        async def analyst():
            await move("#qs .qbtn >> nth=0")
            await page.wait_for_function("document.querySelectorAll('#msgs .meta.ok, #msgs .meta.bad').length > 0", timeout=60000)
            await page.wait_for_timeout(1200)
            await move("#msgs .msg.from-bot .bub", click=False)

        async def gate():
            await page.wait_for_timeout(700)
            await page.evaluate("() => { const s = document.getElementById('limit'); s.value = 5; s.dispatchEvent(new Event('input')); }")
            box = await page.locator("#limit").bounding_box()
            x0 = box["x"] + box["width"] * (4 / 59)
            await m.move(x0, box["y"] + box["height"] / 2, steps=20)
            await m.down()
            for i in range(30):
                await m.move(x0 + (box["width"] * (5 / 59)) * (i + 1) / 30, box["y"] + box["height"] / 2)
                await page.wait_for_timeout(55)
            await m.up()
            await page.evaluate("() => { const s = document.getElementById('limit'); s.value = 10; s.dispatchEvent(new Event('input')); }")
            await page.wait_for_timeout(800)
            await move("#gtPass", click=False)

        for key, fn, nav in [("overview", overview, None), ("games", games, "games"), ("review", review, "review"), ("analyst", analyst, "dashboard"), ("gate", gate, "gates")]:
            await scene(key, fn, nav)
        await page.wait_for_timeout(500)
        await cdp.send("Page.stopScreencast")
        await ctx.close()
        await b.close()
    # frames arrive only when the page repaints: hold each one until the next, then resample to 30 fps
    lst = os.path.join(OUT, "frames.txt")
    with open(lst, "w") as f:
        for i, (t, fp) in enumerate(frames):
            nxt = frames[i + 1][0] if i + 1 < len(frames) else t + 0.5
            f.write("file '%s'\nduration %.4f\n" % (fp.replace(os.sep, "/"), max(0.001, nxt - t)))
        f.write("file '%s'\n" % frames[-1][1].replace(os.sep, "/"))
    screen = os.path.join(OUT, "screen.mp4")
    run(["-f", "concat", "-safe", "0", "-i", lst, "-vf", f"scale={W}:{H},fps=30", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", screen])
    off = frames[0][0] - t0  # the screen video starts at the first frame
    return screen, {k: max(0.0, v - off) for k, v in marks.items()}


def run(args):
    subprocess.run([FF, "-y", "-loglevel", "error", *args], check=True)


def build(d, webm, marks):
    parts = []
    enc = ["-c:v", "libx264", "-preset", "medium", "-crf", "24", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "128k", "-ar", "44100"]
    for key, text, cap in SCENES:
        a = os.path.join(OUT, f"{key}.mp3")
        seg = os.path.join(OUT, f"seg_{key}.mp4")
        L = d[key] + 0.5
        fade = f"fade=t=in:st=0:d=0.35,fade=t=out:st={L - 0.35:.2f}:d=0.35"
        if cap is None:
            png = os.path.join(OUT, f"{key}.png")
            (card_hook if key == "hook" else card_end)(png)
            run(["-loop", "1", "-t", f"{L:.2f}", "-i", png, "-i", a, "-filter_complex",
                 f"[0:v]scale={W}:{H},zoompan=z='min(zoom+0.0006,1.06)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps=30,{fade}[v];[1:a]apad[a]",
                 "-map", "[v]", "-map", "[a]", "-t", f"{L:.2f}", *enc, seg])
        else:
            cp = os.path.join(OUT, f"cap_{key}.png")
            caption(cp, cap)
            run(["-ss", f"{marks[key]:.2f}", "-t", f"{L:.2f}", "-i", webm, "-i", cp, "-i", a, "-filter_complex",
                 f"[0:v]scale={W}:{H},setpts=PTS-STARTPTS[b];[b][1:v]overlay=40:H-h-40:enable='gte(t,0.3)',{fade}[v];[2:a]apad[a]",
                 "-map", "[v]", "-map", "[a]", "-t", f"{L:.2f}", *enc, seg])
        parts.append(seg)
    lst = os.path.join(OUT, "list.txt")
    open(lst, "w").write("".join(f"file '{p.replace(os.sep, '/')}'\n" for p in parts))
    run(["-f", "concat", "-safe", "0", "-i", lst, "-c:v", "libx264", "-crf", "25", "-preset", "slow", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", FINAL])
    run(["-ss", "1.5", "-i", parts[0], "-frames:v", "1", "-q:v", "3", os.path.join(ROOT, "deploy", "site", "trackgate-tour.jpg")])


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    d = asyncio.run(voice())
    print("voice", json.dumps({k: round(v, 1) for k, v in d.items()}), "total", round(sum(d.values()), 1))
    if "--voice-only" in sys.argv:
        sys.exit()
    webm, marks = asyncio.run(record(d))
    print("recorded", webm, {k: round(v, 1) for k, v in marks.items()})
    build(d, webm, marks)
    print("done", FINAL, round(os.path.getsize(FINAL) / 1e6, 1), "MB", round(dur(FINAL), 1), "s")
