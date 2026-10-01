# Preserved audit-output classification failure

The second fresh native collection rejected `cpu_audit_controls` because the
collector expected unittest text (`Ran 13 tests`). The existing host audit
CLI wraps the actual unittest run in JSON with `status` and `tests` fields.
The collector must parse that executed wrapper result, requiring status pass
and the exact 13-case denominator. Positive and failed-wrapper controls cover
this format; no expected count, CPU behavior or assertion is weakened.
All final lanes must be collected again on the corrected source identity.
