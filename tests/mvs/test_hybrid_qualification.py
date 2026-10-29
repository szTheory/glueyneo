import inspect
import unittest
import argparse
import tempfile
import json
from pathlib import Path
from unittest import mock

from tools.mvs import hybrid_qualification as p
from tools.mvs import hybrid_gameplay as g


class ProducerTests(unittest.TestCase):
    def test_derived_driver_preserves_native_default_and_never_rewrites_strict(self):
        original_native = inspect.getsource(p.q.run_active_scene)
        original_frontend = inspect.getsource(p.q.run_active_scene_frontend)
        native, frontend = p.derived_sources()
        compile(native, '<test native>', 'exec')
        compile(frontend, '<test frontend>', 'exec')
        self.assertIn('hybrid_native_sink.update', native)
        self.assertIn('actual = hybrid_owned_run(', frontend)
        self.assertNotIn('_write_active_scene_contract(', frontend)
        self.assertEqual(original_native, inspect.getsource(p.q.run_active_scene))
        self.assertEqual(original_frontend, inspect.getsource(p.q.run_active_scene_frontend))

    def test_prepare_calibrate_freeze_cli_stages_are_not_human_acceptance(self):
        with mock.patch.object(p, 'prepare', return_value={'stage':'prepared','overall':'pending','human_semantics':'pending'}) as prepare, \
             mock.patch('sys.argv', ['hybrid', 'prepare', '--output', 'local/qualification/new-test']):
            self.assertEqual(0, p.main())
            prepare.assert_called_once()
        with mock.patch.object(p, 'calibrate', return_value={'machine_status':'fail','overall':'fail','human_semantics':'pending'}), \
             mock.patch('sys.argv', ['hybrid', 'calibrate', '--output', 'local/qualification/new-test']):
            self.assertEqual(1, p.main())

    def test_manual_budget_and_actual_config_keys(self):
        self.assertEqual(236, g.budget())
        self.assertLessEqual(g.budget(), 255)
        config = 'input_player1_left = "left"\ninput_player1_right = "right"\ninput_player1_b = "z"\ninput_player1_select = "num1"\ninput_player1_start = "num2"\n'
        self.assertEqual('z', g.instructions(config)['fire'])
        self.assertEqual('custom', g.instructions(config.replace('"z"', '"custom"'))['fire'])

    def test_relative_capture_preview_matches_actual_resolved_configuration(self):
        cfg, manual = p.preview_configuration(argparse.Namespace(capture_dir=Path('local/qualification/relative-captures')))
        self.assertIsNotNone(cfg); self.assertIsNotNone(manual)
        self.assertNotEqual(cfg, manual)
        smoke=p.q._load_retroarch_smoke()
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp).resolve();captures=Path('local/qualification/relative-captures').resolve()
            text=smoke.write_frontend_config(work,captures,direct_log=True).read_text()+'config_save_on_exit = "false"\n'
            self.assertEqual(cfg,p.q._frontend_configuration_identity(text,work_directory=work,capture_directory=captures))
        with mock.patch.object(p.q,'_frontend_configuration_identity',return_value=None):
            with self.assertRaises(ValueError):
                p.preview_configuration(argparse.Namespace(capture_dir=Path('local/qualification/relative-captures')))

    def test_invalid_preview_aborts_before_intent_or_frontend_launch(self):
        native = 'def run_active_scene(*args):\n hybrid_native_sink.update(contract={},runs={})\n return {"predicate_results":{"overall":"pass"}}\n'
        frontend = 'def run_active_scene_frontend(*args,**kwargs):\n hybrid_owned_run(synthetic_args,{},invocation_id="a"*32)\n'
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);strict=out/'strict.json';strict.write_text('{}')
            core=out/'core';core.write_bytes(b'core')
            (out/'native-driver.py').write_text(native);(out/'frontend-driver.py').write_text(frontend)
            (out/'preparation.json').write_text(json.dumps({'strict_path':str(strict),
                'strict_sha256':p.q._sha256_path(strict),'implementation':{}}))
            smoke=mock.Mock();smoke.validate_inputs.return_value=(None,core,None,{})
            with mock.patch.object(p.h,'source_identity',return_value={}), \
                 mock.patch.object(p,'derived_sources',return_value=(native,frontend)), \
                 mock.patch.object(p.q,'_load_retroarch_smoke',return_value=smoke), \
                 mock.patch.object(p.q,'_active_frontend_sources',return_value={}), \
                 mock.patch.dict(p.q.__dict__,synthetic_args=argparse.Namespace(capture_dir=Path('relative'))), \
                 mock.patch.object(p,'preview_configuration',side_effect=ValueError('invalid cfg')):
                with self.assertRaises(ValueError):p.calibrate(out)
            smoke.run_mvs_active_scene.assert_not_called()
            self.assertFalse((out/'acquisition-intent.json').exists())


if __name__ == '__main__':
    unittest.main()
