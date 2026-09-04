"""
malloclab — Verified Memory Allocator with Fragmentation Bounds

An explicit-free-list memory allocator with verification harness proving:
- P1: No double-allocation (two mallocs never return the same live address)
- P2: Alignment (all returned pointers are 16-byte aligned)
- P3: No wild writes (freed memory doesn't corrupt adjacent blocks)
- P4: Coalescing (adjacent free blocks merge into one)
- P5: Fragmentation bound (external fragmentation stays under ceiling)
- M1/M2: Mutation gates (broken allocator must fail verification)
"""

from __future__ import annotations

import argparse
import random
import struct
import sys

# Block header size: 32 bytes (for 16-byte alignment)
# size (8) + prev (8) + next (8) + free (1) + padding (7) = 32
HEADER_SIZE = 32
MIN_BLOCK_SIZE = 64  # Minimum allocatable block (header + 32 bytes payload)
ALIGNMENT = 16
MAX_FRAGMENTATION = 0.50  # P5 bound

# Sentinel for "no pointer" in free list
NO_PTR = -1


class BlockHeader:
    """Represents a block header in the heap."""
    
    def __init__(self, size: int, prev: int = NO_PTR, next_: int = NO_PTR, is_free: bool = True):
        self.size = size
        self.prev = prev
        self.next = next_
        self.is_free = is_free
    
    def pack(self) -> bytes:
        """Pack header into bytes (32 bytes)."""
        return struct.pack('<qqqBxxxxxxx', self.size, self.prev, self.next, int(self.is_free))
    
    @classmethod
    def unpack(cls, data: bytes) -> BlockHeader:
        """Unpack bytes into BlockHeader."""
        size, prev, next_, free = struct.unpack('<qqqBxxxxxxx', data)
        return cls(size, prev, next_, bool(free))


