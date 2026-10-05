"""Conservative decoder for observed PCS Generic scoreboard writes.
Unknown/enhanced messages are logged, never guessed. One command per BLE write.
"""
import re

SERVICE_UUID = '5a0d6a15-b664-4304-8530-3a0ec53e5bc1'
WRITE_UUID = 'df531f62-fc0b-40ce-81b2-32a6262ea440'


def combined_score(payload: bytes):
    """Read the two score values without assuming their display order."""
    try: text = payload.decode('utf-8').strip('\x00\r\n ')
    except UnicodeDecodeError: return None
    if not text.startswith('BTS'): return None
    match = re.fullmatch(r'(\d{1,4})\s*/\s*(\d{1,4})(?:\s*&.*)?', text[3:].strip())
    if not match or min(int(match[1]), int(match[2])) > 10: return None
    return match[1], match[2]


def score_fields(pair, order=None):
    a, b = pair
    # Both display conventions occur in captured PCS packets. Small scores
    # cannot identify the order: wait for BTR/BTW instead of inventing wickets.
    if int(a) > 10: order = 'runs_first'
    elif int(b) > 10: order = 'wickets_first'
    elif int(a) == int(b): return {'runs':a, 'wickets':b}
    if order not in ('runs_first', 'wickets_first'): return {}
    runs, wickets = (a,b) if order == 'runs_first' else (b,a)
    return {'runs':runs, 'wickets':wickets} if int(wickets) <= 10 else {}


class ScoreDecoder:
    """Calibrate combined-score order against dedicated authoritative writes."""
    def __init__(self):
        self.order = None
        self.combined = None
        self.combined_at = None
        self.dedicated = set()

    def fallback(self, fields):
        # Once BTR/BTW is present, that field has a single authoritative source.
        # A display-format change in BTS must never transiently create wickets.
        return {key:value for key,value in fields.items() if key not in self.dedicated}

    def decode(self, payload, now):
        pair = combined_score(payload)
        if pair:
            self.combined, self.combined_at = pair, now
            if int(pair[0]) > 10: self.order = 'runs_first'
            elif int(pair[1]) > 10: self.order = 'wickets_first'
            return self.fallback(score_fields(pair, self.order))
        fields = decode_packet(payload)
        key = 'runs' if payload[:3] == b'BTR' else 'wickets' if payload[:3] == b'BTW' else None
        if key in fields: self.dedicated.add(key)
        if self.combined and now - self.combined_at <= 1.2:
            # BTR/BTW immediately follow BTS in scorer delta batches. A new
            # dedicated value also corrects a convention changed by the scorer.
            if key in fields:
                value = int(fields[key]); a, b = map(int, self.combined)
                if (a == value) != (b == value):
                    self.order = ('runs_first' if a == value else 'wickets_first') if key == 'runs' else ('wickets_first' if a == value else 'runs_first')
                    fields = {**self.fallback(score_fields(self.combined, self.order)), **fields}
        return fields


def decode_packet(payload: bytes) -> dict:
    try:
        text = payload.decode('utf-8').strip('\x00\r\n ')
    except UnicodeDecodeError:
        return {}
    code, value = text[:3], text[3:].strip()
    if code == 'BTS':
        pair = combined_score(payload)
        return score_fields(pair) if pair else {}
    elif code == 'OVB' and re.fullmatch(r'\d{1,3}(?:\.[0-5])?', value):
        return {'overs': value if '.' in value else value + '.0'}
    elif code in ('B1S', 'B2S') and re.fullmatch(r'\d{1,4}', value):
        return {('batter1_runs' if code == 'B1S' else 'batter2_runs'): value}
    elif code in ('BTN', 'FTN', 'B1N', 'B2N', 'F1N'):
        key = {'BTN':'team1', 'FTN':'team2', 'B1N':'batter1_name',
               'B2N':'batter2_name', 'F1N':'bowler'}[code]
        if len(value) <= 160:
            return {key: value}
    elif code in ('B1B', 'B2B') and re.fullmatch(r'\d{1,4}', value):
        return {('batter1_balls' if code == 'B1B' else 'batter2_balls'): value}
    elif code in ('B1K', 'B2K') and value in ('0', '1'):
        return {'striker':code[1]} if value == '1' else {'_strike_off':code[1]}
    elif code == 'F1S':
        if not value:
            return {'bowler_figures':'', 'bowler_overs':''}
        match = re.fullmatch(r'(\d{1,4})/(\d{1,2})\s*\((\d{1,3}(?:\.[0-5])?)\)', value)
        if match and int(match[2]) <= 10:
            # Captured F1S7/0 (0.2): runs conceded / wickets, then overs.
            return {'bowler_figures': f'{match[2]}–{match[1]}',
                    'bowler_overs': match[3] if '.' in match[3] else match[3]+'.0'}
    elif code == 'COV' and len(value) <= 160:
        # Complete current-over snapshot, NOT an incremental delivery event.
        # Preserve unfamiliar extras notation verbatim; blank clears the row.
        return {'deliveries':' '.join(value.split())}
    elif code == 'BTR' and re.fullmatch(r'\d{1,4}', value):
        return {'runs':value}
    elif code == 'BTW' and re.fullmatch(r'\d{1,2}', value) and int(value) <= 10:
        return {'wickets':value}
    elif code in ('LWN', 'LWD', 'LWB', 'LWF') and len(value) <= 160:
        # Confirmed by caught/bowled/LBW/run-out tests. These are delta fields:
        # an unchanged bowler/type may not be resent at the next wicket.
        return {{'LWN':'last_wicket_name', 'LWD':'last_wicket_code',
                 'LWB':'last_wicket_bowler', 'LWF':'last_wicket_fielder'}[code]:value}
    elif code == 'LWS':
        if not value: return {'last_wicket_runs':'', 'last_wicket_balls':''}
        match = re.fullmatch(r'(\d{1,4})\s*\((\d{1,4})\)', value)
        if match: return {'last_wicket_runs':match[1], 'last_wicket_balls':match[2]}
    # FTS is intentionally not used as a target: custom/DLS/multi-innings
    # targets cannot safely be inferred by adding one to an opposition total.
    return {}
