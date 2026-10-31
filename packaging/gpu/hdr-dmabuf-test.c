/* SPDX-License-Identifier: MIT */
#include "hdr-dmabuf.h"
#include <assert.h>
static VkResult status;
static unsigned destroyed, freed;
VKAPI_ATTR VkResult VKAPI_CALL vkGetFenceStatus(VkDevice device, VkFence fence)
{ (void)device; (void)fence; return status; }
VKAPI_ATTR void VKAPI_CALL vkDestroyBuffer(VkDevice device, VkBuffer buffer,
                                          const VkAllocationCallbacks *allocator)
{ (void)device; (void)buffer; (void)allocator; destroyed++; }
VKAPI_ATTR void VKAPI_CALL vkFreeMemory(VkDevice device, VkDeviceMemory memory,
                                       const VkAllocationCallbacks *allocator)
{ (void)device; (void)memory; (void)allocator; freed++; }
int main(void)
{
    struct hdr_dma_buffer buffer={.capacity=4096};
    status=VK_NOT_READY;
    assert(hdr_dma_retire(VK_NULL_HANDLE,&buffer,VK_NULL_HANDLE)==VK_NOT_READY);
    assert(!destroyed && !freed && buffer.capacity==4096);
    status=VK_ERROR_DEVICE_LOST;
    assert(hdr_dma_retire(VK_NULL_HANDLE,&buffer,VK_NULL_HANDLE)==VK_ERROR_DEVICE_LOST);
    assert(!destroyed && !freed && buffer.capacity==4096);
    status=VK_SUCCESS;
    assert(hdr_dma_retire(VK_NULL_HANDLE,&buffer,VK_NULL_HANDLE)==VK_SUCCESS);
    assert(destroyed==1 && freed==1 && !buffer.capacity);
    return 0;
}
