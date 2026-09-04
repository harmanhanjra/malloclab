# Threat Model

## Threats
1. **Corrupted heap metadata**: Malformed headers could cause out-of-bounds access
2. **Double-free attacks**: Freeing same pointer twice to corrupt free list
3. **Forged free pointers**: Interior or out-of-range offsets could be interpreted as headers
4. **Fragmentation exhaustion**: Adversarial alloc/free patterns to degrade performance

## Mitigations
- `free()` checks an independent issued/live pointer registry before reading metadata
- Forged, interior, out-of-range, boolean, and non-integer pointers fail closed
- Double-free is silently ignored (idempotent)
- Fragmentation bound (MAX_FRAGMENTATION = 0.50) enforced by P5
- Zero external dependencies, no network I/O
- Deterministic seeded RNG for reproducible testing

## Assumptions
- Single-threaded usage (no concurrent access)
- Heap size is fixed at initialization
- No real memory addresses (simulated with bytearray)
- Direct mutation of the public `heap` bytearray can still corrupt metadata; this
  teaching allocator does not provide process-level memory isolation
