"""Match history and shared broadcast playout for the local scoreboard.

Generic Bluetooth writes arrive one field at a time. Coalesce them before taking
score observations; COV is a replacement snapshot, never an incremental event.
"""
from __future__ import annotations

import copy
import math
import random
import re


DEFAULT_CONFIG = {
    "total_overs": 20, "wickets_limit": 10, "target": None,
    "rotation_mode": "mixed", "interval_seconds": 10, "graphic_seconds": 25,
    "auto_drinks": True, "auto_innings_break": True, "auto_summary": True,
    "match_title": "BACKYARD CRICKET", "venue": "", "messages": [],
    "result_override": "",
}
KINDS = {"run_chart", "batting_card", "innings_break", "match_summary"}


def integer(value):
    return int(value) if str(value).isdigit() else None


def balls(value):
    match = re.fullmatch(r"(\d{1,3})(?:\.([0-5]))?", str(value))
    return int(match[1]) * 6 + int(match[2] or 0) if match else None


def overs(value):
    return f"{value // 6}.{value % 6}" if value is not None else "—"


def validate_config(changes):
    if not isinstance(changes, dict) or set(changes) - set(DEFAULT_CONFIG):
        raise ValueError("Unknown broadcast setting")
    for key, value in changes.items():
        if key in ("auto_drinks", "auto_innings_break", "auto_summary"):
            if type(value) is not bool: raise ValueError(f"{key} must be true or false")
        elif key in ("total_overs", "wickets_limit", "interval_seconds", "graphic_seconds"):
            limits = {"total_overs": (1, 100), "wickets_limit": (1, 10),
                      "interval_seconds": (5, 60), "graphic_seconds": (5, 120)}
            lo, hi = limits[key]
            if type(value) is not int or not lo <= value <= hi:
                raise ValueError(f"{key} must be between {lo} and {hi}")
        elif key == "target":
            if value is not None and (type(value) is not int or not 1 <= value <= 9999):
                raise ValueError("Target must be a positive number or blank")
        elif key == "rotation_mode":
            if value not in ("mixed", "automatic", "manual"): raise ValueError("Invalid strip mode")
        elif key == "messages":
            if not isinstance(value, list) or len(value) > 20: raise ValueError("Use at most 20 messages")
            for item in value:
                if not isinstance(item, dict) or set(item) - {"type", "text", "team1", "team2", "wins1", "wins2", "attendance"}:
                    raise ValueError("Invalid message")
                if item.get("type") not in ("custom", "head_to_head", "attendance"): raise ValueError("Invalid message type")
                if any(not isinstance(v, str) or len(v) > 160 for v in item.values()): raise ValueError("Message fields must be short text")
                for field in ("wins1", "wins2", "attendance"):
                    if item.get(field) and not item[field].isdigit(): raise ValueError(f"{field} must be a whole number")
        elif not isinstance(value, str) or len(value) > 160:
            raise ValueError(f"{key} must be text up to 160 characters")


def new_innings(score):
    return {"team": score["team1"], "opposition": score["team2"],
            "color": score["color1"], "opposition_color": score["color2"],
            "logo": score["logo1"], "opposition_logo": score["logo2"],
            "runs": None, "wickets": None, "balls": None, "batters": [], "bowlers": [],
            "samples": {}, "over_tokens": {}, "wicket_events": [], "last_wicket": None,
            "drinks_shown": False, "ended": False, "extras": None, "tracked_from_start": False}


