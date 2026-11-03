// SPDX-License-Identifier: GPL-2.0-only
/* Candidate-only WC heaps. The DT supplies a dedicated reusable CMA pool. */
#include <linux/dma-buf.h>
#include <linux/dma-heap.h>
#include <linux/dma-mapping.h>
#include <linux/dma-map-ops.h>
#include <linux/iosys-map.h>
#include <linux/mm.h>
#include <linux/module.h>
#include <linux/of_reserved_mem.h>
#include <linux/platform_device.h>
#include <linux/scatterlist.h>
#include <linux/slab.h>
#include <linux/vmalloc.h>

#define GFX_ATTRS (DMA_ATTR_WRITE_COMBINE | DMA_ATTR_FORCE_CONTIGUOUS)

struct wc_heap {
	struct device *dev;
	struct reserved_mem *pool;
	bool contiguous;
};

struct wc_buffer {
	struct wc_heap *heap;
	size_t len;
	struct page **pages;
	struct sg_table table;
	void *cpu;
	dma_addr_t dma;
};

static bool wc_pool_contains(struct reserved_mem *pool, phys_addr_t start, size_t len)
{
	return start >= pool->base && len <= pool->size &&
	       start - pool->base <= pool->size - len;
}

static struct sg_table *wc_map(struct dma_buf_attachment *attachment,
			       enum dma_data_direction direction)
{
	struct wc_buffer *buffer = attachment->dmabuf->priv;
	struct sg_table *table;
	struct scatterlist *src, *dst;
	unsigned int i;
	int ret;

	table = kmalloc_obj(*table);
	if (!table)
		return ERR_PTR(-ENOMEM);
	ret = sg_alloc_table(table, buffer->table.orig_nents, GFP_KERNEL);
	if (ret)
		goto free_table;
	dst = table->sgl;
	for_each_sgtable_sg(&buffer->table, src, i) {
		sg_set_page(dst, sg_page(src), src->length, src->offset);
		dst = sg_next(dst);
	}
	ret = dma_map_sgtable(attachment->dev, table, direction,
			      DMA_ATTR_SKIP_CPU_SYNC);
	if (ret) {
		sg_free_table(table);
		goto free_table;
	}
	return table;
free_table:
	kfree(table);
	return ERR_PTR(ret);
}

static void wc_unmap(struct dma_buf_attachment *attachment,
		     struct sg_table *table, enum dma_data_direction direction)
{
	dma_unmap_sgtable(attachment->dev, table, direction, DMA_ATTR_SKIP_CPU_SYNC);
	sg_free_table(table);
	kfree(table);
}

static int wc_begin_cpu(struct dma_buf *dmabuf, enum dma_data_direction direction)
{
	/* All CPU mappings are WC; there are no dirty cached CPU aliases. */
	dma_rmb();
	return 0;
}

static int wc_end_cpu(struct dma_buf *dmabuf, enum dma_data_direction direction)
{
	dma_wmb();
	return 0;
}

static int wc_mmap(struct dma_buf *dmabuf, struct vm_area_struct *vma)
{
	struct wc_buffer *buffer = dmabuf->priv;
	unsigned long count = vma_pages(vma), i;
	unsigned long offset = vma->vm_pgoff;
	int ret;

	if (offset > buffer->len >> PAGE_SHIFT ||
	    count > (buffer->len >> PAGE_SHIFT) - offset)
		return -EINVAL;
	if (buffer->heap->contiguous)
		return dma_mmap_attrs(buffer->heap->dev, vma, buffer->cpu,
				      buffer->dma, buffer->len, GFX_ATTRS);
	vm_flags_set(vma, VM_DONTEXPAND | VM_DONTDUMP | VM_PFNMAP);
	vma->vm_page_prot = pgprot_writecombine(vma->vm_page_prot);
	for (i = 0; i < count; i++) {
		ret = remap_pfn_range(vma, vma->vm_start + (i << PAGE_SHIFT),
				      page_to_pfn(buffer->pages[offset + i]),
				      PAGE_SIZE, vma->vm_page_prot);
		if (ret)
			return ret;
	}
	return 0;
}