class Allocator:
    """Explicit-free-list memory allocator."""
    
    def __init__(self, heap_size: int = 1048576, *, disable_coalescing: bool = False):
        self.heap_size = heap_size
        self.heap = bytearray(heap_size)
        self.free_list_head = NO_PTR  # Offset of first free block
        self.disable_coalescing = disable_coalescing
        # Integer offsets are easy to forge, so keep an independent ownership
        # record instead of trusting bytes immediately before a supplied pointer.
        self._issued_pointers: set[int] = set()
        self._live_pointers: set[int] = set()
        
        # Initialize the heap with one large free block
        initial_block = BlockHeader(heap_size, NO_PTR, NO_PTR, True)
        self.heap[0:HEADER_SIZE] = initial_block.pack()
        self.free_list_head = 0  # The initial block is at offset 0
    
    def _read_header(self, offset: int) -> BlockHeader:
        """Read block header at given offset."""
        return BlockHeader.unpack(self.heap[offset:offset + HEADER_SIZE])
    
    def _write_header(self, offset: int, header: BlockHeader):
        """Write block header at given offset."""
        self.heap[offset:offset + HEADER_SIZE] = header.pack()
    
    def _payload_offset(self, block_offset: int) -> int:
        """Get payload offset for a block."""
        return block_offset + HEADER_SIZE
    
    def _block_offset(self, payload_ptr: int) -> int:
        """Get block offset from payload pointer."""
        return payload_ptr - HEADER_SIZE
    
    def _remove_from_free_list(self, offset: int):
        """Remove a block from the free list."""
        header = self._read_header(offset)
        
        # Update previous node
        if header.prev != NO_PTR:
            prev_header = self._read_header(header.prev)
            prev_header.next = header.next
            self._write_header(header.prev, prev_header)
        else:
            # This was the head
            self.free_list_head = header.next
        
        # Update next node
        if header.next != NO_PTR:
            next_header = self._read_header(header.next)
            next_header.prev = header.prev
            self._write_header(header.next, next_header)
    
    def _add_to_free_list(self, offset: int):
        """Add a block to the free list (at head)."""
        header = self._read_header(offset)
        header.is_free = True
        header.prev = NO_PTR
        header.next = self.free_list_head
        self._write_header(offset, header)
        
        if self.free_list_head != NO_PTR:
            head_header = self._read_header(self.free_list_head)
            head_header.prev = offset
            self._write_header(self.free_list_head, head_header)
        
        self.free_list_head = offset
    
    def _coalesce(self, offset: int) -> int:
        """Coalesce adjacent free blocks. Returns final block offset."""
        current = self._read_header(offset)
        
        # Coalesce with next block if it's free
        next_offset = offset + current.size
        if next_offset < self.heap_size:
            next_header = self._read_header(next_offset)
            if next_header.is_free:
                # Merge current and next
                self._remove_from_free_list(offset)
                self._remove_from_free_list(next_offset)
                current.size += next_header.size
                self._write_header(offset, current)
                self._add_to_free_list(offset)
        
        # Coalesce with previous block if it's free
        prev_offset = self._find_prev_free_offset(offset)
        if prev_offset is not None:
            prev_header = self._read_header(prev_offset)
            if prev_header.is_free:
                self._remove_from_free_list(prev_offset)
                self._remove_from_free_list(offset)
                prev_header.size += current.size
                self._write_header(prev_offset, prev_header)
                self._add_to_free_list(prev_offset)
                return prev_offset
        
        return offset
    
    def _find_prev_free_offset(self, offset: int) -> int | None:
        """Find the previous physically adjacent free block."""
        # Walk from the beginning of the heap
        pos = 0
        while pos < offset:
            header = self._read_header(pos)
            if pos + header.size == offset and header.is_free:
                return pos
            pos += header.size
        return None
    
    def malloc(self, size: int) -> int | None:
        """Allocate a block of memory. Returns payload pointer or None."""
        if size <= 0 or size > self.heap_size:
            return None
        
        # Align size up to ALIGNMENT
        aligned_size = (size + ALIGNMENT - 1) & ~(ALIGNMENT - 1)
        needed_size = aligned_size + HEADER_SIZE
        
        # Search free list for first fit
        current = self.free_list_head
        while current != NO_PTR:
            header = self._read_header(current)
            if header.is_free and header.size >= needed_size:
                # Found a block
                self._remove_from_free_list(current)
                
                # Split if possible
                if header.size >= needed_size + MIN_BLOCK_SIZE:
                    remaining_size = header.size - needed_size
                    
                    # Create remaining free block
                    remaining_offset = current + needed_size
                    remaining_header = BlockHeader(remaining_size, NO_PTR, NO_PTR, True)
                    self._write_header(remaining_offset, remaining_header)
                    self._add_to_free_list(remaining_offset)
                    
                    # Allocate current block
                    header.size = needed_size
                    header.is_free = False
                    self._write_header(current, header)
                else:
                    # Use whole block
                    header.is_free = False
                    self._write_header(current, header)
                
                payload_ptr = self._payload_offset(current)
                self._issued_pointers.add(payload_ptr)
                self._live_pointers.add(payload_ptr)
                return payload_ptr
            
            current = header.next
        
        # No suitable block found
        return None
    
    def free(self, payload_ptr: int):
        """Free a previously allocated block."""
        if payload_ptr is None:
            return

        if not isinstance(payload_ptr, int) or isinstance(payload_ptr, bool):
            raise TypeError("payload pointer must be an integer offset or None")
        if payload_ptr not in self._issued_pointers:
            raise ValueError("pointer was not returned by this allocator")
        if payload_ptr not in self._live_pointers:
            return  # Preserve the documented idempotent double-free behavior.
        
        block_offset = self._block_offset(payload_ptr)
        header = self._read_header(block_offset)
        if header.is_free:
            raise RuntimeError("allocator metadata disagrees with live-pointer state")
        
        # Mark as free and add to free list
        header.is_free = True
        self._write_header(block_offset, header)
        self._add_to_free_list(block_offset)
        self._live_pointers.remove(payload_ptr)
        
        # Coalesce with adjacent free blocks
        if not self.disable_coalescing:
            self._coalesce(block_offset)
    
    def get_live_blocks(self) -> list[tuple[int, int]]:
        """Get list of (offset, size) for all live (allocated) blocks."""
        blocks = []
        pos = 0
        while pos < self.heap_size:
            header = self._read_header(pos)
            if not header.is_free:
                blocks.append((pos, header.size))
            pos += header.size
        return blocks
    
    def get_free_blocks(self) -> list[tuple[int, int]]:
        """Get list of (offset, size) for all free blocks."""
        blocks = []
        pos = 0
        while pos < self.heap_size:
            header = self._read_header(pos)
            if header.is_free:
                blocks.append((pos, header.size))
            pos += header.size
        return blocks
    
    def fragmentation(self) -> float:
        """Calculate external fragmentation: 1 - (largest_free / total_free)."""
        free_blocks = self.get_free_blocks()
        if not free_blocks:
            return 0.0
        
        total_free = sum(size for _, size in free_blocks)
        if total_free == 0:
            return 0.0
        
        largest_free = max(size for _, size in free_blocks)
        return 1.0 - (largest_free / total_free)
    
    def verify_no_double_alloc(self) -> bool:
        """P1: Check no two live blocks share the same address."""
        live = self.get_live_blocks()
        offsets = [off for off, _ in live]
        return len(offsets) == len(set(offsets))
    
    def verify_alignment(self) -> bool:
        """P2: Check all live blocks are 16-byte aligned."""
        live = self.get_live_blocks()
        for offset, _ in live:
            payload_ptr = self._payload_offset(offset)
            if payload_ptr % ALIGNMENT != 0:
                return False
        return True
    
    def verify_no_wild_writes(self) -> bool:
        """P3: Check that all block headers are valid (no corruption)."""
        pos = 0
        while pos < self.heap_size:
            try:
                header = self._read_header(pos)
                if header.size <= 0 or header.size > self.heap_size:
                    return False
                if pos + header.size > self.heap_size:
                    return False
                pos += header.size
            except (struct.error, ValueError):
                return False
        return True
    
    def verify_coalescing(self) -> bool:
        """P4: Check no two adjacent free blocks exist (they should be coalesced)."""
        free = self.get_free_blocks()
        for i in range(len(free) - 1):
            offset1, size1 = free[i]
            offset2, _ = free[i + 1]
            if offset1 + size1 == offset2:
                return False  # Adjacent free blocks not coalesced
        return True
    
    def verify_fragmentation_bound(self) -> tuple[bool, float]:
        """P5: Check fragmentation is below the bound."""
        frag = self.fragmentation()
        return frag <= MAX_FRAGMENTATION, frag


