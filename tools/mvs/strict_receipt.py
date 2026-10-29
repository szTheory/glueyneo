"""Truthful equivalent-producer receipts for the unchanged strict predicates.

Legacy CLI receipts remain a separate exact-provenance route. This route never
renames calibration commands or rewrites frozen contracts and failed evidence.
"""
import copy
import json
from pathlib import Path

from tools.mvs import hybrid_acceptance as h
from tools.mvs import qualify_local_boot as q

KIND = "original_strict_equivalent_producer_v1"
PREDICATES = (*h.RETAINED, "combined", "overall")


def issue(profile):
    from tools.mvs.strict_producer_proof import validate_proof
    profile = Path(profile).resolve()
    proof = validate_proof(profile)
    candidate = json.loads((profile / "original-strict-candidate.json").read_text())
    execution = json.loads((profile / "calibration-process.json").read_text())
    if execution.get('status') != 'complete' or execution.get('exit_code') != 0:
        raise ValueError('producer did not complete')
    command=execution.get('command')
    if (not isinstance(command,list) or len(command)!=6 or
        command[:5]!=['python3','-m','tools.mvs.hybrid_qualification','calibrate','--output'] or
        Path(command[5]).resolve()!=profile):
        raise ValueError('unknown actual producer command')
    report = json.loads((q.PROJECT_ROOT / candidate['report']).read_text())
    contract = json.loads((profile / 'strict-contract.json').read_text())
    status,current_contract=q.validate_scene_contract(q.PHASE06_CONTRACT_PATH)
    if status!='active_scene_contract_valid' or current_contract!=contract:
        raise ValueError('current original contract/media graph differs')
    if ((q.PROJECT_ROOT/candidate['report']).resolve()!=(q.PROJECT_ROOT/proof['producer_report_path']).resolve() or
        q._sha256_path(q.PROJECT_ROOT/candidate['report'])!=proof['producer_report_sha256'] or
        contract['contract_identity']!=proof['contract_identity'] or
        Path(contract['frontend']['calibration_report']).resolve()!=Path(proof['parent_calibration_path']).resolve() or
        contract['frontend']['calibration_report_sha256']!=proof['parent_calibration_sha256']):
        raise ValueError('receipt report or parent differs from validated proof')
    if report['predicates'] != proof['strict_predicates']:
        raise ValueError('predicate context differs from validated proof')
    if not all(report['predicates'].get(k)=='pass' for k in PREDICATES):
        raise ValueError('original strict predicate failed')
    if (q.PROJECT_ROOT / candidate['report']).resolve() == Path(contract['frontend']['calibration_report']).resolve():
        raise ValueError('qualification cohort is parent calibration')
    value = {'receipt_kind':KIND,'status':'original_strict_qualified',
        'execution_mode':'equivalent_producer_strict_qualification',
        'actual_command':execution['command'],'producer_exit_code':execution['exit_code'],
        'producer_status':execution['status'],'profile':str(profile),
        'report':candidate['report'],'report_sha256':q._sha256_path(q.PROJECT_ROOT/candidate['report']),
        'parent_contract_identity':contract['contract_identity'],
        'parent_calibration_report':contract['frontend']['calibration_report'],
        'parent_calibration_sha256':contract['frontend']['calibration_report_sha256'],
        'predicate_results':report['predicates'],'validation_proof':proof,
        'validator_sha256':q._sha256_path(Path(__file__))}
    value['receipt_identity']=h.identity(value)
    return value


def validate_receipt(value):
    try:
        if not isinstance(value,dict) or value.get('receipt_kind')!=KIND:
            return False
        if value.get('receipt_identity') != h.identity({k:v for k,v in value.items() if k!='receipt_identity'}):
            return False
        return issue(value['profile']) == value
    except (KeyError,TypeError,ValueError,OSError,RuntimeError):
        return False


def record(profile):
    profile = Path(profile).resolve()
    receipt = issue(profile)
    if not validate_receipt(receipt):
        raise ValueError('new strict receipt did not validate')
    destination = profile/('original-strict-receipt-'+receipt['validator_sha256'][:12]+'.json')
    if destination.exists():
        raise ValueError('receipt output already exists')
    destination.write_text(json.dumps(receipt,indent=2)+'\n')
    index_path=q.PROJECT_ROOT/'local/qualification/phase06-current-execute-index.json'
    index=json.loads(index_path.read_text())
    backup=profile/('execute-index-before-strict-receipt-'+receipt['receipt_identity'][:12]+'.json')
    backup.write_bytes(index_path.read_bytes())
    index['current_frontend_acceptance']=receipt
    index['original_strict_receipt_path']=str(destination.relative_to(q.PROJECT_ROOT))
    index_path.write_text(json.dumps(index,indent=2)+'\n')
    return receipt
