"""Original strict predicates, truthful equivalent producer lineage.

No receipt/command is relabelled and no calibration is fitted to new pixels.
This narrowly proves the default source paths for the recorded nonmanual cohort.
"""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

from tools.mvs import hybrid_acceptance as h
from tools.mvs import hybrid_revalidation as bridge
from tools.mvs import qualify_local_boot as q

POLICY = "original_strict_equivalent_producer_proof_v1"


def require(value, why):
    if not value: raise ValueError(why)


def find_source(path, expected_hash):
    commits = subprocess.run(['git','log','--all','--format=%H','--',path],cwd=q.PROJECT_ROOT,
        capture_output=True,check=True,timeout=5).stdout.decode().splitlines()
    for commit in commits:
        data=subprocess.run(['git','show',commit+':'+path],cwd=q.PROJECT_ROOT,
            capture_output=True,check=True,timeout=5).stdout
        if hashlib.sha256(data).hexdigest()==expected_hash:return commit,data
    raise ValueError('frozen source unavailable')


def collector_projection(source):
    tree=ast.parse(source)
    for node in tree.body:
        if isinstance(node,ast.FunctionDef) and node.name=='_run_mvs_active_scene_impl':
            for i,arg in reversed(list(enumerate(node.args.kwonlyargs))):
                if arg.arg=='manual_handoff':
                    default=node.args.kw_defaults[i]
                    require(isinstance(default,ast.Constant) and default.value is None,'manual default changed')
                    del node.args.kwonlyargs[i];del node.args.kw_defaults[i]
    return bridge.projection(ast.unparse(tree),'collector')


class StrictReplayProjection(ast.NodeTransformer):
    def __init__(self):self.function=None
    def visit_FunctionDef(self,node):
        previous=self.function;self.function=node.name
        node=self.generic_visit(node)
        if node.name=='_evidence' and len(node.body)>=2:
            a,b=node.body[-2:]
            if (isinstance(a,ast.Assign) and len(a.targets)==1 and isinstance(a.targets[0],ast.Name) and a.targets[0].id=='result' and
                isinstance(b,ast.Return) and isinstance(b.value,ast.Name) and b.value.id=='result'):
                node.body[-2:]=[ast.Return(value=a.value)]
        self.function=previous
        return node
    def visit_Assign(self,node):
        name=node.targets[0].id if len(node.targets)==1 and isinstance(node.targets[0],ast.Name) else None
        if name=='MANUAL_POLICY' and self.function is None:
            require(isinstance(node.value,ast.Constant) and node.value.value=='manual_sampled_input_rgb_replay_v1','unknown manual policy')
            return None
        if self.function=='_evidence' and name=='manual':
            expected=ast.parse('manual = (invocation.get("input_mode") == "manual" and invocation.get("hybrid_policy") == "frontend_joint_delivery_human_semantics_v1" and _hash(invocation.get("hybrid_machine_identity")))').body[0]
            require(ast.dump(node)==ast.dump(expected),'manual dispatch changed')
            return None
        if self.function=='_evidence' and name=='maximum_interval':
            require(ast.dump(node.value)==ast.dump(ast.parse('64 if manual else 12',mode='eval').body),'interval policy changed')
            return None
        if (self.function=='validate_receipt' and name=='policy' or self.function=='_worker' and name=='evidence'):
            expected=('_evidence(core_sha256, bundle_sha256, invocation, configuration_identity)["policy"]'
                      if name=='policy' else '_evidence(core["sha256"], bundle_hash, invocation, identity)')
            require(ast.dump(node.value)==ast.dump(ast.parse(expected,mode='eval').body),'extra validation dispatch changed')
            return None
        return self.generic_visit(node)
    def visit_If(self,node):
        if self.function=='_evidence' and isinstance(node.test,ast.Name) and node.test.id=='manual':return []
        return self.generic_visit(node)
    def visit_IfExp(self,node):
        if isinstance(node.test,ast.Name) and node.test.id=='manual':return self.visit(node.orelse)
        return self.generic_visit(node)
    def visit_Name(self,node):
        if isinstance(node.ctx,ast.Load) and self.function=='_evidence' and node.id=='maximum_interval':return ast.Constant(12)
        if isinstance(node.ctx,ast.Load) and self.function=='validate_receipt' and node.id=='policy':return ast.Name(id='POLICY',ctx=ast.Load())
        return node
    def visit_Subscript(self,node):
        if (self.function=='_worker' and isinstance(node.value,ast.Name) and node.value.id=='evidence' and
            isinstance(node.slice,ast.Constant) and node.slice.value=='policy'):
            return ast.Name(id='POLICY',ctx=ast.Load())
        return self.generic_visit(node)


def replay_projection(source):
    return ast.dump(StrictReplayProjection().visit(ast.parse(source)),include_attributes=False)


def _report_pixels(report, sources, cfg, schedule):
    runs={};replay=q._load_frontend_replay();identifiers=set()
    for row in report['invocations']:
        require(row.get('input_mode') not in ('manual','automated_diagnostic') and
            not any(k in row for k in ('hybrid_policy','hybrid_machine_identity')),'manual evidence is not strict')
        iid=row['invocation_id'];require(iid not in identifiers,'duplicate invocation');identifiers.add(iid)
        require(row['status']=='complete' and row['frontend_exit_code']==0 and len(row['captures'])==6,'incomplete role')
        events=q._active_scene_input_events(schedule,row['pair'],row['role'])
        require(q._active_frontend_events_valid(row,events,iid),'parent input history invalid')
        for target,capture in zip(schedule['pairs'][row['pair']]['capture_frames'],row['captures']):
            mask=next((m for f,m in reversed(events) if f<=target),0)
            require(q.active_scene_frontend_capture_is_valid(capture,row['observations'],invocation_id=iid,
                expected_mask=mask,origin=row['active_origin_video_sequence'],target_frame=target),'parent capture interval invalid')
        require(all(h._owned_capture(c,iid) for c in row['captures']),'capture ownership/hash')
        bridge.producer_transfer(row,sources,cfg)
        runs.setdefault(row['pair'],{})[row['role']]=[replay._capture_rgb(c) for c in row['captures']]
    require(len(identifiers)==10 and {(r['pair'],r['role']) for r in report['invocations']}==
        {(p,r) for p in q._ACTIVE_SCENE_PAIR_NAMES for r in ('action','control')},'role coverage')
    runs['scene']={'status':'complete','t0':runs['right']['control'][0],'endpoint':runs['right']['control'][-1]}
    return runs


