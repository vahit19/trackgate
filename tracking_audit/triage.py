"""Triage queue and report narration.

The queue is pure code: the events where the two feeds disagree most, each
with a link to the exact second in PFF's film room so a person can look at
the broadcast and decide which feed is right.

Narration uses an LLM (OpenRouter, OpenAI-compatible) to turn the computed
facts into a short report. Every number in the generated text must appear in
the facts (within rounding); otherwise the text is rejected and the plain
code-generated summary is used instead.
"""
import json
import os
import re
import urllib.request

NUM = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])")


def queue(moments, video_url, period_starts, top=15):
    """Worst events first. period_starts: {period: video seconds at kick-off}."""
    ranked = sorted(moments, key=lambda m: (-m["median_m"], -m["max_m"]))[:top]
    out = []
    for m in ranked:
        link = None
        if video_url and m["period"] in period_starts:
            link = f'{video_url.rstrip("/")}/{period_starts[m["period"]] + m["pff_period_t"]:.3f}'
        out.append({**m, "video": link})
    return out


def _numbers(obj, acc):
    if isinstance(obj, dict):
        for v in obj.values():
            _numbers(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _numbers(v, acc)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        acc.add(float(obj))
        if 0 <= obj <= 1:
            acc.add(float(obj) * 100)  # rates may be written as percentages
    elif isinstance(obj, str):
        for n in NUM.findall(obj):
            acc.add(float(n))


def numbers_supported(text, facts, tol=0.051):
    allowed = set()
    _numbers(facts, allowed)
    bad = []
    for n in NUM.findall(text):
        x = float(n)
        if x in (1, 2, 5, 90, 95, 2022):  # thresholds and labels used by the report itself
            continue
        if not any(abs(x - a) <= tol * max(1.0, abs(a)) for a in allowed):
            bad.append(n)
    return bad


def narrate(facts, api_key=None, model=None, fetch=urllib.request.urlopen):
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
    model = model or os.environ.get("LLM_MODEL", "anthropic/claude-haiku-5.5")
    if not api_key:
        return None, ["no OPENROUTER_API_KEY"]
    prompt = (
        "Write a short acceptance-test note (max 180 words, plain English, no headings) for a sports data buyer. "
        "Explain how far two tracking providers disagree on the same broadcast moments, and what the PFF "
        "'ESTIMATED' flag means for reliability. Use only numbers that appear in the JSON, rounded to one decimal "
        "place or as percentages. Do not speculate about causes beyond occlusion or camera framing.\n\n"
        + json.dumps(facts)
    )
    body = json.dumps({"model": model, "temperature": 0.1, "max_tokens": 400,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body, headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "X-Title": "tracking-audit"})
    with fetch(req, timeout=60) as r:
        text = json.loads(r.read())["choices"][0]["message"]["content"].strip()
    bad = numbers_supported(text, facts)
    return (text if not bad else None), bad
