# Retrospective — malloclab (Cycle 31)

## What went well
- **Correct coalescing logic**: The `_coalesce` method properly handles both directions (next and previous block), which was the hardest part to get right.
- **Signed size field**: Using signed integers for block size simplifies the free-list traversal — negative sizes indicate free blocks, eliminating the need for a separate flag byte.
- **First-fit is adequate**: While not optimal, first-fit allocation is simpler to verify and the fragmentation bound (0.50) was achievable across all random workloads.

## Lessons learned
1. **Signed size field simplifies coalescing**: Using signed size (negative = free) avoids a separate flag byte and makes block traversal atomic.
2. **First-fit is correct but not optimal**: Best-fit would lower fragmentation but first-fit is simpler to verify and still meets the bound.
3. **Alignment must be enforced at header level**: If headers are aligned, payloads are aligned. Pad header to 32 bytes (not 16) to maintain 16-byte alignment of payloads.
4. **Mutation gates catch real bugs**: M1 (skip coalescing) was designed to catch regressions in the merge logic.
5. **Fragmentation bound is workload-dependent**: The 0.50 bound holds for random workloads; pathological patterns (alloc/free alternating sizes) can exceed it — document the assumption.

## Improvements for next cycle
- Best-fit allocation strategy for lower fragmentation
- Red-black tree free list for O(log n) search instead of O(n) linear scan
- Thread-safe version with lock verification
- Real-world workload traces (malloc trace replay from Linux/Windows allocators)
- Hypothesis fuzzing of alloc/free patterns
- Benchmark against system malloc (libc/mimalloc) to compare throughput

## Technical debt
- None — all tests pass, ruff clean, bandit clean
- The 32-byte header is larger than necessary (struct packing leaves 7 bytes padding) — could be reduced to 24 bytes with custom packing, but clarity is prioritized
- No support for huge allocations (>heap_size) — would need dynamic heap expansion

## Verification harness quality
- 21 tests covering all properties (P1-P5, M1-M2)
- Harness is deterministic (seeded RNG) and reproducible
- Mutation gates are non-vacuous (M1/M2 both detect their respective mutations)
- Boundary cases tested: zero-size, negative, too-large, double-free
