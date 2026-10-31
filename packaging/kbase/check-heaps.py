#!/usr/bin/env python3
"""Run the actual heap mmap boundary code against a host VMA/DMA model."""
from pathlib import Path
import subprocess
import tempfile


def check():
    text = (Path(__file__).parent / 'heaps/vim4_kbase_heaps.c').read_text()
    function = 'static int wc_mmap' + text.split('static int wc_mmap', 1)[1].split(
        '\nstatic int wc_vmap', 1)[0]
    pool_check = 'static bool wc_pool_contains' + text.split(
        'static bool wc_pool_contains', 1)[1].split('\nstatic struct sg_table', 1)[0]
    model = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <limits.h>
#include <stdint.h>
typedef uint64_t phys_addr_t;
struct reserved_mem { phys_addr_t base, size; };
#define PAGE_SHIFT 12
#define PAGE_SIZE 4096
#define EINVAL 22
#define VM_DONTEXPAND 1
#define VM_DONTDUMP 2
#define VM_PFNMAP 4
#define GFX_ATTRS 3
struct wc_heap { void *dev; bool contiguous; };
struct wc_buffer { struct wc_heap *heap; size_t len; unsigned long *pages; void *cpu; unsigned long dma; };
struct dma_buf { void *priv; };
struct vm_area_struct { unsigned long vm_start, vm_end, vm_pgoff, vm_page_prot, flags; };
#define vma_pages(v) (((v)->vm_end-(v)->vm_start)>>PAGE_SHIFT)
#define vm_flags_set(v,f) ((v)->flags |= (f))
#define pgprot_writecombine(p) ((p)|8)
#define page_to_pfn(p) (p)
static unsigned long mappings, dma_mappings;
static int remap_pfn_range(struct vm_area_struct *v, unsigned long va, unsigned long pfn,
                          unsigned long bytes, unsigned long prot) {
    assert(prot & 8); assert(bytes == PAGE_SIZE); assert(va >= v->vm_start && va < v->vm_end);
    assert(pfn == 100 + v->vm_pgoff + mappings); mappings++; return 0;
}
static int dma_mmap_attrs(void *d, struct vm_area_struct *v, void *cpu,
                          unsigned long dma, size_t len, unsigned long attrs) {
    (void)d; (void)v; (void)cpu; (void)dma; assert(len == 4*PAGE_SIZE); assert(attrs == GFX_ATTRS);
    dma_mappings++; return 0;
}
'''
    exercise = r'''
int main(void) {
    struct reserved_mem pool = {.base=0x10000000, .size=0x8000000};
    assert(wc_pool_contains(&pool, pool.base, pool.size));
    assert(wc_pool_contains(&pool, pool.base+pool.size-PAGE_SIZE, PAGE_SIZE));
    assert(!wc_pool_contains(&pool, pool.base-1, PAGE_SIZE));
    assert(!wc_pool_contains(&pool, pool.base+pool.size-PAGE_SIZE, 2*PAGE_SIZE));
    assert(!wc_pool_contains(&pool, pool.base, SIZE_MAX));
    assert(!wc_pool_contains(&pool, UINT64_MAX-PAGE_SIZE, 2*PAGE_SIZE));
    unsigned long pages[] = {100,101,102,103};
    struct wc_heap heap = {0};
    struct wc_buffer buffer = {.heap=&heap, .pages=pages, .len=4*PAGE_SIZE};
    struct dma_buf buf = {.priv=&buffer};
    struct vm_area_struct v = {.vm_end=2*PAGE_SIZE, .vm_pgoff=2};
    assert(wc_mmap(&buf,&v)==0 && mappings==2 && !dma_mappings);
    mappings=0; v.vm_pgoff=3;
    assert(wc_mmap(&buf,&v)==-EINVAL && !mappings);
    v.vm_pgoff=ULONG_MAX;
    assert(wc_mmap(&buf,&v)==-EINVAL && !mappings);
    v.vm_pgoff=0; v.vm_end=4*PAGE_SIZE; heap.contiguous=true;
    assert(wc_mmap(&buf,&v)==0 && dma_mappings==1 && !mappings);
    v.vm_end=5*PAGE_SIZE;
    assert(wc_mmap(&buf,&v)==-EINVAL && dma_mappings==1);
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix='kbase-heaps-') as directory:
        program = Path(directory) / 'mmap.c'
        executable = Path(directory) / 'mmap'
        program.write_text(model + pool_check + function + exercise)
        subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', str(program),
                        '-o', str(executable)], check=True)
        subprocess.run([str(executable)], check=True)
    print('Heap mmap/pool: bounds/overflow rejection and WC/DMA routes passed')


if __name__ == '__main__':
    check()
