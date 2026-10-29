import copy
import unittest
import hashlib
import json
import struct
import tempfile
import zlib
from pathlib import Path
from unittest import mock

from tools.mvs import hybrid_acceptance as h


class HybridPolicyTests(unittest.TestCase):
    def machine(self):
        value = {"policy": h.POLICY, "machine_status": "pass", "overall": "pending",
                 "human_semantics": "pending", "implementation": h.source_identity(),
                 "machine_gates": {n: "pass" for n in (*h.RETAINED, "combined_projectile", "native_combined", "joint_input_transfer_lifecycle")}}
        value["machine_identity"] = h.identity(value)
        return value

    def test_distinct_contract_preserves_original(self):
        strict = {"schedule": {"events": [0, 1]}, "contract_identity": "original"}
        before = copy.deepcopy(strict)
        derived = h.derive_contract(strict)
        self.assertEqual(before, strict)
        self.assertNotEqual(h.identity(strict), h.identity(derived))
        self.assertEqual(list(h.RETAINED), derived["retained_frontend_predicates"])

    def test_missing_feedback_remains_pending(self):
        with mock.patch.object(h, "machine_is_current", return_value=True):
            self.assertEqual("pending", h.review_feedback(self.machine(), None, None)["overall"])

    def test_human_cannot_override_failed_machine(self):
        machine = self.machine(); machine["machine_status"] = "fail"
        self.assertEqual("fail", h.review_feedback(machine, {}, {"outcome": "pass"})["overall"])

    def test_changed_machine_is_rejected(self):
        machine = self.machine(); machine["machine_gates"]["scene"] = "fail"
        self.assertEqual("fail", h.review_feedback(machine, {}, {})["overall"])

    def test_feedback_requires_exact_session_and_bounded_time(self):
        machine = self.machine()
        session = {"policy": h.POLICY, "machine_identity": machine["machine_identity"],
                   "status": "complete", "clean_exit": True, "artifact_sha256": "a" * 64}
        feedback = {"policy": h.POLICY, "machine_identity": machine["machine_identity"],
                    "session_identity": h.identity(session), "outcome": "pass", "viewing_seconds": 60}
        # This isolates feedback combination; real session validator has its own negatives.
        with mock.patch.object(h, "gameplay_session_valid", return_value=True), \
             mock.patch.object(h, "machine_is_current", return_value=True):
            self.assertEqual("pass", h.review_feedback(machine, session, feedback)["overall"])
            for key, bad in [("session_identity", "stale"), ("viewing_seconds", 0),
                             ("viewing_seconds", 121), ("viewing_seconds", True), ("outcome", "yes")]:
                broken = dict(feedback, **{key: bad})
                self.assertEqual("pending", h.review_feedback(machine, session, broken)["overall"])
            self.assertEqual("pending", h.review_feedback(machine, session, dict(feedback, outcome="unknown"))["overall"])
        self.assertFalse(h.gameplay_session_valid(session, machine))

    def test_real_manual_protocol_receipt_and_mutations(self):
        """Real parser, PNG decoder, interval binder and replay receipt validator.

        The receipt fixture exercises protocol admission, not actual RGB replay
        execution or human truth. Only the local file-ownership root is isolated.
        """
        replay = h.q._load_frontend_replay()
        smoke = h.q._load_retroarch_smoke()
        joint = h.joint_mask()
        iid = "a" * 32
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capdir = root / h.q.PHASE06_RUN_ROOT / ("run-" + iid) / "captures"
            capdir.mkdir(parents=True)
            def chunk(k, b):
                return struct.pack(">I", len(b)) + k + b + struct.pack(">I", zlib.crc32(k+b))
            raw = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 320,224,8,2,0,0,0)) +
                   chunk(b"IDAT", zlib.compress((b"\0" + b"\0" * 960) * 224)) + chunk(b"IEND",b""))
            records=[]
            def event(kind, sample, mask, video):
                records.append(dict(event_kind=kind, sample_sequence=sample, sampled_mask=mask,
                    successful_video_sequence=video, executed_cycles=video*100, invocation_id=iid))
            event("B",0,0,0);event("S",1,1,0);event("V",1,1,1);event("R",1,1,1)
            begin=1
            event("S",2,98,1);event("V",2,98,2);event("P",2,98,2);event("S",3,96,2)
            for seq in range(3,10): event("V",seq,0x60,seq)
            event("S",10,0,9);event("V",10,0,10);event("V",11,0,11);event("V",12,0,12)
            captures=[]
            for n,(lo,hi) in enumerate(((2,3),(4,5),(9,10))):
                path=capdir/(str(n)+".png");path.write_bytes(raw)
                first=next(i+1 for i,r in enumerate(records) if r['event_kind']=='V' and r['successful_video_sequence']==lo)
                last=next(i+1 for i,r in enumerate(records) if r['event_kind']=='V' and r['successful_video_sequence']==hi)
                binding=smoke.bind_manual_gameplay_capture(records[:first],records[:last],
                    invocation_id=iid,capture_sha256=hashlib.sha256(raw).hexdigest())
                captures.append(dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),target_frame=lo-2,**binding))
            sources={"core_sha256":"b"*64}
            app={"core_sha256":"b"*64}
            text='config_save_on_exit = "false"\n'
            row=dict(status="complete",frontend_exit_code=0,owned_child_reaped=True,identity=app,
                invocation_id=iid,input_mode="manual",manual_boot_policy="human_coin_start_from_boot_v1",handoff_record_count=begin,close_record_count=len(records),
                observations=records,captures=captures,active_origin_video_sequence=2,
                configuration_text=text,configuration_sha256=hashlib.sha256(text.encode()).hexdigest(),
                selected_bundle_sha256="c"*64)
            row["replay"]={"policy":replay.POLICY,"binding":replay.replay_binding("b"*64,"c"*64,row,"cfg"),
                "core_sha256":"b"*64,"bundle_sha256":"c"*64,"status":"pass",
                "captures":[dict(capture_sha256=c["sha256"],successful_video_interval=c["successful_video_interval"],
                                 matching_sequences=[c["successful_video_interval"][0]]) for c in captures]}
            machine=self.machine();machine.update(expected_sources=sources,expected_app_identity=app,
                expected_manual_configuration_identity="cfg", expected_bundle_sha256="c"*64)
            machine["machine_identity"]=h.identity({k:v for k,v in machine.items() if k!="machine_identity"})
            row.update(hybrid_policy=h.POLICY, hybrid_machine_identity=machine["machine_identity"])
            row["replay"]["policy"] = replay.MANUAL_POLICY
            row["replay"]["binding"] = replay.replay_binding("b"*64,"c"*64,row,"cfg")
            session=dict(policy=h.POLICY,session_kind="human_gameplay",machine_identity=machine["machine_identity"],status="complete",
                clean_exit=True,active_frames=10,invocation=row,sources=sources,configuration_identity="cfg")
            def seal(s):
                s["artifact_sha256"]=h.identity({"invocation":s["invocation"],"sources":s["sources"],
                    "configuration_identity":s["configuration_identity"],"machine_identity":machine["machine_identity"]})
            seal(session)
            with mock.patch.object(h.q,"PROJECT_ROOT",root), mock.patch.object(h.q,"ignored",return_value=True), \
                 mock.patch.object(h.q,"_load_frontend_replay",return_value=replay), \
                 mock.patch.object(h.q,"_load_retroarch_smoke",return_value=smoke), \
                 mock.patch.object(h,"joint_mask",return_value=joint), mock.patch.object(h.q,"_active_frontend_sources",return_value=sources):
                self.assertTrue(h.gameplay_session_valid(session,machine))
                bad=copy.deepcopy(session);bad["invocation"]["hybrid_machine_identity"]="d"*64
                bad["invocation"]["replay"]["binding"]=replay.replay_binding("b"*64,"c"*64,bad["invocation"],"cfg")
                seal(bad)
                self.assertFalse(h.gameplay_session_valid(bad,machine))
                for field,value in (("configuration_identity","stale"),("active_frames",1801)):
                    bad=copy.deepcopy(session);bad[field]=value;seal(bad)
                    self.assertFalse(h.gameplay_session_valid(bad,machine))
                for field,value in (("handoff_record_count",48),("close_record_count",begin),
                                    ("owned_child_reaped",False),("frontend_exit_code",1)):
                    bad=copy.deepcopy(session);bad["invocation"][field]=value;seal(bad)
                    self.assertFalse(h.gameplay_session_valid(bad,machine))
                bad=copy.deepcopy(session);bad["invocation"]["observations"][-1]["event_kind"]="X";seal(bad)
                self.assertFalse(h.gameplay_session_valid(bad,machine))
                bad=copy.deepcopy(session);bad["invocation"]["captures"][0]["path"]=str(root/"wrong.png");seal(bad)
                self.assertFalse(h.gameplay_session_valid(bad,machine))

    def test_old_machine_or_acquisition_implementation_is_not_current(self):
        machine=self.machine()
        self.assertFalse(h.machine_is_current(machine))  # No owned acquisition artifacts.
        contract={"schedule":{}}
        acquisition=h.prepare_acquisition(contract, {"core_sha256":"a"*64}, "cfg", {},
                                          manual_configuration_identity="manual")
        self.assertEqual("manual", acquisition["manual_configuration_identity"])
        self.assertEqual(h.identity(h.derive_contract(contract)), acquisition["policy_contract_identity"])
        self.assertEqual(h.source_identity(), acquisition["implementation"])


if __name__ == "__main__":
    unittest.main()
