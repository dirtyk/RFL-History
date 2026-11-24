"""Merge Yahoo (2006-2024) + Sleeper (2025-) RFL data into one compact dataset: data.json"""
import json, re, sys, os, statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
YAHOO = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "rfl_yahoo_history.json")

# Sleeper username -> canonical owner
SLEEPER_OWNER = {
    "jojopolo": "Jonathan", "djrentec": "Reni", "vr6gt17": "Bob", "mcarmel": "Mark",
    "Lilfrog8": "Fish", "LittleHector": "Little Hector", "FFDragon37": "Tim",
    "bjames923": "Brandon", "NoleSteelers": "Justin K", "ryancj77": "Ryan",
    "kkholiday": "Kristian", "Tswisstopher": "T",
}
# Yahoo manager label -> canonical owner (filled in after inspecting the data)
YAHOO_ALIAS = json.load(open(os.path.join(HERE, "yahoo_alias.json"))) if os.path.exists(os.path.join(HERE, "yahoo_alias.json")) else {}

players = json.load(open(os.path.join(ROOT, "data", "players.json")))
def pname(pid):
    p = players.get(pid)
    if not p:
        return pid  # DEF abbreviations
    if p.get("position") == "DEF":
        return f"{p.get('last_name') or pid} D/ST"
    return f"{p.get('first_name','')} {p.get('last_name','')}".strip()
def ppos(pid):
    p = players.get(pid); return (p or {}).get("position") or ("DEF" if not pid.isdigit() else "")

def num(s):
    try: return float(str(s).replace(",", ""))
    except: return 0.0

seasons = []

# ---------------- Yahoo ----------------
def yahoo_owner(mgr, year, tid):
    m = re.sub(r"\s*Commissioner$", "", (mgr or "").strip())
    return YAHOO_ALIAS.get(f"{year}:{tid}") or YAHOO_ALIAS.get(m) or m

