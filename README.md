# RFL — Real Football League History

Every season of the RFL, 2006–present: champions, standings, playoff brackets, weekly box scores, draft boards, rosters, manager careers, head-to-head records and the record book.

**View it:** https://dirtyk.github.io/RFL-History/

- 2006–2024: Yahoo Fantasy (archived in `data/yahoo/`, no longer changes)
- 2025–present: Sleeper (refreshed with the script below)

## Updating

Requires Python 3 only; no installs or API keys.

```bash
python tools/update.py      # pulls all RFL Sleeper seasons, rebuilds the site
git add -A && git commit -m "Update through week N" && git push
```

GitHub Pages republishes within a minute or two of the push. The script finds the current RFL league automatically each new season.

## Fixing a manager name

Yahoo seasons map each team's manager to a single name in `tools/yahoo_alias.json` (e.g. `"KK☠️": "Kristian"`, or `"2009:2": "Name"` for one team in one season). Sleeper usernames are mapped in `SLEEPER_OWNER` in `tools/build.py`. Edit, then run `python tools/update.py --offline`.

## Files

| Path | What |
|---|---|
| `index.html`, `data.json` | The site (served by GitHub Pages) |
| `tools/update.py` | Refresh Sleeper data + rebuild |
| `tools/build.py` | Merges Yahoo + Sleeper into `data.json` |
| `tools/template.html` | Site source |
| `data/yahoo/` | Raw Yahoo archive |
| `data/sleeper.json` | Raw Sleeper pull |
