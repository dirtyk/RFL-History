#!/usr/bin/env python3
"""Refresh the RFL site.

Pulls every RFL season on Sleeper (following previous_league_id back to the
first Sleeper season), merges it with the frozen Yahoo history in data/yahoo/,
and rebuilds data.json + index.html at the repo root.

Usage:
    python tools/update.py          # refresh Sleeper data and rebuild
    python tools/update.py --offline  # rebuild from data already on disk

Then commit and push; GitHub Pages redeploys automatically.
No API keys needed (Sleeper's API is public and read-only).
"""
import json, os, re, subprocess, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
DATA = os.path.join(ROOT, "data")
API = "https://api.sleeper.app/v1"
USER_ID = "479486754722672640"  # kkholiday, a member of RFL every Sleeper season
LEAGUE_NAME = re.compile(r"^RFL\b", re.I)


def get(path):
    with urllib.request.urlopen(API + path, timeout=60) as r:
        return json.load(r)


def current_league():
    state = get("/state/nfl")
    for season in (state["league_season"], state["season"], state["previous_season"]):
        for lg in get(f"/user/{USER_ID}/leagues/nfl/{season}") or []:
            if LEAGUE_NAME.search(lg.get("name", "")):
                return lg["league_id"]
    sys.exit("Couldn't find the RFL league on Sleeper.")


def pull_season(lid):
    lg = get(f"/league/{lid}")
    s = {"league": lg, "users": get(f"/league/{lid}/users"), "rosters": get(f"/league/{lid}/rosters"),
         "winners_bracket": get(f"/league/{lid}/winners_bracket") or [],
         "losers_bracket": get(f"/league/{lid}/losers_bracket") or [], "matchups": {}}
    try:
        s["draft"] = [{"meta": d, "picks": get(f"/draft/{d['draft_id']}/picks")} for d in get(f"/league/{lid}/drafts")]
    except Exception as e:
        s["draft"] = str(e)
    for w in range(1, 19):
        m = get(f"/league/{lid}/matchups/{w}")
        if m:
            s["matchups"][w] = m
    return lg["season"], lg.get("previous_league_id"), s


def refresh_players():
    path = os.path.join(DATA, "players.json")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 7 * 86400:
        return
    print("Downloading Sleeper player map (~15 MB, cached for a week)...")
    urllib.request.urlretrieve(API + "/players/nfl", path)


def main():
    os.makedirs(DATA, exist_ok=True)
    if "--offline" not in sys.argv:
        out, lid = {}, current_league()
        while lid and lid != "0":
            season, prev, s = pull_season(lid)
            out[season] = s
            print(f"Sleeper {season}: {s['league']['status']}, {len(s['matchups'])} weeks")
            lid = prev
        json.dump(out, open(os.path.join(DATA, "sleeper.json"), "w"))
    refresh_players()
    subprocess.run([sys.executable, os.path.join(TOOLS, "build.py")], check=True)
    data = open(os.path.join(ROOT, "data.json")).read()  # keep site + data in sync
    html = open(os.path.join(TOOLS, "template.html")).read().replace("__DATA__", "")
    open(os.path.join(ROOT, "index.html"), "w").write(html)
    print("Rebuilt index.html and data.json. Commit and push to publish.")


if __name__ == "__main__":
    main()
