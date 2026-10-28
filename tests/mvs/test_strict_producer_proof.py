"""No guest/frontend execution; immutable source and optional private-data audit."""
from pathlib import Path
import subprocess
import unittest
from tools.mvs import strict_producer_proof as p


def source(ref,path):
    try:
        return subprocess.run(['git','show',ref+':'+path],cwd=p.q.PROJECT_ROOT,
            capture_output=True,check=True,timeout=5).stdout
    except subprocess.SubprocessError:
        raise unittest.SkipTest('immutable source epoch is not in this checkout')


class StrictProducerProofTests(unittest.TestCase):
    def test_real_default_collector_projection_and_automated_drift(self):
        path='tests/libretro/retroarch_smoke.py'
        old=source('c31014f8',path);new=source('5512de69',path)
        self.assertEqual(p.collector_projection(old),p.collector_projection(new))
        changed=new.replace(b'ready_video + 600',b'ready_video + 601')
        self.assertNotEqual(new,changed)
        self.assertNotEqual(p.collector_projection(old),p.collector_projection(changed))
        with self.assertRaises(ValueError):p.collector_projection(new.replace(b'manual_handoff=None',b'manual_handoff=True'))

    def test_real_strict_replay_projection_and_interval_drift(self):
        path='tools/mvs/frontend_replay.py'
        old=source('52ac66d8',path);new=source('5512de69',path)
        self.assertEqual(p.replay_projection(old),p.replay_projection(new))
        with self.assertRaises(ValueError):p.replay_projection(new.replace(b'64 if manual else 12',b'64 if manual else 13'))
        changed=old.replace(b'hi - lo <= 12',b'hi - lo <= 13')
        self.assertNotEqual(old,changed)
        self.assertNotEqual(p.replay_projection(changed),p.replay_projection(new))

    def test_unknown_profile_and_missing_proof_are_not_accepted(self):
        self.assertFalse(p.proof_valid(Path('local/qualification/nonexistent-profile'),{}))

    @unittest.skipUnless(Path('local/qualification/phase06-hybrid-preparation-repaired/machine-calibration.json').exists(),
                         'private retained evidence intentionally absent from public CI')
    def test_actual_fixed_strict_dataset_and_independent_parent(self):
        profile=Path('local/qualification/phase06-hybrid-preparation-repaired')
        proof=p.validate_proof(profile)
        self.assertEqual('pass',proof['strict_predicates']['overall'])
        self.assertFalse(proof['same_calibration_sample'])
        self.assertFalse(proof['fitting'])
        self.assertNotEqual(proof['producer_report_path'],proof['parent_calibration_path'])
        self.assertTrue(p.proof_valid(profile,proof))
        changed=dict(proof,parent_calibration_sha256='0'*64)
        self.assertFalse(p.proof_valid(profile,changed))


if __name__=='__main__':unittest.main()
