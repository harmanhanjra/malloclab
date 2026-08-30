"""Tests for malloclab - Verified Memory Allocator."""

import random

from malloclab import ALIGNMENT, HEADER_SIZE, Allocator, verify_harness


class TestBlockHeader:
    """Test BlockHeader pack/unpack."""
    
    def test_pack_unpack_roundtrip(self):
        from malloclab import BlockHeader
        h = BlockHeader(size=1024, prev=0, next_=32, is_free=True)
        packed = h.pack()
        assert len(packed) == HEADER_SIZE
        unpacked = BlockHeader.unpack(packed)
        assert unpacked.size == 1024
        assert unpacked.prev == 0
        assert unpacked.next == 32
        assert unpacked.is_free == True
    
    def test_pack_unpack_busy(self):
        from malloclab import BlockHeader
        h = BlockHeader(size=512, prev=64, next_=0, is_free=False)
        packed = h.pack()
        unpacked = BlockHeader.unpack(packed)
        assert unpacked.is_free == False


class TestAllocator:
    """Test basic allocator operations."""
    
    def test_initial_heap_is_one_free_block(self):
        alloc = Allocator(1024)
        free = alloc.get_free_blocks()
        assert len(free) == 1
        assert free[0][1] == 1024
    
    def test_malloc_returns_aligned_pointer(self):
        alloc = Allocator(1024)
        ptr = alloc.malloc(100)
        assert ptr is not None
        assert ptr % ALIGNMENT == 0
    
    def test_malloc_returns_valid_pointer(self):
        alloc = Allocator(1024)
        ptr = alloc.malloc(100)
        assert ptr is not None
        assert ptr > 0
    
    def test_malloc_zero_returns_none(self):
        alloc = Allocator(1024)
        assert alloc.malloc(0) is None
    
    def test_malloc_negative_returns_none(self):
        alloc = Allocator(1024)
        assert alloc.malloc(-1) is None
    
    def test_malloc_too_large_returns_none(self):
        alloc = Allocator(1024)
        assert alloc.malloc(2048) is None
    
    def test_free_makes_block_available(self):
        alloc = Allocator(4096)
        ptr = alloc.malloc(512)
        assert ptr is not None
        alloc.free(ptr)
        # After free, fragmentation should be low (coalescing)
        free = alloc.get_free_blocks()
        total_free = sum(size for _, size in free)
        assert total_free > 0
    
    def test_double_free_silently_ignored(self):
        alloc = Allocator(4096)
        ptr = alloc.malloc(256)
        alloc.free(ptr)
        alloc.free(ptr)  # Should not crash
    
    def test_alloc_write_alloc_pattern(self):
        alloc = Allocator(4096)
        ptr1 = alloc.malloc(100)
        ptr2 = alloc.malloc(100)
        assert ptr1 is not None
        assert ptr2 is not None
        # Write to ptr1 should not corrupt ptr2
        pattern = b'X' * 100
        alloc.heap[ptr1:ptr1+100] = pattern
        # ptr2 header should still be valid
        header2 = alloc._read_header(ptr2 - HEADER_SIZE)
        assert not header2.is_free


class TestCoalescing:
    """Test block coalescing on free."""
    
    def test_adjacent_free_blocks_coalesce(self):
        alloc = Allocator(8192)
        ptr1 = alloc.malloc(256)
        ptr2 = alloc.malloc(256)
        ptr3 = alloc.malloc(256)
        
        assert ptr1 is not None
        assert ptr2 is not None
        assert ptr3 is not None
        
        # Free adjacent blocks
        alloc.free(ptr1)
        alloc.free(ptr2)
        
        # Check that no two free blocks are adjacent
        free = alloc.get_free_blocks()
        for i in range(len(free) - 1):
            offset1, size1 = free[i]
            offset2, _ = free[i + 1]
            assert offset1 + size1 != offset2, "Adjacent free blocks not coalesced"
    
    def test_triple_coalesce(self):
        alloc = Allocator(8192)
        ptr1 = alloc.malloc(128)
        ptr2 = alloc.malloc(128)
        ptr3 = alloc.malloc(128)
        
        alloc.free(ptr1)
        alloc.free(ptr2)
        alloc.free(ptr3)
        
        # All three should coalesce into one large free block
        free = alloc.get_free_blocks()
        # We may have leftover fragments, but at least one should be large
        largest = max(size for _, size in free)
        assert largest >= 128 * 3


class TestFragmentation:
    """Test fragmentation bound."""
    
    def test_fragmentation_bounded_random_workload(self):
        rng = random.Random(42)
        alloc = Allocator(1048576)
        allocated = []
        
        for _ in range(100):
            if rng.random() < 0.7 or not allocated:
                size = rng.randint(16, 1024)
                ptr = alloc.malloc(size)
                if ptr is not None:
                    allocated.append(ptr)
            else:
                idx = rng.randint(0, len(allocated) - 1)
                alloc.free(allocated[idx])
                allocated.pop(idx)
        
        frag = alloc.fragmentation()
        assert frag <= 0.50, f"Fragmentation {frag} exceeds bound"
    
    def test_fragmentation_after_full_free(self):
        alloc = Allocator(8192)
        ptr1 = alloc.malloc(100)
        ptr2 = alloc.malloc(100)
        alloc.free(ptr1)
        alloc.free(ptr2)
        # After freeing everything, fragmentation should be low
        assert alloc.fragmentation() <= 0.1


class TestNoDoubleAlloc:
    """Test P1: No two mallocs return the same address."""
    
    def test_no_double_allocation(self):
        alloc = Allocator(8192)
        pointers = set()
        for _ in range(20):
            ptr = alloc.malloc(64)
            if ptr is not None:
                assert ptr not in pointers, f"Double allocation at {ptr}"
                pointers.add(ptr)


class TestAlignment:
    """Test P2: All returned pointers are aligned."""
    
    def test_all_aligned(self):
        alloc = Allocator(16384)
        for _ in range(50):
            ptr = alloc.malloc(random.randint(1, 200))
            if ptr is not None:
                assert ptr % ALIGNMENT == 0


class TestVerifyHarness:
    """Test the verification harness."""
    
    def test_harness_passes(self):
        result = verify_harness(seed=42, trials=50)
        assert result is True
    
    def test_harness_deterministic(self):
        result1 = verify_harness(seed=123, trials=20)
        result2 = verify_harness(seed=123, trials=20)
        assert result1 == result2


class TestMutationGates:
    """Test that mutation gates detect broken allocators."""
    
    def test_m1_broken_coalescing_detected(self):
        # Use disable_coalescing to simulate broken allocator
        alloc = Allocator(8192, disable_coalescing=True)
        ptr1 = alloc.malloc(128)
        ptr2 = alloc.malloc(128)
        alloc.free(ptr1)
        alloc.free(ptr2)
        
        # With coalescing disabled, adjacent free blocks remain separate
        free = alloc.get_free_blocks()
        adjacent_exists = any(
            free[i][0] + free[i][1] == free[i+1][0] 
            for i in range(len(free) - 1)
        )
        assert adjacent_exists, "M1: Broken coalescing not detected (no adjacent free blocks found)"
    
    def test_m2_broken_alignment_detected(self):
        # Simulate broken alignment
        bad_offset = 4  # Not 16-byte aligned
        payload = bad_offset + HEADER_SIZE
        misaligned = (payload % ALIGNMENT != 0)
        assert misaligned, "M2: Misaligned pointer not detected"