static int wc_vmap(struct dma_buf *dmabuf, struct iosys_map *map)
{
	struct wc_buffer *buffer = dmabuf->priv;
	void *address = buffer->cpu;

	if (!buffer->heap->contiguous)
		address = vmap(buffer->pages, buffer->len >> PAGE_SHIFT,
			       VM_MAP, pgprot_writecombine(PAGE_KERNEL));
	if (!address)
		return -ENOMEM;
	iosys_map_set_vaddr(map, address);
	return 0;
}

static void wc_vunmap(struct dma_buf *dmabuf, struct iosys_map *map)
{
	struct wc_buffer *buffer = dmabuf->priv;

	if (!buffer->heap->contiguous)
		vunmap(map->vaddr);
}

static void wc_free_storage(struct wc_buffer *buffer)
{
	unsigned long i;

	if (buffer->heap->contiguous) {
		if (buffer->cpu)
			dma_free_attrs(buffer->heap->dev, buffer->len, buffer->cpu,
				       buffer->dma, GFX_ATTRS);
	} else if (buffer->pages) {
		for (i = 0; i < buffer->len >> PAGE_SHIFT; i++)
			if (buffer->pages[i])
				__free_page(buffer->pages[i]);
		kvfree(buffer->pages);
	}
	kfree(buffer);
}

static void wc_release(struct dma_buf *dmabuf)
{
	struct wc_buffer *buffer = dmabuf->priv;

	sg_free_table(&buffer->table);
	wc_free_storage(buffer);
}

static const struct dma_buf_ops wc_buf_ops = {
	.map_dma_buf = wc_map,
	.unmap_dma_buf = wc_unmap,
	.begin_cpu_access = wc_begin_cpu,
	.end_cpu_access = wc_end_cpu,
	.mmap = wc_mmap,
	.vmap = wc_vmap,
	.vunmap = wc_vunmap,
	.release = wc_release,
};

static struct dma_buf *wc_allocate(struct dma_heap *heap, unsigned long len,
				   u32 fd_flags, u64 heap_flags)
{
	DEFINE_DMA_BUF_EXPORT_INFO(info);
	struct wc_heap *state = dma_heap_get_drvdata(heap);
	struct wc_buffer *buffer;
	struct dma_buf *dmabuf;
	unsigned long i, count = len >> PAGE_SHIFT;
	int ret = -ENOMEM;

	buffer = kzalloc_obj(*buffer);
	if (!buffer)
		return ERR_PTR(-ENOMEM);
	buffer->heap = state;
	buffer->len = len;
	if (state->contiguous) {
		buffer->cpu = dma_alloc_attrs(state->dev, len, &buffer->dma,
					      GFP_KERNEL | __GFP_ZERO, GFX_ATTRS);
		if (!buffer->cpu)
			goto free_storage;
		ret = dma_get_sgtable_attrs(state->dev, &buffer->table,
					    buffer->cpu, buffer->dma, len, GFX_ATTRS);
		if (ret)
			goto free_storage;
		/* Reject any DMA backend that did not honor physical contiguity. */
		if (buffer->table.orig_nents != 1) {
			ret = -EINVAL;
			goto free_table;
		}
		/* DMA-direct may fall back to buddy pages if the pool is exhausted. */
		if (!wc_pool_contains(state->pool, sg_phys(buffer->table.sgl), len)) {
			ret = -ENOMEM;
			goto free_table;
		}
	} else {
		buffer->pages = kvcalloc(count, sizeof(*buffer->pages), GFP_KERNEL);
		if (!buffer->pages)
			goto free_storage;
		for (i = 0; i < count; i++) {
			buffer->pages[i] = alloc_page(GFP_KERNEL | __GFP_ZERO);
			if (!buffer->pages[i])
				goto free_storage;
		}
		ret = sg_alloc_table_from_pages(&buffer->table, buffer->pages,
						count, 0, len, GFP_KERNEL);
		if (ret)
			goto free_storage;
		/* Flush the cached zeroing alias before exposing WC mappings. */
		ret = dma_map_sgtable(state->dev, &buffer->table, DMA_BIDIRECTIONAL, 0);
		if (ret)
			goto free_table;
		dma_unmap_sgtable(state->dev, &buffer->table, DMA_BIDIRECTIONAL, 0);
	}
	info.exp_name = dma_heap_get_name(heap);
	info.ops = &wc_buf_ops;
	info.size = len;
	info.flags = fd_flags;
	info.priv = buffer;
	dmabuf = dma_buf_export(&info);
	if (!IS_ERR(dmabuf))
		return dmabuf;
	ret = PTR_ERR(dmabuf);
free_table:
	sg_free_table(&buffer->table);
free_storage:
	wc_free_storage(buffer);
	return ERR_PTR(ret);
}