def validate_proof(profile):
    profile=Path(profile).resolve()
    reevaluation=bridge.create_bridge(profile)
    machine=json.loads((profile/'machine-calibration.json').read_text())
    contract=json.loads((profile/'strict-contract.json').read_text());front=contract['frontend']
    require(front['frozen'] is True and front['semantic_review']=='observed','original semantic freeze missing')
    parent_path=Path(front['calibration_report']);parent=json.loads(parent_path.read_text())
    require(bridge.digest(parent_path)==front['calibration_report_sha256'] and parent['status']=='complete' and
        parent['sources']==front['sources'] and parent['temporal_alignment']=='pass','original calibration changed')
    require(front['composition_policy']==q.FRONTEND_COMPOSITION_POLICY and
        front['schedule_policy']=='same_controls_bounded_retiming_v1' and
        front['native_schedule_identity']==q.active_scene_configuration_identity(contract['schedule']) and
        parent['native_contract_identity']==q._active_frontend_native_identity(contract) and
        parent['frontend_schedule_identity']==q.active_scene_configuration_identity(front['schedule']) and
        parent['media_identity']==contract['media_identity'] and parent['app_identity']==front['app_identity'] and
        parent['configuration_identity']==front['configuration_identity'],'original frozen parent graph mismatch')
    require(front['reviewed_capture_identity'] in {c['sha256'] for r in parent['invocations'] for c in r['captures']},'original reviewed capture absent')
    require(front['sources']['core_sha256']==machine['expected_sources']['core_sha256'] and
        front['sources']['evaluator']==machine['expected_sources']['evaluator'],'original native/core evaluator changed')
    epochs={}
    for path,key,project in [('tests/libretro/retroarch_smoke.py','collector_sha256',collector_projection),
                             ('tools/mvs/frontend_replay.py','replay_sha256',replay_projection)]:
        commit,old=find_source(path,front['sources'][key]);produced=bridge.git_source(path)
        require(hashlib.sha256(produced).hexdigest()==machine['expected_sources'][key],'producer source hash changed')
        require(project(old)==project(produced),'original automated source differs: '+path)
        epochs[path]={'frozen_commit':commit,'frozen_hash':front['sources'][key],
            'producer_commit':bridge.PRODUCER,'producer_hash':machine['expected_sources'][key],'projection':'equivalent nonmanual default'}
    parent_runs=_report_pixels(parent,front['sources'],front['configuration_identity'],front['schedule'])
    evaluation={**contract,'schedule':front['schedule']}
    old_pred=q.evaluate_active_scene_pairs(evaluation,parent_runs,frontend_intervals=True);old_pred['composition']='pass'
    require(all(old_pred[n]=='pass' for n in (*h.RETAINED,'combined')),'original calibration predicates no longer pass')
    require(q._active_frontend_temporal_bounds_valid(front['schedule'],parent['invocations']),'original temporal coverage')
    ids={a['invocation_id'] for a in machine['capture_artifacts']};matches=[]
    for path in (q.PROJECT_ROOT/q.PHASE06_RUN_ROOT).glob('run-*/frontend-report.json'):
        row=json.loads(path.read_text())
        if {r.get('invocation_id') for r in row.get('invocations',[])}==ids:matches.append((path,row))
    require(len(matches)==1,'producer report ancestry ambiguous');path,report=matches[0]
    require(path.resolve()!=parent_path.resolve(),'same calibration/acceptance sample')
    require(report['contract_identity']==contract['contract_identity'] and
        report['configuration_identity']==front['configuration_identity'] and report['app_identity']==front['app_identity'] and
        report['frontend_schedule_identity']==q.active_scene_configuration_identity(front['schedule']) and
        report['native_contract_identity']==q._active_frontend_native_identity(contract),'frozen parent/profile mismatch')
    require(all(report['predicates'][n]=='pass' for n in (*h.RETAINED,'combined','overall')) and
        all(reevaluation['frontend_predicates'][n]=='pass' for n in (*h.RETAINED,'combined','overall')),'strict predicate failed')
    proof={'policy':POLICY,'profile':str(profile),'contract_identity':contract['contract_identity'],
        'parent_calibration_path':str(parent_path),'parent_calibration_sha256':bridge.digest(parent_path),
        'producer_report_path':str(path.relative_to(q.PROJECT_ROOT)),'producer_report_sha256':bridge.digest(path),
        'source_epochs':epochs,'current_bridge_identity':reevaluation['certificate_identity'],
        'strict_predicates':report['predicates'],'fitting':False,'same_calibration_sample':False,
        'proof_source_sha256':bridge.digest(__file__)}
    proof['proof_identity']=h.identity(proof)
    return proof


def proof_valid(profile, proof):
    try:return validate_proof(profile)==proof
    except (KeyError,TypeError,ValueError,OSError,RuntimeError,subprocess.SubprocessError):return False
