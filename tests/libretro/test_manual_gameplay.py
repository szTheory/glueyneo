"""Synthetic protocol/controller tests, never human gameplay evidence."""
import unittest
from pathlib import Path
from unittest import mock
import retroarch_smoke as s


def record(kind, sample, mask, video):
    return dict(event_kind=kind, sample_sequence=sample, sampled_mask=mask,
                successful_video_sequence=video, executed_cycles=video * 10,
                invocation_id="manual-test")


class ManualWindowTests(unittest.TestCase):
    def test_from_boot_early_start_direction_fire_never_injects_coin_start(self):
        rows=[record('B',0,0,0),record('S',1,1,0),record('V',1,1,1),record('R',1,1,1),
              record('S',2,98,1),record('V',2,98,2),record('P',2,98,2)]
        class Collector:
            invocation_id='manual-test';process=object();expected_mask=0;calls=0
            def drain(self):
                self.calls+=1
                if self.calls>=3:
                    seq=self.calls
                    rows.append(record('V',seq,98,seq))
                s._validated_observation_records(rows,'manual-test')
                return list(rows)
        c=Collector();keys=mock.Mock();handoff=mock.Mock()
        def capture(*args,**kwargs):
            kwargs['post_transition'](s.SCREENSHOT_KEY_CODE,True)
            kwargs['post_transition'](s.SCREENSHOT_KEY_CODE,False)
            return Path('capture.png'),{'capture_sha256':'a'*64}
        with mock.patch.object(s,'request_manual_gameplay_screenshot',side_effect=capture), \
             mock.patch.object(s,'frontend_exited',return_value=False),mock.patch.object(s.time,'sleep'):
            result=s._manual_from_boot(c,keys,Path('captures'),3,[1,2,3],lambda:10,handoff)
        self.assertEqual(2,result['active_origin_video_sequence'])
        self.assertEqual(1,result['handoff_record_count'])
        self.assertIsNone(c.expected_mask)
        keys.set_mask.assert_not_called();keys.release_all.assert_not_called()
        self.assertTrue(all(call.args[0]==s.SCREENSHOT_KEY_CODE for call in keys.post_key.call_args_list))
        handoff.assert_called_once_with(0)

    def test_real_protocol_and_only_screenshot_posts_after_handoff(self):
        lines = [record("B", 0, 0, 0), record("S", 1, 0, 0), record("V", 1, 0, 1)]
        s._validated_observation_records(lines, "manual-test")
        class Collector:
            invocation_id = "manual-test"
            process = object()
            expected_mask = 0
            step = 0
            def drain(self):
                self.step += 1
                if self.step == 2:
                    lines.extend([record("S", 2, 96, 1), record("V", 2, 96, 2)])
                if self.step == 3:
                    lines.extend([record("S", 3, 0, 2), record("V", 3, 0, 3)])
                if self.step == 4:
                    lines.append(record("V", 4, 0, 4))
                s._validated_observation_records(lines, "manual-test")
                return list(lines)
        keys = mock.Mock(); keys.post_key = mock.Mock()
        def capture(collector, directory, timeout, post_transition):
            post_transition(s.SCREENSHOT_KEY_CODE, True)
            post_transition(s.SCREENSHOT_KEY_CODE, False)
            return Path("owned.png"), {"capture_sha256": "a"*64}
        handoff = mock.Mock()
        with mock.patch.object(s, "request_manual_gameplay_screenshot", side_effect=capture), \
             mock.patch.object(s, "frontend_exited", return_value=False), \
             mock.patch.object(s.time, "sleep"):
            result = s._manual_active_window(Collector(), keys, Path("captures"), 1,
                                              3, [1, 2, 3], lambda: 10, handoff)
        self.assertEqual("manual", result["input_mode"])
        self.assertEqual(3, len(result["captures"]))
        keys.release_all.assert_called_once()
        keys.set_mask.assert_not_called()
        self.assertTrue(all(c.args[0] == s.SCREENSHOT_KEY_CODE for c in keys.post_key.call_args_list))
        handoff.assert_called_once_with(1)

    def test_variable_mask_capture_is_manual_only(self):
        before = [record('B',0,0,0),record('S',1,0,0),record('V',1,0,1),
                  record('S',2,32,1),record('V',2,32,2)]
        after = before + [record('S',3,96,2),record('V',3,96,3),record('V',4,96,4)]
        binding = s.bind_manual_gameplay_capture(before, after,
            invocation_id='manual-test',capture_sha256='a'*64)
        self.assertEqual([32,96],binding['sampled_masks'])
        self.assertEqual([2,4],binding['successful_video_interval'])
        with self.assertRaises(s.SmokeBlocked):
            s.bind_active_scene_capture(before,after,invocation_id='manual-test',
                expected_mask=32,capture_sha256='a'*64)
        for broken in [before, after[:-3] + after[-2:]]:
            with self.assertRaises(s.SmokeBlocked):
                s.bind_manual_gameplay_capture(before,broken,invocation_id='manual-test',capture_sha256='a'*64)
        with self.assertRaises(s.SmokeBlocked):
            s.bind_manual_gameplay_capture(before,after,invocation_id='stale',capture_sha256='a'*64)

    def test_unknown_or_oversized_window_rejected_before_handoff(self):
        for total, targets in [(1801, [1, 2, 3]), (1800, [1, 2])]:
            handoff = mock.Mock()
            with self.assertRaises(s.SmokeBlocked):
                s._manual_active_window(None, mock.Mock(), Path("captures"), 1,
                                       total, targets, lambda: 10, handoff)
            handoff.assert_not_called()


if __name__ == "__main__":
    unittest.main()