static const struct dma_heap_ops wc_heap_ops = {
	.allocate = wc_allocate,
};

static int wc_probe(struct platform_device *pdev)
{
	static struct wc_heap states[2];
	const char * const names[] = { "system-uncached", "heap-gfx" };
	struct dma_heap_export_info info = { .ops = &wc_heap_ops };
	struct dma_heap *heap;
	struct device_node *node;
	struct reserved_mem *pool;
	int ret, i;

	if (dev_is_dma_coherent(&pdev->dev))
		return dev_err_probe(&pdev->dev, -EINVAL, "WC heap requires noncoherent DMA ops\n");
	/* Initial cache maintenance must map original system pages, not bounce. */
	ret = dma_set_mask_and_coherent(&pdev->dev, DMA_BIT_MASK(64));
	if (ret)
		return ret;
	ret = of_reserved_mem_device_init(&pdev->dev);
	if (ret)
		return dev_err_probe(&pdev->dev, ret, "Dedicated CMA pool required\n");
	node = of_parse_phandle(pdev->dev.of_node, "memory-region", 0);
	pool = of_reserved_mem_lookup(node);
	of_node_put(node);
	if (!pool || !pdev->dev.cma_area) {
		of_reserved_mem_device_release(&pdev->dev);
		return -EINVAL;
	}
	for (i = 0; i < ARRAY_SIZE(states); i++) {
		states[i].dev = &pdev->dev;
		states[i].pool = pool;
		states[i].contiguous = i != 0;
		info.name = names[i];
		info.priv = &states[i];
		heap = dma_heap_add(&info);
		if (IS_ERR(heap)) {
			ret = PTR_ERR(heap);
			if (!i) {
				of_reserved_mem_device_release(&pdev->dev);
				return ret;
			}
			/* The public heap API has no unregister: keep the first valid. */
			dev_err(&pdev->dev, "heap-gfx registration failed: %d\n", ret);
			break;
		}
		if (!i)
			__module_get(THIS_MODULE);
		dev_info(&pdev->dev, "%s: WC, %s backing\n", names[i],
			 i ? "dedicated contiguous CMA" : "system pages");
	}
	/* No unbind/unload until reboot: heaps retain callbacks and device state. */
	return 0;
}

static const struct of_device_id wc_match[] = {
	{ .compatible = "khadas,vim4-kbase-heaps" },
	{ }
};
MODULE_DEVICE_TABLE(of, wc_match);

static struct platform_driver wc_driver = {
	.probe = wc_probe,
	.driver = {
		.name = "vim4-kbase-heaps",
		.of_match_table = wc_match,
		.suppress_bind_attrs = true,
	},
};
module_platform_driver(wc_driver);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("VIM4 candidate WC system and dedicated CMA DMA heaps");
MODULE_IMPORT_NS("DMA_BUF");
MODULE_IMPORT_NS("DMA_BUF_HEAP");
