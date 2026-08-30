# Threat Model

## Threats
1. **Corrupted heap metadata**: Malformed headers could cause out-of-bounds access
2. **Double-free attacks**: Freeing same pointer twice to corrupt free list
3. **Fragmentation exhaustion**: Adversarial alloc/free patterns to degrade performance

## Mitigations
- All block headers are validated before traversal
- Double-free is silently ignored (idempotent)
- Fragmentation bound (MAX_FRAGMENTATION = 0.50) enforced by P5
- Zero external dependencies, no network I/O
- Deterministic seeded RNG for reproducible testing

## Assumptions
- Single-threaded usage (no concurrent access)
- Heap size is fixed at initialization
- No real memory addresses (simulated with bytearray)