# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

---

## snapshot-inventory-mismatch — test children mutate the clean qualification snapshot during full-sdk-ctest
- **Date:** 2026-10-10
- **Error patterns:** snapshot-inventory-mismatch, materialized source inventory differs from archived member bytes, materialized source inventory changed after archive creation, generated-output-path-conflict, verify_snapshot, full-sdk-ctest, ym2610-installed-linkages, __pycache__, .pyc, python -I, PYTHONDONTWRITEBYTECODE, not a committed ancestor of the checked head, not committed at the checked head
- **Root cause(s):** run_script_entry ran `python -I -c`, and -I ignores PYTHONDONTWRITEBYTECODE, so the child wrote tools/__pycache__ into the snapshot; eight ReviewProvenanceTest cases read ROOT's Git history, which a snapshot does not have (no .git); run_script_entry ran the real snapshot verify_playable.py main(), whose OUTPUT.mkdir created empty build/playable-qualification dirs that the file-only inventory_tree missed, so the later overlay raised generated-output-path-conflict
- **Fix:** add -B to the entry child; add a skipUnless((ROOT / ".git").exists()) guard to the eight provenance tests; run_script_entry copies verify_playable.py and private_paths.py into a test-owned temporary root and runs that copy; refresh the rights inventory
- **Files changed:** tests/tools/test_verify_playable.py, docs/rights-inventory.md
- **Why not caught:** no gate existed for this class. Tool tests ran only inside the Git checkout, and verify_snapshot compares files only, not directories.
- **Recurrence guard:** tests/tools/test_verify_playable.py:test_entry_child_writes_nothing_into_the_source_tree; open follow-up to add a directory-set check to verify_snapshot. Pattern: the raise site of a shared reason token (create_snapshot vs verify_snapshot) can be misattributed, so check which lane the receipt last recorded.
---

