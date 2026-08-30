# Project Specification

## Overview
malloclab is a verified memory allocator with fragmentation bounds. It implements an explicit-free-list allocator and proves correctness properties via a deterministic simulation harness.

## Components

### BlockHeader
- 32-byte header: size (8) + prev (8) + next (8) + free (1) + padding (7)
- Pack/unpack via struct

### Allocator
- `__init__(heap_size)`: Initialize heap with one large free block
- `malloc(size)`: First-fit allocation with block splitting
- `free(ptr)`: Mark free, add to free list, coalesce adjacent
- `get_live_blocks()`: Walk heap, return allocated blocks
- `get_free_blocks()`: Walk heap, return free blocks
- `fragmentation()`: Calculate external fragmentation

### Verification Harness
- P1: No double-allocation
- P2: Alignment (16-byte)
- P3: No wild writes
- P4: Coalescing
- P5: Fragmentation bound
- M1: Broken coalescing mutation
- M2: Broken alignment mutation

## CLI
- `malloclab demo`: Run demonstration
- `malloclab verify --seed N --trials T`: Run verification harness