# Why This Memory Allocator?

"Build your own malloc" tutorials are everywhere — most stop at "it returned a pointer." None proves:
- That two mallocs never return the same live address
- That all pointers are properly aligned
- That freeing adjacent blocks actually coalesces them
- That fragmentation stays within provable bounds

This project fills the gap with a zero-dependency explicit-free-list allocator and a 7-gate verification harness.

## The Problem Space

Memory allocators are foundational systems software. Real-world allocators (jemalloc, tcmalloc, mimalloc) use sophisticated techniques — size classes, thread-local caches, huge pages. But the core invariant remains: **don't return the same address twice, and don't fragment memory into unusable slivers**.

## Why Verify?

A standard allocator test suite might check "can I malloc and free 1000 blocks without crashing?" But that's a happy path. It doesn't catch:
- Coalescing bugs that leak virtual address space over time
- Alignment violations that cause SIGBUS on architectures requiring it
- Fragmentation that degrades to O(n) allocation in long-running servers

## The Series Context

This is Cycle 31 of an autonomous R&D series. The series has filled:
- CodeSec (AI security review), HookDoctor (webhook diagnostics), Onboarder (checklist generator)
- TensorForge (autograd engine), RingProxy (consistent-hash LB), ConvergeKit (CRDTs)
- RaftLab (Raft consensus), PhoenixKV (WAL durability), RegexLab (Thompson-NFA)
- RegAllocLab (register allocation), SeedKit (BitTorrent), DnsCacheGuard (DNS poisoning)
- RankLab (BM25 search), Mergelab (3-way merge), QosLab (MQTT QoS)
- PhysLab (physics engine), GClab (garbage collection), Annlab (HNSW ANN index)
- Compresslab (LZ77+Huffman), Bftlab (BFT consensus), Mempoolab (mempool/MEV)
- Forklab (fork choice), Bloomlab (Bloom filter), Satlab (DPLL SAT solver)
- McpGuardLab (MCP security), TypeSoundLab (type inference)

malloclab opens the **Memory Allocator** pillar — first time a "build your own malloc" ships with a correctness harness proving no-double-alloc, alignment, coalescing, and fragmentation bounds.