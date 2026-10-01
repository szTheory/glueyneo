# Preserved collection failure

At source revision 5ed70a6, native CTest execution passed but acceptance
collection rejected its truncated JUnit JSON with `Invalid control character
at: line 36 column 21 (char 1027)`. CTest's default passed-output limit was
1,024 bytes. The output ended with `[This part of the test output was removed
since it exceeds the threshold of 1024 bytes.]` inside a JSON string.

A separate native `cpu_closure` rerun passed in 3.69 seconds and reproduced
the same truncation. This is an evidence transport failure, not a passing
admission or a CPU counterexample. The correction sets an explicit finite
10 MiB per-case output limit and rejects any truncation marker. The control
tests cover rejection. All three final lanes must run again on the corrected
collector. No runtime code or frozen cap changed.
