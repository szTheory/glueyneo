"""Source/protocol bridge tests; no frontend or guest execution."""
import copy
import hashlib
import unittest

from tools.mvs import hybrid_revalidation as r


class RevalidationTests(unittest.TestCase):
    def test_default_projection_keeps_scripted_changes_visible(self):
        old = 'def run(manual_handoff=None):\n    if manual_handoff is not None:\n        manual()\n    else:\n        scripted(1)\n'
        changed_manual = old.replace('manual()', 'manual_from_boot()') + '\ndef _manual_new():\n    return 2\n'
        self.assertEqual(r.projection(old,'collector'),r.projection(changed_manual,'collector'))
        self.assertNotEqual(r.projection(old,'collector'),r.projection(old.replace('scripted(1)','scripted(2)'),'collector'))
        self.assertNotEqual(r.projection(old,'collector'),r.projection(old.replace('manual_handoff=None','manual_handoff=False'),'collector'))
        with self.assertRaises(ValueError):
            r.projection(old.replace('manual_handoff is not None','manual_handoff and True'),'collector')
        for declaration in ['@side_effect()\ndef _manual_new():\n pass\n',
                            'def _manual_new(x=side_effect()):\n pass\n']:
            with self.assertRaises(ValueError):r.projection(old+declaration,'collector')

    def test_only_explicit_manual_helper_functions_are_excluded(self):
        old='def machine_calibration():\n    return 1\ndef gameplay_session_valid():\n    return False\n'
        self.assertEqual(r.projection(old,'helper'),r.projection(old.replace('return False','return True'),'helper'))
        self.assertNotEqual(r.projection(old,'helper'),r.projection(old.replace('return 1','return 0'),'helper'))

    def test_original_receipt_binding_checked_without_mutation(self):
        replay=r.q._load_frontend_replay()
        def event(kind,sample,mask,video):
            return dict(event_kind=kind,sample_sequence=sample,sampled_mask=mask,
                        successful_video_sequence=video,executed_cycles=video*100,invocation_id='test')
        row=dict(invocation_id='test',selected_bundle_sha256='b'*64,
            configuration_text='config',configuration_sha256=hashlib.sha256(b'config').hexdigest(),
            observations=[event('B',0,0,0),event('S',1,0,0),event('V',1,0,1),event('V',3,0,3)],
            captures=[dict(path='capture.png',sha256='c'*64,successful_video_interval=[1,3],target_frame=1)])
        sources=dict(core_sha256='a'*64,replay_sha256='d'*64,collector_sha256='e'*64,evaluator={'sha256':'f'*64})
        payload=replay._evidence('a'*64,'b'*64,row,'cfg')
        payload['implementation_identity']={'helper':'d'*64,'collector':'e'*64,'evaluator':'f'*64}
        row['replay']=dict(policy=replay.POLICY,binding=hashlib.sha256(replay._canonical(payload)).hexdigest(),
            core_sha256='a'*64,bundle_sha256='b'*64,status='pass',
            captures=[dict(capture_sha256='c'*64,successful_video_interval=[1,3],matching_sequences=[2])])
        before=copy.deepcopy(row)
        r.producer_transfer(row,sources,'cfg')
        self.assertEqual(before,row)
        for change in ('binding','captures'):
            bad=copy.deepcopy(row)
            if change=='binding':bad['replay']['binding']='0'*64
            else:bad['replay']['captures'][0]['matching_sequences']=[4]
            with self.assertRaises(ValueError):r.producer_transfer(bad,sources,'cfg')

    def test_unknown_certificate_never_promotes_machine(self):
        self.assertFalse(r.validated_bridge({'machine_identity':'a'*64},{'policy':'unknown'}))


if __name__ == '__main__':
    unittest.main()