import glob
YF = sorted(glob.glob(os.path.join(ROOT, "data", "yahoo", "*.json")))
if YF:
    Y = {"seasons": {}}
    for f in YF: Y["seasons"].update(json.load(open(f))["seasons"])
    for ys, se in sorted(Y["seasons"].items()):
        year = int(ys)
        if year >= 2025: continue
        teams = {}
        for tid, t in se["teams"].items():
            teams[int(tid)] = {"tid": int(tid), "name": t["name"], "owner": yahoo_owner(t["manager"], year, tid)}
        hdr = se["standingsHeader"]
        def col(c, name):
            return c[hdr.index(name)] if name in hdr and hdr.index(name) < len(c) else ""
        standings, clinched = [], set()
        for row in se["standings"]:
            c = row["cells"]; tid = row["teamId"]
            rk = col(c, "Rank")
            if rk.startswith("*"): clinched.add(tid)
            w, l, t = (list(map(int, re.findall(r"\d+", col(c, "W-L-T")))) + [0, 0, 0])[:3]
            standings.append({"tid": tid, "rank": int(re.sub(r"\D", "", rk) or 0), "w": w, "l": l, "t": t,
                              "pf": num(col(c, "PF")), "pa": num(col(c, "PA"))})
            if tid not in teams:
                teams[tid] = {"tid": tid, "name": col(c, "Team"), "owner": col(c, "Team")}
        settings = {k.rstrip(":").strip(): v for k, v in (se.get("settings") or [])}
        # playoff weeks from settings, e.g. "Week 14, 15 and 16 (6 teams)"
        po_weeks = sorted(set(int(x) for x in re.findall(r"Week (\d+):", se.get("playoffText", ""))))
        po_teams = len(clinched) or 6
        podium = []
        if len(se.get("winners", [])) > 1:
            names = se["winners"][1][:3]
            byname = {t["name"]: tid for tid, t in teams.items()}
            podium = [byname.get(n) for n in names]
        last_wk = po_weeks[-1] if po_weeks else 17
        raw = []
        seen = set()
        for wk, wd in se["weeks"].items():
            wk = int(wk)
            if wk > last_wk: continue
            for g in wd["games"]:
                if g.get("score1") is None: continue
                key = (wk, frozenset((g["team1"], g["team2"])))
                if key in seen: continue
                seen.add(key); raw.append((wk, g))
        raw.sort(key=lambda x: x[0])
        alive = set(clinched)
        games = []
        lu = lambda L: [[x["player"], x["slot"], x["pts"], 1 if x.get("bench") else 0] for x in (L or []) if x["player"] not in ("(Empty)", "")]
        for wk in sorted(set(w for w, _ in raw)):
            elim = set()
            for _, g in [x for x in raw if x[0] == wk]:
                a, b = g["team1"], g["team2"]
                typ = "reg"
                if po_weeks and wk >= po_weeks[0]:
                    if a in alive and b in alive:
                        typ = "playoff"; elim.add(b if g["score1"] > g["score2"] else a)
                    elif a in clinched and b in clinched: typ = "place"
                    else: typ = "cons"
                games.append({"wk": wk, "a": a, "b": b, "sa": g["score1"], "sb": g["score2"],
                              "pa": g.get("proj1"), "pb": g.get("proj2"), "type": typ,
                              "la": lu(g.get("lineup1")), "lb": lu(g.get("lineup2"))})
            alive -= elim
        median = settings.get("Play Against Median Score", "No").startswith("Yes")
        if median:
            for wk in sorted(set(g["wk"] for g in games if g["type"] == "reg")):
                rows = [(g["a"], g["sa"]) for g in games if g["wk"] == wk and g["type"] == "reg"] + [(g["b"], g["sb"]) for g in games if g["wk"] == wk and g["type"] == "reg"]
                med = round(statistics.median([p for _, p in rows]), 2)
                for t, p in rows:
                    games.append({"wk": wk, "a": t, "b": None, "sa": p, "sb": med, "type": "median"})
        byname = {t["name"]: tid for tid, t in teams.items()}
        draft, n = [], len(teams) or 12
        for p in se["draft"]:
            draft.append({"rd": p["round"], "pk": p["pick"], "ov": (p["round"] - 1) * n + p["pick"],
                          "tid": byname.get(p["team"]), "player": p["player"]})
        seasons.append({"year": year, "platform": "Yahoo", "teams": list(teams.values()), "standings": standings,
                        "podium": podium, "games": sorted(games, key=lambda g: g["wk"]), "draft": draft,
                        "poWeeks": po_weeks, "poTeams": po_teams, "median": median,
                        "settings": {k: settings[k] for k in settings if k in ("Scoring Type", "Max Teams", "Playoffs", "Draft Type", "Roster Positions", "Max Acquisitions for Entire Season", "Fractional Points", "Negative Points", "Play Against Median Score")}})

