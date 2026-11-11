# TrackGate (tracking-audit)

**Acceptance tests for sports tracking data, before it is trusted for officiating, betting or broadcast.**

On 455,579 player positions from 10 games of the 2022 FIFA World Cup, two commercial tracking providers (PFF FC
broadcast tracking and StatsBomb 360) put the same player at the same moment **more than 5 m apart 13.1% of the
time**, and **48.8% of the time when PFF flags the position as estimated** while the player is on screen. With every
event allowed to shift up to ±1 s to its best-agreeing moment, not one of the 10 games passes a "no more than 5% of
positions over 5 m" gate.

Leagues are moving optical tracking toward decisions. The NHL's Sean Ellis (VP, Hockey Operations) on using
tracking for officiating: *"Not currently, but that's definitely where we're going… We're not going to roll it out
until we're 100% confident… the data… is accurate."* ([SBJ, Nov 2025](https://smt.com/live-from-toronto-inside-the-nhls-high-tech-situation-room-11-14-25/)).
Dave Lehanski (EVP): *"We've used this season mostly to validate the data from arena to arena"*
([SVG, Jun 2025](https://www.sportsvideo.org/2025/06/04/svg-sit-down-nhl-sony-execs-dive-deeper-into-new-technology-partnership-involving-beyond-sports-hawk-eye-and-more/)).
This repository is that validation step as software: it measures, with confidence intervals, how far two
sources of the same games disagree, where, and under which quality flags, and it hands a person the exact
seconds of video to check.

## What it does

1. **Cross-source agreement.** Two feeds of the same games (two vendors; optical vs chip; automated stats vs
   human operators). Orientation and clock offset are fitted from the data; players are matched within each team
   by minimum total distance; every event is shifted within ±1 s to its best-agreeing moment, so what remains is
   not a timing artefact. Output: median and 90th-percentile gap, share of positions apart by more than 1, 2 and
   5 m with 95% Wilson intervals, split by the provider's own quality flag.
2. **Physics checks that need no ground truth.** Speeds above 12.5 m/s, accelerations above 12 m/s², jumps over
   2.5 m in 0.1 s, positions outside the playing surface, and (for 29-joint skeletons) bone-length stability and
   impossible joint speeds.
3. **Triage queue.** The worst moments of each game with a link to that second in the provider's video room, so
   a person decides which feed is right.
4. **Report note (optional LLM).** A short plain-English note generated through OpenRouter. Every number in the
   text must exist in the computed results; otherwise the note is rejected.

It runs offline in Docker on the owner's machine; no data needs to leave the building.

## Results: 2022 FIFA World Cup, PFF FC broadcast tracking vs StatsBomb 360

Same matches, same broadcast moments (every StatsBomb 360 freeze frame). Neither provider is ground truth: when
they are metres apart, at least one of them is metres off.

<!-- results:start -->
| Match | Date | Player positions compared | Median gap (m) | 90th pct gap (m) | Gap > 2 m | Gap > 5 m | Gap > 5 m when PFF says ESTIMATED |
|---|---|---:|---:|---:|---:|---:|---:|
| Senegal v Netherlands | 2022-11-21 | 45,100 | 2.10 | 4.87 | 52.5% | 9.2% | 29.5% |
| England v Iran | 2022-11-21 | 44,575 | 2.42 | 6.19 | 59.6% | 15.8% | 51.7% |
| Qatar v Ecuador | 2022-11-20 | 39,071 | 2.27 | 5.19 | 56.9% | 11.2% | 37.9% |
| United States v Wales | 2022-11-21 | 51,929 | 2.08 | 4.91 | 52.2% | 9.4% | 38.6% |
| Argentina v Saudi Arabia | 2022-11-22 | 44,166 | 2.43 | 6.97 | 59.9% | 17.6% | 58.4% |
| Denmark v Tunisia | 2022-11-22 | 37,710 | 3.05 | 8.00 | 69.1% | 25.6% | 57.9% |
| Mexico v Poland | 2022-11-22 | 44,803 | 2.05 | 5.03 | 51.1% | 10.2% | 46.3% |
| France v Australia | 2022-11-22 | 53,909 | 1.78 | 4.03 | 43.1% | 5.1% | 24.4% |
| Morocco v Croatia | 2022-11-23 | 47,659 | 2.74 | 6.81 | 64.9% | 20.5% | 59.6% |
| Germany v Japan | 2022-11-23 | 46,657 | 2.09 | 4.96 | 52.4% | 9.8% | 43.3% |
| **All 10 matches** | | **455,579** | | | **55.7%** | **13.1%** | **48.8%** |
<!-- results:end -->

PFF marks each player `VISIBLE` or `ESTIMATED`. StatsBomb 360 only records players visible in the broadcast
frame, so the last column is about players who were on screen while PFF estimated their position.

## Physics checks: SkillCorner open data (2 A-League matches, 25 fps body pose)

| Match | Player positions | Truly detected | Speed > 12.5 m/s | Jumps > 2.5 m in 0.1 s | Off pitch |
|---|---:|---:|---:|---:|---:|
| Brisbane Roar v Perth Glory | 1,054,724 | 57.9% | 0 | 0 | 151 (all extrapolated) |
| Sydney FC v Adelaide United | 957,682 | 65.8% | 3 | 2 | 20 |

SkillCorner's feed passes the physics checks almost cleanly; the number that matters is that 34–42% of player
positions are extrapolated rather than seen, which SkillCorner flags honestly. Its 29-joint skeletons keep bone
lengths within 1.2–4.0 cm at the 90th percentile (a fitted skeleton model), so bone-length checks cannot catch
joint errors there; the cross-source comparison above can.

## What this does not show

- Which provider is right in a given disagreement; the triage queue exists so a person can check the video.
- Accuracy against a physical reference (e.g. a calibrated multi-camera rig or chip system); that is the next step
  on a league's own data.
- StatsBomb 360 positions are themselves estimated from broadcast video.
- The results cover the first 10 of the 64 games; the scripts run all of them.
- 6.2% of StatsBomb freeze frames are recorded from the other team's perspective; both readings are tried per frame and the better one is used, and the count is reported per game.

## Run it

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -t .
python scripts/run_worldcup.py            # downloads public data on first run, writes results/worldcup/
python scripts/summary_table.py           # rebuilds the table above from results/
python scripts/triage_match.py 3812       # worst moments of one match with film-room links
python -m tracking_audit.cli physics --tracking data/1925299_tracking.jsonl --match data/1925299_match.json \
    --pose data/1925299_pose.jsonl.zip --out results/skillcorner/1925299.json
```

CI re-runs the tests and fails if any number in the results table differs from `results/`.
To run on your own feeds, see [docs/INPUT_FORMAT.md](docs/INPUT_FORMAT.md).

## Data and credits

- [StatsBomb open data](https://github.com/statsbomb/open-data) (events and 360 freeze frames). Data provided by StatsBomb.
- [PFF FC 2022 World Cup dataset](https://www.blog.fc.pff.com/blog/pff-fc-release-2022-world-cup-data) (broadcast tracking), free on request from PFF FC / Gradient Sports.
- [SkillCorner open data](https://github.com/SkillCorner/opendata) (broadcast tracking and body pose), credit SkillCorner.

Raw data is not redistributed here; the scripts download it from the providers.

## Author

Vahit Feryad, PhD · [vahitferyad.com](https://vahitferyad.com/) · [GitHub](https://github.com/vahit19) ·
[Google Scholar](https://scholar.google.com/citations?hl=en&user=JUtYZ1oAAAAJ)

MIT License.
