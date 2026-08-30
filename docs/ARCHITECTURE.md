# Architecture

## Heap Layout

```
┌─────────────────────────────────────────────────────────────────┐
│                        Heap (bytearray)                         │
│  ┌──────────┬──────────┬──────────┬──────────┬────────────────┐ │
│  │ Header 0 │ Payload 0│ Header 1 │ Payload 1│     ...        │ │
│  │ (32 B)   │ (var)    │ (32 B)   │ (var)    │                │ │
│  └──────────┴──────────┴──────────┴──────────┴────────────────┘ │
│       ↑           ↑          ↑           ↑                      │
│       │           │          │           │                      │
│  free_list ←──────────────→ free_list                           │
│  (doubly-linked list of free blocks)                            │
└─────────────────────────────────────────────────────────────────┘
```

## Block Header Format (32 bytes)

```
┌────────────────┬────────────────┬────────────────┬───────────────┐
│ size (8 bytes) │ prev (8 bytes) │ next (8 bytes) │ free (1 byte) │
│ (signed int)   │ (ptr or -1)    │ (ptr or -1)    │ (0 or 1)      │
└────────────────┴────────────────┴────────────────┴───────────────┘
```

- `size`: Total block size including header (positive = allocated, negative = free)
- `prev`: Offset of previous free block in free list (-1 = none)
- `next`: Offset of next free block in free list (-1 = none)
- `free`: 1 if block is free, 0 if allocated

## Free List

Doubly-linked list of free blocks, sorted by address. New free blocks are added at the head.

## Allocation Strategy

1. **First-fit**: Walk free list, find first block large enough
2. **Split**: If block is larger than needed + MIN_BLOCK_SIZE, split into allocated + free remainder
3. **Return**: Payload pointer (block_offset + HEADER_SIZE)

## Deallocation Strategy

1. **Mark free**: Set free flag, add to free list
2. **Coalesce**: Merge with adjacent free blocks (both directions)

## Verification Strategy

Deterministic seeded simulation:
- Random sequence of malloc/free operations
- Property checks after each trial
- Mutation tests to prove harness non-vacuity