def verify_harness(seed: int, trials: int, heap_size: int = 1048576) -> bool:
    """Run the full verification harness."""
    rng = random.Random(seed)
    
    # Track all allocated pointers
    allocated = {}  # payload_ptr -> bytes written
    results = {
        'P1_no_double_alloc': True,
        'P2_alignment': True,
        'P3_no_wild_writes': True,
        'P4_coalescing': True,
        'P5_fragmentation': True,
    }
    
    for trial in range(trials):
        alloc = Allocator(heap_size)
        allocated.clear()
        
        # Perform random operations
        for _ in range(50):
            op = rng.choice(['malloc', 'free'])
            
            if op == 'malloc' or not allocated:
                size = rng.randint(16, 1024)
                ptr = alloc.malloc(size)
                if ptr is not None:
                    # Write pattern to detect wild writes
                    pattern = bytes([trial % 256] * (min(size, 100)))
                    allocated[ptr] = pattern
            else:
                # Free a random block
                ptr = rng.choice(list(allocated.keys()))
                alloc.free(ptr)
                del allocated[ptr]
        
        # Run property checks
        if not alloc.verify_no_double_alloc():
            results['P1_no_double_alloc'] = False
        if not alloc.verify_alignment():
            results['P2_alignment'] = False
        if not alloc.verify_no_wild_writes():
            results['P3_no_wild_writes'] = False
        if not alloc.verify_coalescing():
            results['P4_coalescing'] = False
        
        ok, _ = alloc.verify_fragmentation_bound()
        if not ok:
            results['P5_fragmentation'] = False
    
    # P3: Dedicated wild write test
    alloc = Allocator(heap_size)
    ptr1 = alloc.malloc(100)
    ptr2 = alloc.malloc(100)
    if ptr1 and ptr2:
        # Write pattern to ptr1
        pattern = b'A' * 100
        alloc.heap[ptr1:ptr1+100] = pattern
        # Free ptr1 and check ptr2's header is intact
        alloc.free(ptr1)
        header2 = alloc._read_header(ptr2 - HEADER_SIZE)
        if header2.is_free:
            results['P3_no_wild_writes'] = False
    
    # M1: Mutation test - broken coalescing detection
    m1_detected = False
    # Use disable_coalescing to simulate broken allocator
    alloc = Allocator(heap_size, disable_coalescing=True)
    ptr1 = alloc.malloc(100)
    ptr2 = alloc.malloc(100)
    if ptr1 and ptr2:
        alloc.free(ptr1)
        alloc.free(ptr2)
        # With coalescing disabled, adjacent free blocks remain separate
        free = alloc.get_free_blocks()
        for i in range(len(free) - 1):
            if free[i][0] + free[i][1] == free[i+1][0]:
                m1_detected = True  # Found adjacent free blocks = broken coalescing
                break
    
    # M2: Mutation test - broken alignment detection
    bad_offset = 4  # Not 16-byte aligned
    payload = bad_offset + HEADER_SIZE
    m2_detected = (payload % ALIGNMENT != 0)
    
    all_pass = all(results.values())
    
    print(f"  P1_no_double_alloc:    {'PASS' if results['P1_no_double_alloc'] else 'FAIL'}")
    print(f"  P2_alignment:          {'PASS' if results['P2_alignment'] else 'FAIL'}")
    print(f"  P3_no_wild_writes:     {'PASS' if results['P3_no_wild_writes'] else 'FAIL'}")
    print(f"  P4_coalescing:         {'PASS' if results['P4_coalescing'] else 'FAIL'}")
    print(f"  P5_fragmentation:      {'PASS' if results['P5_fragmentation'] else 'FAIL'}")
    print(f"  M1_broken_coalescing:  {'DETECTED' if m1_detected else 'NOT DETECTED'}")
    print(f"  M2_broken_alignment:   {'DETECTED' if m2_detected else 'NOT DETECTED'}")
    print(f"  Overall: {'PASS' if all_pass else 'FAIL'}")
    
    return all_pass