# ---------------- Sleeper ----------------
S = json.load(open(os.path.join(ROOT, "data", "sleeper.json")))
for ys in sorted(S):
    s = S[ys]; lg = s["league"]; year = int(ys)
    users = {u["user_id"]: u for u in s["users"]}
    teams = []
    for r in s["rosters"]:
        u = users.get(r["owner_id"], {})
        teams.append({"tid": r["roster_id"], "name": ((u.get("metadata") or {}).get("team_name") or u.get("display_name") or "").strip(),
                      "owner": SLEEPER_OWNER.get(u.get("display_name"), u.get("display_name"))})
    pws = lg["settings"]["playoff_week_start"]
    wb, lb = s["winners_bracket"], s["losers_bracket"]
    po_pairs = {}
    for m in wb:
        po_pairs[(pws + m["r"] - 1, frozenset((m.get("t1"), m.get("t2"))))] = "place" if m.get("p") not in (None, 1) else "playoff"
    for m in lb:
        po_pairs[(pws + m["r"] - 1, frozenset((m.get("t1"), m.get("t2"))))] = "cons"
    games = []
    rec = defaultdict(lambda: {"w": 0, "l": 0, "t": 0, "pf": 0.0, "pa": 0.0})
    for wk, rows in s["matchups"].items():
        wk = int(wk)
        if not any(r.get("points") for r in rows): continue
        by = defaultdict(list)
        for r in rows:
            if r.get("matchup_id") is not None: by[r["matchup_id"]].append(r)
        def lineup(r):
            st = r.get("starters") or []; pp = r.get("players_points") or {}
            slots = lg["roster_positions"]
            out = [[pname(p), (slots[i] if i < len(slots) else "").replace("WRRB_FLEX","FLEX"), round(pp.get(p, 0), 2), 0] for i, p in enumerate(st) if p != "0"]
            out += [[pname(p), "BN", round(pp.get(p, 0), 2), 1] for p in (r.get("players") or []) if p not in st]
            return out
        regular = wk < pws
        for mid, pr in by.items():
            if len(pr) != 2: continue
            a, b = pr
            typ = "reg" if regular else po_pairs.get((wk, frozenset((a["roster_id"], b["roster_id"]))), "cons")
            games.append({"wk": wk, "a": a["roster_id"], "b": b["roster_id"], "sa": a["points"], "sb": b["points"],
                          "type": typ, "la": lineup(a), "lb": lineup(b)})
        if regular and lg["settings"].get("league_average_match"):
            pts = sorted(r["points"] for r in rows)
            med = statistics.median(pts)
            for r in rows:
                games.append({"wk": wk, "a": r["roster_id"], "b": None, "sa": r["points"], "sb": round(med, 2), "type": "median"})
    standings = []
    for r in s["rosters"]:
        st = r["settings"]
        standings.append({"tid": r["roster_id"], "w": st["wins"], "l": st["losses"], "t": st.get("ties", 0),
                          "pf": st["fpts"] + st.get("fpts_decimal", 0) / 100,
                          "pa": st.get("fpts_against", 0) + st.get("fpts_against_decimal", 0) / 100})
    standings.sort(key=lambda x: (-x["w"], -x["pf"]))
    for i, x in enumerate(standings): x["rank"] = i + 1
    podium = []
    fin = [m for m in wb if m.get("p") == 1 and m.get("w")]
    if fin:
        third = [m for m in wb if m.get("p") == 3 and m.get("w")]
        podium = [fin[0]["w"], fin[0]["l"], third[0]["w"] if third else None]
        # final rank: podium first
        done = {}
        for m in wb:
            if m.get("p") and m.get("w"): done[m["w"]] = m["p"]; done[m["l"]] = m["p"] + 1
        for x in standings:
            x["seed"] = x["rank"]
        standings.sort(key=lambda x: (done.get(x["tid"], 99), x["seed"]))
        for i, x in enumerate(standings): x["rank"] = i + 1
    draft = []
    if isinstance(s.get("draft"), list) and s["draft"]:
        for p in s["draft"][0]["picks"]:
            md = p["metadata"]
            nm = f"{md.get('first_name','')} {md.get('last_name','')}".strip()
            if md.get("position") == "DEF": nm = f"{md.get('last_name') or md.get('team')} D/ST"
            draft.append({"rd": p["round"], "pk": p["draft_slot"] if p["round"] % 2 else 13 - p["draft_slot"],
                          "ov": p["pick_no"], "tid": p["roster_id"], "player": nm, "pos": md.get("position")})
        draft.sort(key=lambda d: d["ov"])
        for d in draft: d["pk"] = (d["ov"] - 1) % 12 + 1
    seasons.append({"year": year, "platform": "Sleeper", "teams": teams, "standings": standings, "podium": podium,
                    "games": sorted(games, key=lambda g: g["wk"]), "draft": draft, "poWeeks": [pws, pws + 1, pws + 2],
                    "poTeams": lg["settings"]["playoff_teams"], "median": bool(lg["settings"].get("league_average_match")),
                    "inProgress": lg["status"] != "complete",
                    "settings": {"Scoring Type": "Half PPR (0.5)", "Playoffs": f"Weeks {pws}-{pws+2} ({lg['settings']['playoff_teams']} teams)",
                                 "Roster Positions": ", ".join(lg["roster_positions"]), "Draft Type": "Snake", "Median game": "Yes" if lg["settings"].get("league_average_match") else "No"}})

seasons.sort(key=lambda s: s["year"])
json.dump({"generated": __import__("datetime").date.today().isoformat(), "seasons": seasons},
          open(os.path.join(ROOT, "data.json"), "w"), separators=(",", ":"))
print("seasons:", [(s["year"], len(s["games"]), len(s["draft"])) for s in seasons])
print("size KB:", os.path.getsize(os.path.join(ROOT, "data.json")) // 1024)
