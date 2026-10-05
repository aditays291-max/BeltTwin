"""Standard-library checks of encoder association and synchronized sensor records."""
import copy
import unittest
from inspection_event import InspectionSession, build_inspection_record, validate_record
from splice_tracker import SpliceTracker, SPEED, SPLICES, LOOP_LENGTH


class InspectionTests(unittest.TestCase):
    def test_two_laps_and_repeatability(self):
        events = SpliceTracker().advance(LOOP_LENGTH * 2)
        self.assertEqual(len(events), 10)
        self.assertEqual([e['splice'] for e in events[:5]], ['S02', 'S01', 'S05', 'S04', 'S03'])
        session = InspectionSession()
        for index, event in enumerate(events, 1):
            now = event['time_s']
            record = session.start(event, now)
            self.assertEqual(record, build_inspection_record(event, index))
            self.assertEqual(session.state(now), 'SCANNING')
            self.assertEqual(session.advance(now + .59), [])
            self.assertEqual(session.advance(now + .61), [record])
            self.assertEqual(session.state(now + .61), 'COMPLETE')
            self.assertEqual(session.state(now + 2.51), 'READY')
            self.assertEqual(record['encoder']['travel_ticks'], round(now * SPEED * 100))
            validate_record(record)
        self.assertEqual(len(session.inspection_history), 10)
        self.assertEqual(session.pending_count, 0)
        self.assertEqual({r['splice_id'] for r in session.inspection_history}, set(SPLICES))

    def test_reject_wrong_association_and_sensor_context(self):
        event = SpliceTracker().advance(8)[0]
        bad_event = dict(event, splice='S03')
        with self.assertRaises(ValueError):
            build_inspection_record(bad_event, 1)
        record = build_inspection_record(event, 1)
        for mutation in ('context', 'channels', 'unhealthy'):
            bad = copy.deepcopy(record)
            if mutation == 'context':
                bad['camera']['inspection_id'] = 'INS-9999'
            elif mutation == 'channels':
                bad['mfl']['channels'].pop()
            else:
                bad['mfl']['channels'][0] = float('nan')
            with self.assertRaises(ValueError):
                validate_record(bad)

    def test_coarse_steps_do_not_lose_inspections(self):
        tracker = SpliceTracker()
        session = InspectionSession()
        for event in tracker.advance(LOOP_LENGTH * 3):
            session.start(event, 100)
        self.assertEqual(session.advance(100.61), session.inspection_history)
        self.assertEqual(len(session.inspection_history), 15)
        self.assertEqual(tracker.advance(LOOP_LENGTH * 3), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