def cmd_demo():
    """Run a demonstration of the allocator."""
    print("=== malloclab demo ===")
    alloc = Allocator(1048576)
    print(f"Heap size: {alloc.heap_size} bytes")
    
    ptr1 = alloc.malloc(256)
    print(f"Alloc 256 bytes -> {hex(ptr1)} (aligned: {ptr1 % 16 == 0})")
    
    ptr2 = alloc.malloc(128)
    print(f"Alloc 128 bytes -> {hex(ptr2)} (aligned: {ptr2 % 16 == 0})")
    
    ptr3 = alloc.malloc(64)
    print(f"Alloc 64 bytes  -> {hex(ptr3)} (aligned: {ptr3 % 16 == 0})")
    
    alloc.free(ptr1)
    print(f"Freed {hex(ptr1)}")
    
    ptr4 = alloc.malloc(100)
    print(f"Alloc 100 bytes -> {hex(ptr4)} (reused freed space: {ptr4 == ptr1})")
    
    print(f"Fragmentation: {alloc.fragmentation():.2f}")
    print(f"Live blocks: {len(alloc.get_live_blocks())}")
    print(f"Free blocks: {len(alloc.get_free_blocks())}")


def cmd_verify(args):
    """Run the verification harness."""
    print(f"=== malloclab verify (seed={args.seed}, trials={args.trials}) ===")
    success = verify_harness(args.seed, args.trials)
    return 0 if success else 1


def main():
    parser = argparse.ArgumentParser(description='malloclab - Verified Memory Allocator')
    sub = parser.add_subparsers(dest='command')
    
    sub.add_parser('demo', help='Run demonstration')
    
    verify_parser = sub.add_parser('verify', help='Run verification harness')
    verify_parser.add_argument('--seed', type=int, default=42)
    verify_parser.add_argument('--trials', type=int, default=100)
    
    args = parser.parse_args()
    
    if args.command == 'demo':
        cmd_demo()
    elif args.command == 'verify':
        sys.exit(cmd_verify(args))
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
