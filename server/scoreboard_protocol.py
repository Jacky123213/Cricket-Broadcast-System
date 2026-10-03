"""Conservative decoder for observed PCS Generic scoreboard writes.
Unknown/enhanced messages are logged, never guessed. One command per BLE write.
"""
import re

SERVICE_UUID = '5a0d6a15-b664-4304-8530-3a0ec53e5bc1'
WRITE_UUID = 'df531f62-fc0b-40ce-81b2-32a6262ea440'


def decode_packet(payload: bytes) -> dict:
    try:
        text = payload.decode('utf-8').strip('\x00\r\n ')
    except UnicodeDecodeError:
        return {}
    code, value = text[:3], text[3:].strip()
    if code == 'BTS':
        # Multiple innings may be separated by '&'; don't merge innings.
        match = re.fullmatch(r'(\d{1,4})\s*/\s*(\d{1,2})(?:\s*&.*)?', value)
        if match and int(match[2]) <= 10:
            return {'runs': match[1], 'wickets': match[2]}
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
    # FTS is intentionally not used as a target: custom/DLS/multi-innings
    # targets cannot safely be inferred by adding one to an opposition total.
    return {}
