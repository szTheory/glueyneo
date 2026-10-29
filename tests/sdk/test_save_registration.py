#!/usr/bin/env python3
"""Fail-closed registration and measurement checks for the recurring save suite."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("verify_sdk", ROOT / "tools/verify_sdk.py")
assert SPEC is not None and SPEC.loader is not None
VERIFY = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VERIFY
SPEC.loader.exec_module(VERIFY)
DOC_SPEC = importlib.util.spec_from_file_location(
    "save_process_docs", ROOT / "tests/sdk/test_save_process.py")
assert DOC_SPEC is not None and DOC_SPEC.loader is not None
DOCS = importlib.util.module_from_spec(DOC_SPEC)
sys.modules[DOC_SPEC.name] = DOCS
DOC_SPEC.loader.exec_module(DOCS)


class SaveRegistrationTests(unittest.TestCase):
    assertion_count = 0

    def test_save_suite_runs_serial_after_parallel_recovery_timeout(self) -> None:
        source = (ROOT / "tools/verify_sdk.py").read_text(encoding="utf-8")
        save_suite = source.split("def suite_save()", 1)[1].split("def suite_frontend()", 1)[0]
        self.assertEqual(VERIFY.SAVE_CTEST_WORKERS, 1)
        self.assertIn('"--parallel", str(SAVE_CTEST_WORKERS)', save_suite)

    def __getattribute__(self, name: str):
        attribute = super().__getattribute__(name)
        if name.startswith("assert") and callable(attribute):
            def count_assertion(*args, **kwargs):
                type(self).assertion_count += 1
                return attribute(*args, **kwargs)
            return count_assertion
        return attribute

    @staticmethod
    def ctest_output(*, host_supported: bool = True) -> tuple[str, dict[str, object]]:
        identity: dict[str, object] = {"source_revision": "abcdef0123456789"}
        native = [
            ("sdk_save_api", 'SDK_RESULT {"outcome":"pass","cases":3,"assertions":12,"identity":{"source_revision":"abcdef012345","configuration":"Debug","sanitizer":"NONE"}}'),
            ("sdk_save_receipts", "save receipts passed: positive cases=3 assertions=25; negative control=save.pending-newer"),
            ("sdk_save_lifecycle", 'SDK_RESULT {"outcome":"pass","cases":6,"assertions":36,"identity":{"source_revision":"abcdef012345","configuration":"Debug","sanitizer":"NONE"}}'),
            ("sdk_save_registration", "Ran 4 tests in 0.010s\nOK\n"
             'SAVE_PYTHON_RESULT {"tests":4,"assertions":25}'),
        ]
        host = []
        for name in sorted(VERIFY.SAVE_DARWIN_REQUIRED_CASES):
            if host_supported:
                body = ("Ran 2 tests in 0.010s\nOK\n"
                        'SAVE_PYTHON_RESULT {"tests":2,"assertions":40}')
            else:
                body = f"{len(native) + len(host) + 1}/7 Test #{len(native) + len(host) + 1}: {name} ***Skipped 0.01 sec"
            host.append((name, body))
        rows = native + host
        blocks = []
        for index, (name, body) in enumerate(rows, start=1):
            if name not in VERIFY.SAVE_DARWIN_REQUIRED_CASES or host_supported:
                body_lines = "\n".join(f"{index}: {line}" for line in body.splitlines())
                outcome = "Passed"
            else:
                body_lines = body
                outcome = "***Skipped"
            blocks.append(
                f"Start {index}: {name}\n{body_lines}\n{index}/{len(rows)} Test #{index}: {name} {outcome} 0.01 sec")
        return "\n".join(blocks) + f"\n100% tests passed out of {len(rows)}\n", identity

    def test_save_suite_exposes_fail_closed_case_and_measurement_contract(self) -> None:
        required = (
            "SAVE_NATIVE_REQUIRED_CASES",
            "SAVE_DARWIN_REQUIRED_CASES",
            "validate_save_ctest_output",
            "suite_save",
        )
        missing = [name for name in required if not hasattr(VERIFY, name)]
        self.assertEqual(missing, [], f"save suite is missing required contract: {missing}")
        for path in ("src/sdk_private.h", "tests/sdk/save_controls.py",
                     "tests/sdk/save_fixture.c", "tests/sdk/save_fixture.h",
                     "tests/sdk/test_support.h", "tests/sdk/test_save_process.py",
                     "tests/sdk/test_save_registration.py", "tools/verify_sdk.py"):
            self.assertIn(path, VERIFY.SAVE_SOURCE_PATHS,
                          f"save evidence identity omitted harness source {path}")

    def test_darwin_filesystem_observation_uses_mounted_volume_type(self) -> None:
        outputs = [
            "Filesystem 512-blocks Used Available Capacity Mounted on\n"
            "/dev/diskX 100 50 50 50% /System/Volumes/Data\n",
            "/dev/diskX on /System/Volumes/Data (apfs, local, journaled)\n",
        ]
        with mock.patch.object(VERIFY, "run", side_effect=[
            mock.Mock(stdout=outputs[0]), mock.Mock(stdout=outputs[1]),
        ]) as run:
            self.assertEqual("APFS", VERIFY.darwin_filesystem_type(ROOT))
        self.assertEqual(["df", "mount"], [call.args[0][0] for call in run.call_args_list])

        with mock.patch.object(VERIFY, "run", side_effect=[
            mock.Mock(stdout=outputs[0]), mock.Mock(stdout="/dev/diskX on / (apfs)\n"),
        ]):
            with self.assertRaises(VERIFY.VerificationError):
                VERIFY.darwin_filesystem_type(ROOT)

    def test_save_rights_manifest_binds_current_and_immutable_sources(self) -> None:
        document = json.loads((ROOT / "tests/fixture/rights-manifest.json").read_text())
        self.assertGreater(VERIFY.verify_save_fixture_rights(ROOT, document), 0)

        stale_source = json.loads(json.dumps(document))
        stale_source["mvs_save_fixture"]["assertion_sources"][0]["sha256"] = "0" * 64
        with self.assertRaises(VERIFY.VerificationError):
            VERIFY.verify_save_fixture_rights(ROOT, stale_source)

        unsupported_rights = json.loads(json.dumps(document))
        unsupported_rights["mvs_save_fixture"]["rights"]["game_rom_or_commercial_bytes"] = True
        with self.assertRaises(VERIFY.VerificationError):
            VERIFY.verify_save_fixture_rights(ROOT, unsupported_rights)

        overclaimed_oracle = json.loads(json.dumps(document))
        overclaimed_oracle["mvs_save_fixture"]["oracle"]["physical_power_loss"] = "qualified"
        with self.assertRaises(VERIFY.VerificationError):
            VERIFY.verify_save_fixture_rights(ROOT, overclaimed_oracle)

    def test_lifecycle_result_abi_size_is_bound_to_source_assertion(self) -> None:
        source = (ROOT / "src/instance.c").read_text()
        sizes = DOCS._save_record_sizes_from_source(source)
        self.assertEqual(8, sizes["gn_mvs_save_lifecycle_result_v1"])

        missing_assertion = source.replace(
            '_Static_assert(sizeof(gn_mvs_save_lifecycle_result_v1) == 8u,\n'
            '               "MVS save lifecycle result v1 layout must stay fixed");\n',
            "",
        )
        with self.assertRaises(DOCS.SaveDocsError):
            DOCS._save_record_sizes_from_source(missing_assertion)

    def test_suite_identity_guard_rejects_source_and_rights_drift(self) -> None:
        self.assertIsNone(VERIFY.require_save_evidence_identity_stable(
            "source-a", "source-a", "rights-a", "rights-a"))
        with self.assertRaisesRegex(VERIFY.VerificationError, "sources changed"):
            VERIFY.require_save_evidence_identity_stable(
                "source-a", "source-b", "rights-a", "rights-a")
        with self.assertRaisesRegex(VERIFY.VerificationError, "rights manifest changed"):
            VERIFY.require_save_evidence_identity_stable(
                "source-a", "source-a", "rights-a", "rights-b")

    def test_exact_case_and_positive_assertion_inventory(self) -> None:
        output, identity = self.ctest_output()
        observed = VERIFY.validate_save_ctest_output(
            output, host_supported=True, identity=identity)
        self.assertEqual(set(observed["named_tests"]),
                         VERIFY.SAVE_NATIVE_REQUIRED_CASES | VERIFY.SAVE_DARWIN_REQUIRED_CASES)
        self.assertEqual(observed["per_case_assertions"]["sdk_save_api"], 12)
        self.assertGreater(observed["assertions"], 0)
        self.assertEqual(observed["host_qualification"], "qualified")

    def test_unsupported_host_is_recorded_without_qualifying_darwin(self) -> None:
        output, identity = self.ctest_output(host_supported=False)
        observed = VERIFY.validate_save_ctest_output(
            output, host_supported=False, identity=identity)
        self.assertEqual(observed["host_qualification"], "unsupported")
        self.assertEqual(set(observed["unsupported_host_cases"]),
                         VERIFY.SAVE_DARWIN_REQUIRED_CASES)
        self.assertTrue(all(observed["per_case_assertions"][name] == 0
                            for name in VERIFY.SAVE_DARWIN_REQUIRED_CASES))

    def test_portable_host_preserves_measured_darwin_rows_and_loss_limits(self) -> None:
        path = "docs/native-save.md"
        document = (ROOT / path).read_text(encoding="utf-8")
        source_identity = VERIFY.save_source_identity(ROOT)
        document = DOCS._replace_table_row_cell(
            document, "Measurements and pending evidence", "Claim",
            "save_source_identity_sha256", "Value", source_identity)
        mutations = {
            "omitted stage": DOCS._replace_table_row_cell(
                document, "Measurements and pending evidence", "Claim",
                "host_stage_trace", "Value", "temp-created,write,rename"),
            "linux claimed qualified": DOCS._replace_table_row_cell(
                document, "Measurements and pending evidence", "Claim",
                "tested_host_identity", "Value", "Linux 6.x / ext4; host protocol qualified"),
            "stale source identity": DOCS._replace_table_row_cell(
                document, "Measurements and pending evidence", "Claim",
                "save_source_identity_sha256", "Value", "0" * 64),
            "missing physical loss boundary": DOCS._remove_table_row(
                document, "Measurements and pending evidence", "Claim",
                "physical_board_or_game_save_behavior"),
        }
        lines = document.splitlines()
        identity_index = next(index for index, line in enumerate(lines)
                              if line.startswith("| `tested_host_identity` |"))
        duplicate_row = lines.copy()
        duplicate_row.insert(identity_index + 1, duplicate_row[identity_index])
        mutations["duplicate host identity row"] = "\n".join(duplicate_row) + "\n"
        pending_index = next(index for index, line in enumerate(lines)
                             if line.startswith("| `physical_board_or_game_save_behavior` |"))
        extra_row = lines.copy()
        extra_row.insert(pending_index + 1,
                         "| `unexecuted_host_claim` | measured | Linux host protocol qualified |")
        mutations["extra host qualification row"] = "\n".join(extra_row) + "\n"
        with mock.patch.object(VERIFY, "verify_save_fixture_rights", return_value=1), \
                mock.patch.object(VERIFY, "save_source_identity", return_value=source_identity):
            self.assertGreater(sum(VERIFY._portable_save_docs_counts(
                {path: document}).values()), 0)
            for name, candidate in mutations.items():
                with self.subTest(name=name), self.assertRaises(VERIFY.VerificationError):
                    VERIFY._portable_save_docs_counts({path: candidate})

    def test_portable_host_binds_all_supporting_save_contract_tables(self) -> None:
        def duplicate_row(document: str, heading: str, marker: str) -> str:
            lines = document.splitlines()
            heading_index = next(index for index, line in enumerate(lines)
                                 if line.lstrip("# ").strip() == heading)
            table_index = next(index for index in range(heading_index + 1, len(lines))
                               if lines[index].lstrip().startswith("|"))
            row_index = next(index for index in range(table_index, len(lines))
                             if marker in lines[index])
            lines.insert(row_index + 1, lines[row_index])
            return "\n".join(lines) + "\n"

        def extra_row(document: str, heading: str, row: str) -> str:
            lines = document.splitlines()
            heading_index = next(index for index, line in enumerate(lines)
                                 if line.lstrip("# ").strip() == heading)
            table_index = next(index for index in range(heading_index + 1, len(lines))
                               if lines[index].lstrip().startswith("|"))
            table_end = next(index for index in range(table_index, len(lines))
                             if not lines[index].lstrip().startswith("|"))
            lines.insert(table_end, row)
            return "\n".join(lines) + "\n"

        def replace_cell(document: str, heading: str, key_column: str,
                         key_value: str, value_column: str, replacement: str) -> str:
            lines = document.splitlines()
            heading_index = next(index for index, line in enumerate(lines)
                                 if line.lstrip("# ").strip() == heading)
            table_index = next(index for index in range(heading_index + 1, len(lines))
                               if lines[index].lstrip().startswith("|"))
            headers = [cell.strip().strip("`") for cell in
                       lines[table_index].strip().strip("|").split("|")]
            key_index = headers.index(key_column)
            value_index = headers.index(value_column)
            row_index = next(index for index in range(table_index + 1, len(lines))
                             if lines[index].lstrip().startswith("|") and
                             lines[index].strip().strip("|").split("|")[key_index]
                             .strip().strip("`") == key_value.strip("`"))
            cells = [cell.strip() for cell in lines[row_index].strip().strip("|").split("|")]
            cells[value_index] = replacement
            lines[row_index] = "| " + " | ".join(cells) + " |"
            return "\n".join(lines) + "\n"

        def remove_row(document: str, heading: str, key_column: str,
                       key_value: str) -> str:
            lines = document.splitlines()
            heading_index = next(index for index, line in enumerate(lines)
                                 if line.lstrip("# ").strip() == heading)
            table_index = next(index for index in range(heading_index + 1, len(lines))
                               if lines[index].lstrip().startswith("|"))
            headers = [cell.strip().strip("`") for cell in
                       lines[table_index].strip().strip("|").split("|")]
            key_index = headers.index(key_column)
            row_index = next(index for index in range(table_index + 1, len(lines))
                             if lines[index].lstrip().startswith("|") and
                             lines[index].strip().strip("|").split("|")[key_index]
                             .strip().strip("`") == key_value.strip("`"))
            del lines[row_index]
            return "\n".join(lines) + "\n"

        cases = {
            "docs/native-state.md": (
                "Durable save compatibility field",
                "Loaded profile", "GN_MVS_PROFILE_MSX",
                "| `Another profile` | 9 | Unqualified transfer |",
                replace_cell(
                    (ROOT / "docs/native-state.md").read_text(encoding="utf-8"),
                    "Durable save compatibility field", "Loaded profile",
                    "GN_MVS_PROFILE_MSX", "Meaning", "No durable-save transfer"),
            ),
            "docs/state-inventory.md": (
                "MVS save lineage and snapshot exclusion",
                "Owner item", "`gn_image.save_owner`",
                "| `unexpected_save_owner` | Host | No | No | Extra durable owner |",
                replace_cell(
                    (ROOT / "docs/state-inventory.md").read_text(encoding="utf-8"),
                    "MVS save lineage and snapshot exclusion", "Owner item",
                    "`gn_image.mvs_save_ram` contents", "GNSV durable bytes", "No"),
            ),
            "docs/ownership-and-errors.md": (
                "MVS durable save boundaries",
                "Operation", "Receipt ACK",
                "| Unexpected operation | None | Not a durable save contract |",
                replace_cell(
                    (ROOT / "docs/ownership-and-errors.md").read_text(encoding="utf-8"),
                    "MVS durable save boundaries", "Operation", "Receipt ACK",
                    "Ownership or error effect", "Clears dirty for any receipt"),
            ),
        }
        measured_source_identity = next(
            line.strip().strip("|").split("|")[2].strip().strip("`")
            for line in (ROOT / "docs/native-save.md").read_text(encoding="utf-8").splitlines()
            if line.startswith("| `save_source_identity_sha256` |"))
        with mock.patch.object(VERIFY, "verify_save_fixture_rights", return_value=1), \
                mock.patch.object(
                    VERIFY, "save_source_identity", return_value=measured_source_identity):
            valid_counts = VERIFY._portable_save_docs_counts()
            for path in ("docs/native-state.md", "docs/state-inventory.md",
                         "docs/ownership-and-errors.md"):
                self.assertGreater(valid_counts[path], 0, path)
            for path, (heading, key_column, row_marker, extra, contradiction) in cases.items():
                document = (ROOT / path).read_text(encoding="utf-8")
                missing = remove_row(document, heading, key_column, row_marker)
                mutations = {
                    "missing row": missing,
                    "duplicate row": duplicate_row(document, heading, row_marker),
                    "extra row": extra_row(document, heading, extra),
                    "contradictory row": contradiction,
                }
                for name, candidate in mutations.items():
                    with self.subTest(path=path, mutation=name), self.assertRaisesRegex(
                            VERIFY.VerificationError, "save.docs-ownership"):
                        VERIFY._portable_save_docs_counts({path: candidate})

    def test_portable_contract_mutations_cover_every_table_family(self) -> None:
        table_families = (
            ("docs/native-save.md", "Public records and operations",
             ("Kind", "Name"), ("record", "gn_mvs_save_scope_v1")),
            ("docs/native-save.md", "Numeric save reasons",
             ("Reason",), ("NONE",)),
            ("docs/native-save.md", "GNSV v1 envelope",
             ("Field",), ("Magic",)),
            ("docs/native-save.md", "Ownership and lifecycle",
             ("Event",), ("Successful ACK",)),
            ("docs/native-save.md", "Startup authoritative-slot outcomes",
             ("Outcome",), ("missing",)),
            ("docs/native-save.md", "Synchronous host commit order",
             ("Stage",), ("ack",)),
            ("docs/native-save.md", "Uncertain outcome resolution",
             ("Action",), ("retry",)),
            ("docs/native-save.md", "Malformed authoritative target regressions",
             ("Case",), ("truncated",)),
            ("docs/native-save.md", "Measurements and pending evidence",
             ("Claim",), ("fixture_bytes",)),
            ("docs/native-state.md", "Durable save compatibility field",
             ("Loaded profile",), ("GN_MVS_PROFILE_MSX",)),
            ("docs/state-inventory.md", "MVS save lineage and snapshot exclusion",
             ("Owner item",), ("gn_instance.mvs_save and its listed fields",)),
            ("docs/state-inventory.md", "Image and instance ownership (`src/instance.c`)",
             ("Structure and fields",), ("gn_image.save_owner",)),
            ("docs/ownership-and-errors.md", "MVS durable save boundaries",
             ("Operation",), ("Receipt ACK",)),
        )

        def table_parts(document: str, heading: str):
            lines = document.splitlines()
            heading_index = next(index for index, line in enumerate(lines)
                                 if line.lstrip("# ").strip() == heading)
            table_start = next(index for index in range(heading_index + 1, len(lines))
                               if lines[index].lstrip().startswith("|"))
            table_end = next((index for index in range(table_start + 1, len(lines))
                              if not lines[index].lstrip().startswith("|")), len(lines))
            headers = [cell.strip().strip("`") for cell in
                       lines[table_start].strip().strip("|").split("|")]
            return lines, table_start, table_end, headers

        def mutate(document: str, heading: str, key_columns: tuple[str, ...],
                   key_values: tuple[str, ...], kind: str) -> str:
            lines, table_start, table_end, headers = table_parts(document, heading)
            key_indexes = [headers.index(column) for column in key_columns]
            row_indexes = []
            for index in range(table_start + 2, table_end):
                cells = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
                if len(cells) == len(headers) and tuple(
                        cell.strip().replace("`", "") for cell in
                        (cells[key_index] for key_index in key_indexes)) == key_values:
                    row_indexes.append(index)
            if not row_indexes:
                raise AssertionError(f"could not find {key_values!r} in {heading!r}")
            target_index = row_indexes[0]
            if kind == "missing":
                del lines[target_index]
            elif kind in {"duplicate", "extra"}:
                cells = [cell.strip() for cell in
                         lines[target_index].strip().strip("|").split("|")]
                if kind == "duplicate":
                    insert = target_index + 1
                else:
                    if "Structure and fields" in key_columns:
                        cells[key_indexes[0]] = "gn_image.unexpected_save_owner"
                    else:
                        for offset, key_index in enumerate(key_indexes):
                            cells[key_index] = f"unexpected-contract-row-{offset}"
                    insert = table_end
                lines.insert(insert, "| " + " | ".join(cells) + " |")
            elif kind == "contradiction":
                cells = [cell.strip() for cell in
                         lines[target_index].strip().strip("|").split("|")]
                cells[-1] += "; appended contradictory contract claim"
                lines[target_index] = "| " + " | ".join(cells) + " |"
            else:
                raise AssertionError(f"unknown mutation {kind}")
            return "\n".join(lines) + "\n"

        source_identity = VERIFY.save_source_identity(ROOT)
        native_path = "docs/native-save.md"
        base_native = (ROOT / native_path).read_text(encoding="utf-8")
        base_native = DOCS._replace_table_row_cell(
            base_native, "Measurements and pending evidence", "Claim",
            "save_source_identity_sha256", "Value", source_identity)
        with mock.patch.object(VERIFY, "verify_save_fixture_rights", return_value=1), \
                mock.patch.object(VERIFY, "save_source_identity", return_value=source_identity):
            self.assertGreater(sum(VERIFY._portable_save_docs_counts(
                {native_path: base_native}).values()), 0)
            for path, heading, key_columns, key_values in table_families:
                original = base_native if path == native_path else (
                    ROOT / path).read_text(encoding="utf-8")
                for mutation in ("missing", "duplicate", "extra", "contradiction"):
                    candidate = mutate(original, heading, key_columns, key_values, mutation)
                    overrides = {native_path: base_native, path: candidate}
                    with self.subTest(path=path, table=heading, mutation=mutation), \
                            self.assertRaises(VERIFY.VerificationError):
                        VERIFY._portable_save_docs_counts(overrides)

    def test_save_host_posix_headers_are_inside_the_darwin_guard(self) -> None:
        source = (ROOT / "tests/sdk/save_host.c").read_text(encoding="utf-8")
        guard = source.index("#if defined(__APPLE__) && defined(F_FULLFSYNC)")
        for header in ("errno.h", "limits.h", "sys/stat.h", "unistd.h"):
            marker = f"#include <{header}>"
            self.assertIn(marker, source)
            self.assertGreater(source.index(marker), guard,
                               f"POSIX implementation header {header} is unguarded")

    def test_omitted_extra_duplicate_zero_control_and_source_drift_fail(self) -> None:
        output, identity = self.ctest_output()
        blocks = output.split("Start ")[1:]
        valid_blocks = ["Start " + block for block in blocks]
        mutations = {
            "omitted": "".join(valid_blocks[:-1]) + "100% tests passed out of 6\n",
            "duplicate": "".join(valid_blocks + [valid_blocks[0]]) + "100% tests passed out of 8\n",
            "extra": "".join(valid_blocks).replace(
                "100% tests passed out of 7", "Start 8: foreign\n8: SDK_RESULT {\"outcome\":\"pass\",\"cases\":1,\"assertions\":1}\n8/8 Test #8: foreign Passed 0.01 sec\n100% tests passed out of 8"),
            "zero assertions": output.replace('"assertions":12', '"assertions":0'),
            "zero Python assertions": output.replace(
                '"tests":4,"assertions":25', '"tests":4,"assertions":0'),
            "missing control": output.replace("negative control=save.pending-newer", "negative control=none"),
            "source identity drift": output.replace("abcdef012345", "eeeeeeffffff"),
        }
        for name, candidate in mutations.items():
            with self.subTest(name=name), self.assertRaises(VERIFY.VerificationError):
                VERIFY.validate_save_ctest_output(
                    candidate, host_supported=True, identity=identity)

    @staticmethod
    def measurement_observations() -> dict[str, object]:
        stages = ["temp-created", "partial-write", "write", "file-fullfsync",
                  "file-close", "rename", "directory-fsync", "directory-close",
                  "protocol-complete", "ack"]
        return {
            "fixture_bytes": 67_108_976,
            "fixture_sha256": "9cefb11420e190f5902e8861f5becda1c63c7ccd988118d7d93dc814a1b36690",
            "shared_media_identity": True,
            "host_stage_trace": "temp-created,write,file-fullfsync,file-close,rename,directory-open,directory-fsync,directory-close,ack",
            "recovery_kill_cases": [
                {"stage": stage, "prior_a": prior_a}
                for prior_a in (False, True) for stage in stages
            ],
            "writers": [{}, {}],
            "child_timeout_seconds": 15,
            "child_output_bound_bytes": 1_048_576,
            "suite_critical_path_seconds": 12.0,
            "host_identity": "macOS 26.6.2 / Darwin 25.6.0 / APFS",
            "save_source_identity_sha256": "a" * 64,
            "guest_fixture_source_sha256": "b" * 64,
            "build_identity": "AppleClang 18.0.0; Debug; SDK sanitizer NONE",
            "supported_sync_operations": "F_FULLFSYNC, checked close, rename, directory fsync",
            "host_fault_cases": "18 (9 syscall stages × first-create and A-to-B replacement)",
            "unsupported_host_protocol": "Linux/Windows host protocol unsupported; native-only tests",
        }

    @classmethod
    def measurement_document(cls) -> str:
        observations = cls.measurement_observations()
        recovery_cases = observations["recovery_kill_cases"]
        rows = {
            "fixture_bytes": ("measured", str(observations["fixture_bytes"])),
            "fixture_sha256": ("measured", str(observations["fixture_sha256"])),
            "shared_media_identity_a_b": ("measured", "true"),
            "host_stage_trace": ("measured", str(observations["host_stage_trace"])),
            "process_interruption_stage_cases": (
                "measured", "20 (10 publication stages × first-create and A-to-B replacement)"),
            "writer_reader_process_pairs": ("measured", "2"),
            "child_timeout_bound_seconds": ("bound", "15"),
            "child_output_bound_bytes": ("bound", "1048576"),
            "save_suite_critical_path_bound_seconds": ("bound", "900"),
            "tested_host_identity": ("measured", str(observations["host_identity"])),
            "save_source_identity_sha256": ("measured", str(observations["save_source_identity_sha256"])),
            "guest_fixture_source_sha256": ("measured", str(observations["guest_fixture_source_sha256"])),
            "build_identity": ("measured", str(observations["build_identity"])),
            "supported_sync_operations": ("measured", str(observations["supported_sync_operations"])),
            "host_fault_matrix_cases": ("measured", str(observations["host_fault_cases"])),
            "unsupported_host_protocol": ("bound", str(observations["unsupported_host_protocol"])),
            "peak_restore_staging_bytes": ("pending", "Not measured by this save-process witness"),
            "interrupted_commit_recovery": ("pending", "Only local process interruption is measured"),
            "physical_board_or_game_save_behavior": (
                "pending", "Physical power loss and board/game-save behavior not qualified"),
        }
        lines = ["## Measurements and pending evidence", "",
                 "| Claim | Status | Value |", "|-------|--------|-------|"]
        lines.extend(f"| {claim} | {status} | {value} |"
                     for claim, (status, value) in rows.items())
        return "\n".join(lines) + "\n"

    def test_actual_docs_helper_rejects_unobserved_measurement_mutations(self) -> None:
        observations = self.measurement_observations()
        manifest = json.loads((ROOT / "tests/fixture/rights-manifest.json").read_text())
        oracle = manifest["mvs_save_fixture"]["oracle"]
        source_identity = DOCS._save_manifest_source_identity(ROOT, manifest)
        observations.update({
            "host_identity": oracle["measured_host"],
            "save_source_identity_sha256": source_identity,
            "guest_fixture_source_sha256": VERIFY.evidence.sha256_file(
                ROOT / "tests/fixture/public_save_guest.c"),
            "build_identity": oracle["build_identity"],
            "supported_sync_operations":
                "F_FULLFSYNC, checked file close, atomic rename, directory fsync, and directory close",
            "host_fault_cases": "18 (9 syscall stages × first-create and A-to-B replacement)",
            "unsupported_host_protocol": oracle["unsupported_host_protocol"],
        })
        document = (ROOT / "docs/native-save.md").read_text(encoding="utf-8")
        document = DOCS._replace_table_row_cell(
            document, "Measurements and pending evidence", "Claim",
            "save_source_identity_sha256", "Value", source_identity)
        patched_checks = (
            "_check_api_docs", "_check_envelope_docs", "_check_host_order_docs",
            "_check_lifecycle_docs", "_check_snapshot_docs",
        )

        def check(candidate: str) -> None:
            with mock.patch.multiple(DOCS, **{name: mock.DEFAULT for name in patched_checks}):
                for name in patched_checks:
                    getattr(DOCS, name).return_value = 1
                DOCS.check_save_docs(
                    ROOT, observations, require_measured=True,
                    _document_overrides={"docs/native-save.md": candidate},
                    _run_mutations=False,
                )

        check(document)
        over_budget = dict(observations, suite_critical_path_seconds=900.01)
        with self.assertRaises(DOCS.SaveDocsError) as captured:
            with mock.patch.multiple(DOCS, **{name: mock.DEFAULT for name in patched_checks}):
                for name in patched_checks:
                    getattr(DOCS, name).return_value = 1
                DOCS.check_save_docs(
                    ROOT, over_budget, require_measured=True,
                    _document_overrides={"docs/native-save.md": document},
                    _run_mutations=False,
                )
        self.assertEqual(captured.exception.claim_id, "save.docs-measurements")
        mutations = {
            "omitted stage": DOCS._replace_table_row_cell(
                document, "Measurements and pending evidence", "Claim", "host_stage_trace",
                "Value", "temp-created,write,file-fullfsync,file-close,rename,directory-fsync"),
            "unexecuted host": DOCS._replace_table_row_cell(
                document, "Measurements and pending evidence", "Claim", "tested_host_identity",
                "Value", "Linux 6.x / ext4 / protocol qualified"),
            "changed source identity": DOCS._replace_table_row_cell(
                document, "Measurements and pending evidence", "Claim", "save_source_identity_sha256",
                "Value", "c" * 64),
            "understated measured bound": DOCS._replace_table_row_cell(
                document, "Measurements and pending evidence", "Claim", "child_output_bound_bytes",
                "Value", "1024"),
            "missing loss boundary": DOCS._remove_table_row(
                document, "Measurements and pending evidence", "Claim",
                "physical_board_or_game_save_behavior"),
        }
        for name, candidate in mutations.items():
            with self.subTest(name=name), self.assertRaises(DOCS.SaveDocsError) as captured:
                check(candidate)
            self.assertEqual(captured.exception.claim_id, "save.docs-measurements")
            self.assertIn("docs/native-save.md", str(captured.exception))


if __name__ == "__main__":
    SaveRegistrationTests.assertion_count = 0
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(SaveRegistrationTests))
    print("SAVE_PYTHON_RESULT " + json.dumps({
        "tests": result.testsRun,
        "assertions": SaveRegistrationTests.assertion_count,
    }, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
