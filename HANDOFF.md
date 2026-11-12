# TrackGate: technical handoff

Read this before changing anything. Live at https://vahit19.github.io/trackgate/ (GitHub Pages) and https://vahitferyad.com/trackgate/ (own server).

## Pieces
- `panel/template.html` is the single source of the app (overview, games, review queue, acceptance gate, reports, data sources, docked AI analyst). `python scripts/build_panel.py` writes `panel/index.html` (Claude artifact version) and `deploy/site/index.html` (complete page for Pages and the server), embedding `results/worldcup/*.json` and `panel/recorded_runs.json`.
- Pushing to `master` deploys `deploy/site/` to GitHub Pages (`.github/workflows/pages.yml`). CI (`ci.yml`) re-runs the tests and checks the README table.
- `deploy/trackgate_api.py` (standard library only) relays the analyst's chat to OpenRouter and appends page events to `/data/events.jsonl`. It runs as container `trackgate-api` on 127.0.0.1:8095 under `/opt/trackgate`; nginx proxies `/trackgate/api/`. The key lives only in `/opt/trackgate/.env` on the server.
- `deploy/deploy_trackgate.sh` installs or updates everything (backup, container, page, nginx location, before/after check of every site on the box, reload only). `deploy/visits.sh [days]` summarises the event log.
- `video/make_video.py` builds the 74-second tour (`video/requirements.txt`).
- `scripts/record_runs.py` records real agent runs for the suggested questions; the page replays them when a viewer's network cannot reach the live agent (`?demo=recorded` shows this mode).

## Agent behaviour
The analyst works the app through its own tools (`list_games`, `game_detail`, `simulate_gate`, `set_gate`, `open_game`, `show_moment`, `review_status`, `acceptance_report`) and every number in its answer is checked against the data before it is shown. Rules are general, never per question: copy figures exactly as tools return them, take extremes from `simulate_gate` (`lowest`/`highest`), open one screen per answer, retry on tool errors, one quiet retry on provider errors. `?ask=<question>` opens the app and asks that question.

## Checks before any release
1. `python -m unittest discover -s tests -t .`
2. Build, then open both URLs in a real browser as a visitor: every screen, the tour video, and at least three analyst questions (numbers must show "checked against the data").
3. Recorded mode: open `?demo=recorded&ask=<a suggested question>`.
