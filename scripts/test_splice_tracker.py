"""Standard-library checks for frame skips, loop wrap and duplicate events."""
import unittest
from splice_tracker import SpliceTracker, LOOP_LENGTH, STATION_POSITION, SPLICES, belt_pose


class TrackerTests(unittest.TestCase):
    def test_frame_partition_independence(self):
        end = 3 * LOOP_LENGTH
        coarse = SpliceTracker().advance(end)
        tracker = SpliceTracker()
        fine = []
        for i in range(1, 3001):
            fine.extend(tracker.advance(end * (i / 3000)))
        self.assertEqual(coarse, fine)
        self.assertEqual(len(coarse), 15)
        self.assertEqual({e['splice'] for e in coarse}, set(SPLICES))
        self.assertEqual(tracker.advance(end), [])

    def test_events_match_geometry(self):
        for event in SpliceTracker().advance(2 * LOOP_LENGTH):
            position = SPLICES[event['splice']] + event['encoder_m']
            self.assertAlmostEqual(position % LOOP_LENGTH, STATION_POSITION)
            self.assertAlmostEqual(belt_pose(position)[0], 5.5)
            self.assertAlmostEqual(belt_pose(position)[1], 1.5)

    def test_no_reverse_and_nonfinite(self):
        tracker = SpliceTracker()
        tracker.advance(10)
        for value in (9, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                tracker.advance(value)


if __name__ == '__main__':
    unittest.main()
