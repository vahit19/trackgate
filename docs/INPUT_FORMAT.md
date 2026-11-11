# Running on your own feeds

The audit never needs your data to leave your servers. Two feeds of the same games (for example an optical
system and a chip/sensor system, or an automated stats engine and human operators) are converted to the
structures below by a small adapter; everything else is unchanged.

## Continuous feed (tracking at any frame rate)

`load_*` returns `{period: (times, frames)}`:

- `times`: list of seconds since the start of the period, increasing.
- `frames[i]`: `{"home": [(x, y, flag), ...], "away": [(x, y, flag), ...]}` in metres, origin at centre ice / centre spot.
  `flag` is the provider's own quality label (e.g. `VISIBLE`/`ESTIMATED`); results are reported per flag.

## Snapshot feed (positions at events)

A list of `{"t": seconds, "period": int, "team_home": bool, "mates": [(x, y, is_actor)], "opps": [...], "type": str}`
in the same units, with each snapshot oriented so the acting team attacks left to right (orientation and clock
offset are fitted from the data, per period and team, so no manual calibration is needed).

## Rink or pitch size

Pass the surface size if it is not 105 x 68 m (an NHL rink is 60.96 x 25.91 m).

## Output

Per game: agreement distribution (median, 90th percentile), share of positions apart by more than 1, 2 and 5 m
with 95% Wilson intervals, split by quality flag; and a triage queue of the worst moments with a link to the
second in your video system.
