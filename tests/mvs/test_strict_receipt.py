import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from tools.mvs import strict_receipt as s


class StrictReceiptTests(unittest.TestCase):
    def test_unknown_and_unsealed_receipts_reject(self):
        for value in (None,{}, {'receipt_kind':s.KIND}):
            self.assertFalse(s.validate_receipt(value))

    def test_truthful_route_rejects_same_parent_or_failed_predicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);report=p/'new-report.json';parent=p/'old-calibration.json'
            outcome={'predicates':{key:'pass' for key in s.PREDICATES}}
            report.write_text(json.dumps(outcome))
            (p/'original-strict-candidate.json').write_text(json.dumps({'report':str(report)}))
            command=['python3','-m','tools.mvs.hybrid_qualification','calibrate','--output',str(p)]
            (p/'calibration-process.json').write_text(json.dumps({'status':'complete','exit_code':0,'command':command}))
            contract={'contract_identity':'frozen','frontend':{'calibration_report':str(parent),'calibration_report_sha256':'old'}}
            (p/'strict-contract.json').write_text(json.dumps(contract))
            proof={'producer_report_path':str(report),'producer_report_sha256':s.q._sha256_path(report),'contract_identity':'frozen','parent_calibration_path':str(parent),'parent_calibration_sha256':'old','strict_predicates':copy.deepcopy(outcome['predicates'])}
            with mock.patch('tools.mvs.strict_producer_proof.validate_proof',return_value=proof), \
                 mock.patch.object(s.q,'validate_scene_contract',return_value=('active_scene_contract_valid',contract)):
                good=s.issue(p);self.assertEqual(command,good['actual_command'])
                self.assertTrue(s.validate_receipt(good))
                for field,value in [('parent_contract_identity','wrong'),('validation_proof',{}),('actual_command',['forged'])]:
                    bad=copy.deepcopy(good);bad[field]=value;bad['receipt_identity']=s.h.identity({k:v for k,v in bad.items() if k!='receipt_identity'})
                    self.assertFalse(s.validate_receipt(bad))
                outcome['predicates']['combined']='fail';report.write_text(json.dumps(outcome))
                with self.assertRaises(ValueError):s.issue(p)
                outcome['predicates']['combined']='pass';report.write_text(json.dumps(outcome))
                contract['frontend']['calibration_report']=str(report);(p/'strict-contract.json').write_text(json.dumps(contract))
                with self.assertRaises(ValueError):s.issue(p)


if __name__=='__main__':unittest.main()
