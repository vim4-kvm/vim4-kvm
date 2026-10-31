/* SPDX-License-Identifier: MIT */
#ifndef VIM4_HDR_DMABUF_H
#define VIM4_HDR_DMABUF_H
#include <stdbool.h>
#include <vulkan/vulkan.h>

struct hdr_dma_buffer {
    VkBuffer buffer;
    VkDeviceMemory memory;
    VkDeviceSize capacity;
};

/* Borrows fd. output must be an unused slot; retire before reusing a live slot.
 * Caller retains the capture/output lease through GPU completion.
 * bytes is the visible buffer range; capacity must match the actual allocation.
 * On failure no imported objects remain. No CPU mapping or copy is performed.
 */
VkResult hdr_dma_import(VkPhysicalDevice physical, VkDevice device, int fd,
                       VkDeviceSize bytes, VkDeviceSize capacity,
                       struct hdr_dma_buffer *output);
/* Caller must wait for the producer before acquire, and signal completion to
 * the consumer after release. Queue ownership barriers alone are not fences.
 */
void hdr_dma_transition(VkCommandBuffer command, const struct hdr_dma_buffer *buffer,
                        uint32_t queue, bool acquire, bool writable);
/* Refuses to free before the supplied submission fence has completed. Device
 * loss is not proof of DMA retirement: caller must quarantine until reset.
 */
VkResult hdr_dma_retire(VkDevice device, struct hdr_dma_buffer *buffer, VkFence fence);
#endif