class BroadcastGraphics:
    def __init__(self, saved=None):
        self.config = copy.deepcopy(DEFAULT_CONFIG)
        self.innings = []
        self.phase = "live"
        self.finished_at = None
        self.summary_shown = False
        self.active = None
        self.pending = None
        self.pending_at = None
        self.previous = None
        self.strip = {"text": "BACKYARD CRICKET", "kind": "main"}
        self.next_strip_at = 0
        self.priority = None
        self.dirty = False
        self.random = random.Random()
        if saved:
            validate_config(saved.get("config", {}))
            self.config.update(saved.get("config", {}))
            self.innings = saved.get("innings", [])
            self.phase = saved.get("phase", "live")
            self.finished_at = saved.get("finished_at")
            self.summary_shown = saved.get("summary_shown", False)

    def export(self):
        return {"config": self.config, "innings": self.innings, "phase": self.phase,
                "finished_at": self.finished_at, "summary_shown": self.summary_shown}

    def configure(self, changes):
        validate_config(changes)
        self.config.update(copy.deepcopy(changes))
        self.next_strip_at = 0
        self.dirty = True

    def queue(self, score, changes, now):
        # Close an older packet batch before receiving another one.
        self.flush(now)
        self.pending = copy.deepcopy(score)
        if self.pending_at is None: self.pending_at = now
        if "deliveries" in changes:
            b = balls(score["overs"])
            current_team = self.innings[-1]['team'] if self.innings else score['team1']
            swapping = bool(self.innings and self.innings[-1]['balls'] and
                            self.innings[-1]['team'] != self.innings[-1]['opposition'] and
                            score['team2'] == self.innings[-1]['team'])
            if b is not None and self.phase == "live" and score['team1'] == current_team and not swapping:
                if not self.innings: self.innings.append(new_innings(score))
                index = max(0, (b - 1) // 6) if b and b % 6 == 0 else (b or 0) // 6
                tokens = score["deliveries"].split()
                previous_tokens = self.innings[-1]['over_tokens'].get(str(index), [])
                if b and b % 6 == 0 and tokens and len(tokens) < len(previous_tokens):
                    # New-over COV can precede the next OVB write. Preserve the
                    # previous complete row until the batch's ball count arrives.
                    index = b // 6
                # A clear at an over boundary is the next over's empty row.
                if not tokens and b and b % 6 == 0: index = b // 6
                self.innings[-1]["over_tokens"][str(index)] = tokens
                self.dirty = True

    def flush(self, now, force=False):
        if self.pending is not None and (force or now - self.pending_at >= 1.2):
            score = self.pending
            self.pending = self.pending_at = None
            self.observe(score, now)

    def observe(self, score, now, allow_end=True):
        b, runs, wickets = balls(score["overs"]), integer(score["runs"]), integer(score["wickets"])
        if b is None or runs is None or wickets is None: return
        if self.phase == 'live' and len(self.innings) == 1:
            first = self.innings[0]
            reversed_pair = score['team1'] == first['opposition'] and score['team2'] == first['team'] and score['team1'] != first['team']
            if reversed_pair and b <= 6 and first['balls'] is not None and b < first['balls']:
                # A scorer can end a shortened innings without sending a match
                # control action. Preserve the first innings when the chase resets.
                self.end_innings(now)
            elif first['balls'] and first['team'] != first['opposition'] and (
                    score['team1'] == first['opposition'] or score['team2'] == first['team']):
                # Ignore a partial team-swap batch, never relabel the first innings.
                return
        if self.phase in ('innings_break', 'complete') and self.innings:
            current = self.innings[-1]
            if (score['team1'] == current['team'] and
                    (b, runs, wickets) == (current['balls'], current['runs'], current['wickets'])):
                self._players(current, score, self.previous, now)
                if score['deliveries'].strip():
                    current['over_tokens'][str(max(0, (b-1)//6) if b and b%6==0 else b//6)] = score['deliveries'].split()
                self.previous = copy.deepcopy(score)
                self.dirty = True
                return
            if self.phase == 'complete': return
        if self.phase == "innings_break":
            first = self.innings[0]
            # A scorer reset plus team swap is a reliable new-innings signal.
            if b <= 6 and score["team1"] == first["opposition"] and score['team2'] == first['team'] and score["team1"] != first["team"]:
                self.phase = "live"
                self.innings.append(new_innings(score))
                self.previous = None
                self.active = None
            else: return
        if not self.innings: self.innings.append(new_innings(score))
        current = self.innings[-1]
        previous = self.previous
        old_w = current["wickets"]
        old_b = current["balls"]
        old_tokens = current["over_tokens"]
        if old_b is None: current['tracked_from_start'] = b == 0 and runs == 0
        if old_b is not None and b < old_b:
            current["samples"] = {k: v for k, v in current["samples"].items() if int(k) <= b}
            current["over_tokens"] = {k: v for k, v in old_tokens.items() if int(k) <= b // 6}
        if old_w is not None and wickets < old_w:
            current["wicket_events"] = [e for e in current["wicket_events"] if e["number"] <= wickets]
            current["last_wicket"] = None
            self.priority = None
            for row in current["batters"]:
                if row.get("out_number", 0) > wickets:
                    row.update(dismissal="", out_number=0)
        current.update(team=score["team1"], opposition=score["team2"], color=score["color1"],
                       opposition_color=score["color2"], logo=score["logo1"],
                       opposition_logo=score["logo2"], runs=runs, wickets=wickets, balls=b)
        current["samples"][str(b)] = runs
        if b % 6:
            current['over_tokens'][str(b // 6)] = score['deliveries'].split()
        if old_w is not None and wickets > old_w:
            for number in range(old_w + 1, wickets + 1):
                current["wicket_events"].append({"balls": b, "number": number, "at": now})
        self._players(current, score, previous, now)
        if previous and previous["deliveries"] != score["deliveries"] and any(t in ("4", "6") for t in score["deliveries"].split()):
            # Queue on additions/corrections; repeated COV writes do not add counts.
            self.priority = "boundaries"
            self.next_strip_at = 0
        halfway = self.config["total_overs"] * 3
        if old_b is not None and old_b < halfway <= b and not current["drinks_shown"]:
            current["drinks_shown"] = True
            if self.config["auto_drinks"]: self.show("batting_card", now, reason="Drinks break")
        if b < halfway: current["drinks_shown"] = False
        self.previous = copy.deepcopy(score)
        self.dirty = True
        limit = b >= self.config["total_overs"] * 6 or wickets >= self.config["wickets_limit"]
        if allow_end:
            if len(self.innings) == 1 and limit: self.end_innings(now)
            elif len(self.innings) == 2 and (limit or runs >= self.target()): self.finish(now)

    def _players(self, current, score, previous, now):
        for slot in (1, 2):
            name = score[f"batter{slot}_name"].strip()
            if not name: continue
            row = next((r for r in current["batters"] if r["name"] == name), None)
            if row is None:
                row = {"name": name, "runs": None, "balls": None, "dismissal": "", "active": True, "out_number": 0}
                current["batters"].append(row)
            for field in ("runs", "balls"):
                value = integer(score[f"batter{slot}_{field}"])
                if value is not None: row[field] = value
            row["active"] = row['dismissal'].lower() in ('', 'not out')
            # Last wicket identity is confirmed by a changed batter slot near a
            # wicket event, not guessed from the striker flag (run-outs exist).
            prior_name = previous.get(f"batter{slot}_name") if previous else None
            event = next((e for e in current['wicket_events'] if not e.get('identified_name') and now - e['at'] < 120), None)
            if prior_name and prior_name != name and event and now - event["at"] < 120:
                outgoing = next((r for r in current["batters"] if r["name"] == prior_name), None)
                if outgoing and not outgoing.get("out_number"):
                    dismissal = outgoing['dismissal'] if outgoing['dismissal'].lower() not in ('', 'not out') else 'Out · details pending'
                    outgoing.update(active=False, dismissal=dismissal, out_number=event['number'])
                    event['identified_name'] = prior_name
                    current["last_wicket"] = copy.deepcopy(outgoing)
                    self.priority = "last_wicket"
                    self.next_strip_at = 0
        active_names = {score["batter1_name"], score["batter2_name"]}
        if any(active_names) and self.phase == 'live':
            for row in current["batters"]: row["active"] = row["name"] in active_names
        name = score["bowler"].strip()
        if name:
            row = next((r for r in current["bowlers"] if r["name"] == name), None)
            if row is None:
                row = {"name": name, "figures": "", "overs": ""}
                current["bowlers"].append(row)
            row.update(figures=score["bowler_figures"], overs=score["bowler_overs"])

    def target(self):
        if self.config["target"] is not None: return self.config["target"]
        return (self.innings[0]["runs"] or 0) + 1 if self.innings else 1

    def end_innings(self, now):
        if not self.innings or self.innings[-1]["runs"] is None: raise ValueError("Enter a score before ending the innings")
        if len(self.innings) > 1: return self.finish(now)
        self.innings[-1]["ended"] = True
        self.phase = "innings_break"
        self.dirty = True
        if self.config["auto_innings_break"]: self.show("innings_break", now, reason="Innings break")

    def finish(self, now):
        if not self.innings: raise ValueError("Enter a score before ending the match")
        if len(self.innings) < 2 and not self.config["result_override"]:
            raise ValueError("Start the second innings or enter a result before ending the match")
        if self.phase != "complete":
            self.innings[-1]["ended"] = True
            self.phase = "complete"
            self.finished_at = now
            self.summary_shown = False
            self.active = None
            self.next_strip_at = 0
            self.dirty = True

    def result(self):
        if self.config["result_override"]: return self.config["result_override"]
        if self.phase != "complete" or len(self.innings) < 2: return ""
        first, second = self.innings[:2]
        if second["runs"] >= self.target():
            margin = self.config["wickets_limit"] - second["wickets"]
            return f"{second['team']} wins by {margin} {'wicket' if margin == 1 else 'wickets'}"
        margin = self.target() - 1 - second["runs"]
        if margin == 0: return "Match tied"
        return f"{first['team']} wins by {margin} {'run' if margin == 1 else 'runs'}"

    def show(self, kind, now, reason="Manual", innings=None):
        if kind not in KINDS: raise ValueError("Unknown graphic")
        index = len(self.innings) - 1 if innings is None else innings
        if type(index) is not int or index < 0 or index >= len(self.innings): raise ValueError("No innings statistics available yet")
        self.active = {"kind": kind, "innings": index, "reason": reason,
                       "until": now + self.config["graphic_seconds"]}

    def action(self, command, score, now):
        self.flush(now, force=True)
        kind = command.get("action")
        if kind == "show": self.show(command.get("kind"), now, innings=command.get("innings"))
        elif kind == "hide": self.active = None
        elif kind == "end_innings": self.end_innings(now)
        elif kind == "finish": self.finish(now)
        elif kind == "reopen":
            if self.innings:
                self.phase = "live"
                self.innings[-1]["ended"] = False
                self.finished_at = None
                self.summary_shown = False
                self.active = None
                self.previous = copy.deepcopy(score)
                self.observe(score, now, allow_end=False)
                self.dirty = True
        elif kind == "start_chase":
            if self.phase != "innings_break" or len(self.innings) != 1: raise ValueError("End the first innings before starting the chase")
            self.phase = "live"
            self.innings.append(new_innings(score))
            self.previous = None
            self.active = None
            self.dirty = True
        else: raise ValueError("Unknown broadcast action")

    def edit_stats(self, changes):
        index = changes.get("innings")
        if type(index) is not int or not 0 <= index < len(self.innings): raise ValueError("Choose an innings")
        if set(changes) - {"innings", "batters", "bowlers", "extras", "over_runs", "fours", "sixes", "last_wicket_name"}: raise ValueError("Unknown statistics field")
        current = self.innings[index]
        updated = copy.deepcopy(current)
        for key in ("batters", "bowlers"):
            if key not in changes: continue
            rows = changes[key]
            if not isinstance(rows, list) or len(rows) > 15: raise ValueError("Use at most 15 player rows")
            allowed = {"name", "runs", "balls", "dismissal"} if key == "batters" else {"name", "figures", "overs"}
            cleaned = []
            for row in rows:
                if not isinstance(row, dict) or set(row) - allowed: raise ValueError("Invalid player row")
                item = {k: row.get(k, "") for k in allowed}
                for k, v in item.items():
                    if k in ("runs", "balls"):
                        if v is not None and (type(v) is not int or not 0 <= v <= 9999): raise ValueError("Player scores must be non-negative whole numbers or blank")
                    elif not isinstance(v, str) or len(v) > 160: raise ValueError("Invalid player text")
                if item["name"].strip():
                    if key == "batters": item.update(active=item["dismissal"].lower() in ("", "not out"), out_number=0)
                    cleaned.append(item)
            updated[key] = cleaned
        for key in ("extras", "fours", "sixes"):
            if key in changes:
                v = changes[key]
                if v is not None and (type(v) is not int or not 0 <= v <= 9999): raise ValueError(f"{key} must be a non-negative whole number or blank")
                updated[key] = v
        if "over_runs" in changes:
            values = changes["over_runs"]
            if not isinstance(values, list) or len(values) > 100 or any(v is not None and (type(v) is not int or not 0 <= v <= 999) for v in values): raise ValueError("Invalid runs per over")
            updated["manual_over_runs"] = values
        self.innings[index] = updated
        dismissed = [row for row in updated["batters"] if row["dismissal"] and row["dismissal"].lower() != "not out"]
        selected = changes.get('last_wicket_name')
        if selected is not None and (not isinstance(selected, str) or len(selected) > 160):
            self.innings[index] = current
            raise ValueError('Invalid last wicket batter')
        previous_name = (current['last_wicket'] or {}).get('name')
        chosen = next((row for row in dismissed if row['name'] == (selected or previous_name)), None)
        if selected and chosen is None:
            self.innings[index] = current
            raise ValueError('Last wicket must be a dismissed batter')
        if chosen or dismissed: updated["last_wicket"] = copy.deepcopy(chosen or dismissed[-1])
        else: updated['last_wicket'] = None
        self.next_strip_at = 0
        self.dirty = True

    def stats(self, current):
        out = copy.deepcopy(current)
        b = current["balls"]
        out["overs"] = overs(b)
        out["run_rate"] = round(current["runs"] * 6 / b, 2) if b and current["runs"] is not None else None
        tokens = [t for row in current["over_tokens"].values() for t in row]
        out["fours"] = current.get("fours") if current.get("fours") is not None else tokens.count("4")
        out["sixes"] = current.get("sixes") if current.get("sixes") is not None else tokens.count("6")
        out['fours_manual'] = current.get('fours')
        out['sixes_manual'] = current.get('sixes')
        out['extras_manual'] = current.get('extras')
        legal_tokens = sum(bool(re.fullmatch(r'\d+|[Ww]', t)) for t in tokens)
        out["boundaries_complete"] = (current.get("fours") is not None and current.get("sixes") is not None) or (current.get('tracked_from_start', False) and legal_tokens >= (b or 0))
        known_runs = [r['runs'] for r in current['batters']]
        required = min((current['wickets'] or 0) + 2, self.config['wickets_limit'] + 1)
        if out['extras'] is None and len(known_runs) >= required and all(v is not None for v in known_runs):
            difference = (current['runs'] or 0) - sum(known_runs)
            if difference >= 0: out['extras'] = difference
        samples = {int(k): v for k, v in current["samples"].items()}
        samples.setdefault(0, 0)
        manual = current.get("manual_over_runs", [])
        chart = []
        for index in range(self.config["total_overs"]):
            end = min((index + 1) * 6, b or 0)
            start = index * 6
            runs = samples[end] - samples[start] if end > start and end in samples and start in samples else None
            if index < len(manual) and manual[index] is not None: runs = manual[index]
            chart.append({"over": index + 1, "runs": runs,
                          "wickets": sum(start < e["balls"] <= (index + 1) * 6 for e in current["wicket_events"])})
        out["chart"] = chart
        out.pop("samples", None)
        out.pop("over_tokens", None)
        return out

    def candidates(self, score):
        manual = []
        if score["banner"].strip(): manual.append({"kind": "main", "text": score["banner"]})
        for message in self.config["messages"]:
            kind = message["type"]
            if kind == "head_to_head": text = f"HEAD TO HEAD  {message.get('team1', '')} ({message.get('wins1', '0')})  {message.get('team2', '')} ({message.get('wins2', '0')})"
            elif kind == "attendance": text = f"ATTENDANCE  {int(message.get('attendance') or 0):,}"
            else: text = message.get("text", "")
            if text.strip(): manual.append({"kind": kind, "text": text})
        auto = []
        if self.innings:
            current = self.stats(self.innings[-1])
            last = current["last_wicket"]
            if last and last["runs"] is not None and last["balls"] is not None:
                auto.append({"kind": "last_wicket", "text": f"LAST WICKET  {last['name']} {last['runs']} ({last['balls']})"})
            if any(self.innings[-1]["over_tokens"].values()):
                label = "BOUNDARIES" if current["boundaries_complete"] else "RECORDED BOUNDARIES"
                auto.append({"kind": "boundaries", "text": f"{label}  FOURS {current['fours']}   SIXES {current['sixes']}"})
            if self.innings[-1].get("fours") is not None and not any(c["kind"] == "boundaries" for c in auto):
                auto.append({"kind": "boundaries", "text": f"BOUNDARIES  FOURS {current['fours']}   SIXES {current['sixes']}"})
            if self.phase == 'live' and len(self.innings) == 1 and current["balls"] and current["balls"] < self.config["total_overs"] * 6:
                rpo = current['runs'] * 6 / current['balls']
                remaining = self.config["total_overs"] - current["balls"] / 6
                rates = [rpo, *(math.floor(rpo) + n for n in (1, 2, 3))]
                values = [f"{rate:.2f}".rstrip('0').rstrip('.') +
                          f" RPO {round(current['runs'] + remaining * rate)}" for rate in rates]
                auto.append({"kind": "projection", "text": 'PROJECTED: ' + ' | '.join(values)})
        mode = self.config["rotation_mode"]
        return (manual if mode == "manual" else auto if mode == "automatic" else manual + auto)

    def snapshot(self, score, now):
        self.flush(now)
        for innings in self.innings:
            for slot in (1, 2):
                if innings['team'] == score[f'team{slot}']:
                    innings.update(color=score[f'color{slot}'], logo=score[f'logo{slot}'])
                if innings['opposition'] == score[f'team{slot}']:
                    innings.update(opposition_color=score[f'color{slot}'], opposition_logo=score[f'logo{slot}'])
        if self.active and self.active["until"] <= now: self.active = None
        if self.phase == "complete" and self.config["auto_summary"] and not self.summary_shown and now >= self.finished_at + 30:
            self.show("match_summary", now, reason="Full time")
            self.summary_shown = True
            self.dirty = True
        result = self.result()
        if self.phase == "complete" and result:
            self.strip = {"kind": "result", "text": result}
        elif now >= self.next_strip_at:
            candidates = self.candidates(score)
            chosen = next((c for c in candidates if c["kind"] == self.priority), None)
            self.priority = None
            if chosen is None:
                pool = [c for c in candidates if c["kind"] != self.strip["kind"]] or candidates
                weights = [4 if c["kind"] == "projection" and self.innings[-1]["balls"] >= self.config["total_overs"] * 2 else 1 for c in pool]
                chosen = self.random.choices(pool, weights=weights)[0] if pool else {"kind": "main", "text": score["banner"] or self.config["match_title"]}
            self.strip = {"kind": chosen["kind"], "text": chosen["text"]}
            self.next_strip_at = now + self.config["interval_seconds"]
        return {"config": copy.deepcopy(self.config), "phase": self.phase,
                "innings": [self.stats(i) for i in self.innings], "target": self.target() if len(self.innings) > 1 else None,
                "result": result, "active": copy.deepcopy(self.active), "strip": self.strip.copy(),
                "summary_due_in": max(0, math.ceil(self.finished_at + 30 - now)) if self.finished_at and not self.summary_shown and self.config['auto_summary'] else None}
