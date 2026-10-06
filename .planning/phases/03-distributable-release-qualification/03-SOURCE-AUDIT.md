# Phase 03 source coverage audit

Every in-scope source item has an executable plan. External repository authority and unknown rights are planned as explicit pending evidence, never inferred from a local pass.

| Source | ID | Item | Plan | Status |
|---|---|---|---|---|
| GOAL | — | Download complete unsigned exact-commit SDK, rebuild or relocate and reproduce diagnostic under truthful claims | 03-01, 03-03, 03-04, 03-05 | COVERED |
| REQ | BUILD-03 | Offline archive rebuild and relocated real consumer | 03-01, 03-04 | COVERED |
| REQ | BUILD-04 | Exact matrix identities and all outcomes | 03-03, 03-05 | COVERED |
| REQ | DEL-01 | Always-started aggregate, classifier, counts and measured cost | 03-03, 03-05 | COVERED |
| REQ | DEL-02 | Protected current-SHA checks, independent review, fork/App authority and triage | 03-03, 03-05 | COVERED; hosted receipt pending |
| REQ | DEL-03 | Manifest version, exact commit, complete recoverable draft | 03-01, 03-04 | COVERED; hosted receipt pending |
| REQ | DEL-04 | Downloaded digest/consumer before publication | 03-01, 03-04 | COVERED; hosted receipt pending |
| REQ | DEL-05 | Privacy/content scan, notices, provenance and rights | 03-02, 03-04 | COVERED; any unresolved item remains excluded |
| RESEARCH | Stack | CMake 3.20/preset 2, Python standard library, full-SHA actions, stable runner image labels | 03-01, 03-02, 03-03, 03-04 | COVERED |
| RESEARCH | Architecture | One always-started required aggregate with conservative classifier | 03-03 | COVERED |
| RESEARCH | Architecture | Read-only fork boundary and scoped trusted App authority | 03-03, 03-04, 03-05 | COVERED |
| RESEARCH | Architecture | Serialized idempotent release state machine and same-workflow dependencies | 03-04 | COVERED |
| RESEARCH | Architecture | Bounded scanner and safe archive traversal; separate legal rights | 03-01, 03-02 | COVERED |
| RESEARCH | Pitfalls | Mutable tool images, stale/absent check, privileged PR execution | 03-03, 03-05 | COVERED |
| RESEARCH | Pitfalls | No-new-release retry, artifact mode/asset mixture, Windows inspector, version drift | 03-01, 03-04 | COVERED |
| RESEARCH | Validation | Offline release consumer, exact matrix, CI policy, recovery and scanner canaries | 03-01 through 03-04 | COVERED |
| CONTEXT | D-01 | Three OS, four compiler lanes; Linux Clang sanitizer/fuzz | 03-03 | COVERED |
| CONTEXT | D-02 | Exact exercised support claims only | 03-03, 03-05 | COVERED |
| CONTEXT | D-03 | Unconditional aggregate, classifier, counts/cost | 03-03 | COVERED |
| CONTEXT | D-04 | Windows export inspection parity | 03-01 | COVERED |
| CONTEXT | D-05 | Read-only fork PR and first-time approval | 03-03, 03-05 | COVERED |
| CONTEXT | D-06 | Protected current-SHA main, native auto-merge | 03-05 | COVERED |
| CONTEXT | D-07 | Separate exact-SHA GSD code review and findings | 03-05 | COVERED |
| CONTEXT | D-08 | Scoped App token and hosted event proof | 03-04, 03-05 | COVERED; hosted receipt pending |
| CONTEXT | D-09 | Root manifest owns CMake/package version; pinned release-please schema | 03-01, 03-04 | COVERED |
| CONTEXT | D-10 | Exact commit, offline source and complete per-OS SDK archives | 03-01, 03-04 | COVERED |
| CONTEXT | D-11 | Serialized idempotent draft recovery and same-workflow needs | 03-04 | COVERED |
| CONTEXT | D-12 | Download, digest, offline rebuild, relocation and diagnostic before App publish | 03-01, 03-04 | COVERED |
| CONTEXT | D-13 | Standard-library scanner across public tree/history/log/archive classes | 03-02 | COVERED |
| CONTEXT | D-14 | Fail-closed bounds, redaction, canaries and detector limits | 03-02 | COVERED |
| CONTEXT | D-15 | Item-level redistribution records; unknown rights remain unknown | 03-02, 03-05 | COVERED |

## Spec-less edge flags

The supplied edge probe contains 12 unresolved/unclassified entries and no resolved edges. Keep the following as flagged assumptions until implementation tests or a user decision resolve each, with no inferred backstop: BUILD-03 unclassified; BUILD-04 unclassified; DEL-01 unclassified; DEL-02 adjacency, empty, ordering; DEL-03 boundary, precision; DEL-04 adjacency, empty, ordering; DEL-05 unclassified. The release-recovery tests in 03-04 explicitly exercise equal SHA/version, empty/duplicate asset sets, ordering invariance, and digest/size limits; these tests narrow technical behavior but do not silently change the probe's unresolved status.

## Prohibition recall

Project-specific prohibitions retained in plans: no commercial/private media in archives or public CI; no personal paths, private identities, machine identifiers or secret values in source/logs/artifacts; no rights claim from content scanning; no support claim from intended lanes or local authority substitutes; no privileged fork execution; no stale SHA merge; no publication of incomplete or wrong-commit assets. General security threats are assigned to the plan STRIDE registers.
