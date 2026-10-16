# P0 paired protocol validation

Controlled synthetic runs only; real adapters are unsupported.

| Agent | Case | Execution | Comparable | Public delta (on − off) |
| --- | --- | --- | --- | --- |
| demo | paired-dynamic-update-hard-001 | completed | True | 1.0 |

## Public answer checks

| Agent / case | Arm | Probe | Answer correct | Forbidden value not used (lexical) |
| --- | --- | --- | --- | --- |
| demo / paired-dynamic-update-hard-001 | memory_on | current-location | pass | pass |
| demo / paired-dynamic-update-hard-001 | memory_off | current-location | fail | pass |

## Specified-store checks (excluded from public delta)

| Agent / case | Arm | Check | Content constraint | Specified-store deletion | Global deletion proven |
| --- | --- | --- | --- | --- | --- |
| demo / paired-dynamic-update-hard-001 | memory_on | explicit-deletion | fail | fail | false |
| demo / paired-dynamic-update-hard-001 | memory_off | explicit-deletion | fail | unknown | false |

Answer correctness, lexical forbidden-value non-use and specified-store absence are separate in results.json.
Storage checks never enter the public delta. Execution completed does not imply storage or answers pass.

Only the controlled synthetic fixture executes; no real product-memory comparison.
Fixed on/off order, no repeated sampling or statistical inference.
Forbidden-value non-use is lexical in the declared answer scope; it does not prove semantic invalidation.
Store absence is limited to demo_memory_list; it does not prove global deletion.
File retention/reuse unsupported; no full six-dimension score or legacy GUI/report/rescore integration.
