import tempfile
import unittest
from server.scoreboard_protocol import decode_packet
from server.scoreboard_state import State

class ProtocolTests(unittest.TestCase):
    def test_scores_and_all_out(self):
        self.assertEqual(decode_packet(b'BTS95/4'), {'runs':'95','wickets':'4'})
        self.assertEqual(decode_packet(b'BTS123/10'), {'runs':'123','wickets':'10'})
        self.assertEqual(decode_packet(b'BTS95/4 & 200/8'), {'runs':'95','wickets':'4'})
    def test_overs_and_batters(self):
        self.assertEqual(decode_packet(b'OVB14.2'), {'overs':'14.2'})
        self.assertEqual(decode_packet(b'OVB15'), {'overs':'15.0'})
        self.assertEqual(decode_packet(b'B1S24'), {'batter1_runs':'24'})
    def test_invalid_or_unmapped_is_not_guessed(self):
        for packet in (b'OVB4.6', b'BTS10/99', b'BTSoops', b'FTS123/4', b'B1Sx', b'\xff', b'BTS1/0OVB0.1'):
            self.assertEqual(decode_packet(packet), {})

class EnhancedTests(unittest.TestCase):
    def test_names_balls_and_figures(self):
        for packet, expected in [
            (b'BTNBackyard A', {'team1':'Backyard A'}),
            (b'FTNBackyard B', {'team2':'Backyard B'}),
            (b'B1NPlayer 16', {'batter1_name':'Player 16'}),
            (b'B2NPlayer 17', {'batter2_name':'Player 17'}),
            (b'B1B12', {'batter1_balls':'12'}),
            (b'B2B1', {'batter2_balls':'1'}),
            (b'F1NPlayer 1', {'bowler':'Player 1'}),
            (b'F1S7/0 (0.2)', {'bowler_figures':'0–7','bowler_overs':'0.2'}),
            (b'F1S28/3 (4.5)', {'bowler_figures':'3–28','bowler_overs':'4.5'}),
            (b'F1N ', {'bowler':''}),
            (b'COV ', {'deliveries':''}),
        ]:
            self.assertEqual(decode_packet(packet), expected)
    def test_over_snapshot_undo_repeated_packets_and_strike_order(self):
        with tempfile.TemporaryDirectory() as folder:
            state=State(folder)
            for packet in (b'COV1 2 ',b'COV1 2 ',b'COV1 ',b'COV1 6 ',b'B2K1',b'B1K0'):
                state.receive(packet)
            data=state.snapshot()['score']
            self.assertEqual(data['deliveries'],'1 6')
            self.assertEqual(data['striker'],'2')
            self.assertNotIn('_strike_off',data)
            state.receive(b'B2K0');self.assertEqual(state.snapshot()['score']['striker'],'none')
            state.receive(b'COV ');self.assertEqual(state.snapshot()['score']['deliveries'],'')
    def test_malformed_bowling_figures_and_unobserved_codes(self):
        for packet in (b'F1S7/0 (0.9)',b'F1S7/99 (0.2)',b'B1K8',b'F2NP 2',b'B1D1'):
            self.assertEqual(decode_packet(packet),{})

class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.state=State(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def test_manual_is_not_overwritten_and_packets_logged(self):
        self.state.save({'source':'manual','runs':'51'})
        self.state.receive(b'BTS99/3')
        result=self.state.snapshot()
        self.assertEqual(result['score']['runs'],'51');self.assertEqual(result['packet_count'],1)
        self.assertIsNone(result['last_score'])
    def test_invalid_packet_preserves_score(self):
        self.state.receive(b'BTS95/4');self.state.receive(b'BTSoops')
        self.assertEqual(self.state.snapshot()['score']['runs'],'95')
    def test_restore_clears_live_numbers(self):
        self.state.save({'runs':'70','team1':'TEST'})
        restored=State(self.temp.name).snapshot()['score']
        self.assertEqual(restored['runs'],'');self.assertEqual(restored['team1'],'TEST')
    def test_reset_retains_appearance(self):
        self.state.save({'team1':'A','runs':'9','banner':'OLD'})
        self.state.reset();result=self.state.snapshot()['score']
        self.assertEqual(result['team1'],'A');self.assertEqual(result['runs'],'');self.assertEqual(result['banner'],'')
    def test_invalid_settings_do_not_mutate(self):
        for data in ({'color1':'url(bad)'},{'logo1':'data:image/svg+xml;base64,abcd'},{'source':'unknown'},{'visible':'true'}):
            with self.assertRaises(ValueError): self.state.save(data)
        self.assertEqual(self.state.snapshot()['score']['color1'],'#ec218c')

if __name__=='__main__':unittest.main()
