# Testing

## Unit Tests (21 tests)

| Test Class | Tests | Coverage |
|------------|-------|----------|
| TestBlockHeader | 2 | Pack/unpack roundtrip |
| TestAllocator | 9 | Basic malloc/free operations |
| TestCoalescing | 2 | Adjacent block merging |
| TestFragmentation | 2 | Fragmentation bound |
| TestNoDoubleAlloc | 1 | P1 property |
| TestAlignment | 1 | P2 property |
| TestVerifyHarness | 2 | Harness correctness |
| TestMutationGates | 2 | M1/M2 mutation detection |

## Verification Harness

```
malloclab verify --seed 42 --trials 100
  P1_no_double_alloc:    PASS
  P2_alignment:          PASS
  P3_no_wild_writes:     PASS
  P4_coalescing:         PASS
  P5_fragmentation:      PASS
  M1_broken_coalescing:  DETECTED
  M2_broken_alignment:   DETECTED
  Overall: PASS
```

## Security Audit

- ruff: All checks passed
- bandit: 0 high/medium, 1 low (documented)