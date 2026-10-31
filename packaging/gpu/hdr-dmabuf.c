/* SPDX-License-Identifier: MIT */
#define _POSIX_C_SOURCE 200809L
#include "hdr-dmabuf.h"
#include <fcntl.h>
#include <unistd.h>

VkResult hdr_dma_import(VkPhysicalDevice physical, VkDevice device, int fd,
                       VkDeviceSize bytes, VkDeviceSize capacity,
                       struct hdr_dma_buffer *output)
{
    if (!output)
        return VK_ERROR_INITIALIZATION_FAILED;
    *output = (struct hdr_dma_buffer){0};
    if (!bytes || capacity < bytes)
        return VK_ERROR_INITIALIZATION_FAILED;
    off_t actual = lseek(fd, 0, SEEK_END);
    if (actual < 0 || (VkDeviceSize)actual != capacity)
        return VK_ERROR_INVALID_EXTERNAL_HANDLE;
    VkPhysicalDeviceExternalBufferInfo query = {
        .sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTERNAL_BUFFER_INFO,
        .usage=VK_BUFFER_USAGE_STORAGE_BUFFER_BIT,
        .handleType=VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT };
    VkExternalBufferProperties props = {.sType=VK_STRUCTURE_TYPE_EXTERNAL_BUFFER_PROPERTIES};
    vkGetPhysicalDeviceExternalBufferProperties(physical,&query,&props);
    if (!(props.externalMemoryProperties.externalMemoryFeatures & VK_EXTERNAL_MEMORY_FEATURE_IMPORTABLE_BIT))
        return VK_ERROR_INVALID_EXTERNAL_HANDLE;
    VkExternalMemoryBufferCreateInfo external = {
        .sType=VK_STRUCTURE_TYPE_EXTERNAL_MEMORY_BUFFER_CREATE_INFO,
        .handleTypes=VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT };
    VkBufferCreateInfo create = {.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
        .pNext=&external, .size=bytes, .usage=VK_BUFFER_USAGE_STORAGE_BUFFER_BIT,
        .sharingMode=VK_SHARING_MODE_EXCLUSIVE};
    VkResult result=vkCreateBuffer(device,&create,NULL,&output->buffer);
    if (result != VK_SUCCESS) return result;
    VkMemoryRequirements requirements;
    vkGetBufferMemoryRequirements(device,output->buffer,&requirements);
    PFN_vkGetMemoryFdPropertiesKHR get_fd = (PFN_vkGetMemoryFdPropertiesKHR)
        vkGetDeviceProcAddr(device,"vkGetMemoryFdPropertiesKHR");
    VkMemoryFdPropertiesKHR fd_props = {.sType=VK_STRUCTURE_TYPE_MEMORY_FD_PROPERTIES_KHR};
    result=VK_ERROR_INVALID_EXTERNAL_HANDLE;
    if (!get_fd || capacity < requirements.size) goto fail;
    result=get_fd(device,VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT,fd,&fd_props);
    if (result != VK_SUCCESS) goto fail;
    uint32_t bits=requirements.memoryTypeBits & fd_props.memoryTypeBits;
    result=VK_ERROR_INVALID_EXTERNAL_HANDLE;
    if (!bits) goto fail;
    uint32_t type=0;
    while (!(bits & (1u<<type))) type++;
    int owned_fd=fcntl(fd,F_DUPFD_CLOEXEC,0);
    if (owned_fd<0) goto fail;
    VkMemoryDedicatedAllocateInfo dedicated = {
        .sType=VK_STRUCTURE_TYPE_MEMORY_DEDICATED_ALLOCATE_INFO,.buffer=output->buffer};
    VkImportMemoryFdInfoKHR import = {.sType=VK_STRUCTURE_TYPE_IMPORT_MEMORY_FD_INFO_KHR,
        .pNext=&dedicated,.handleType=VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT,.fd=owned_fd};
    VkMemoryAllocateInfo allocation = {.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
        .pNext=&import,.allocationSize=capacity,.memoryTypeIndex=type};
    result=vkAllocateMemory(device,&allocation,NULL,&output->memory);
    if (result!=VK_SUCCESS) { close(owned_fd); goto fail; }
    result=vkBindBufferMemory(device,output->buffer,output->memory,0);
    if (result!=VK_SUCCESS) goto fail;
    output->capacity=capacity;
    return VK_SUCCESS;
fail:
    vkDestroyBuffer(device,output->buffer,NULL);
    if (output->memory) vkFreeMemory(device,output->memory,NULL);
    *output=(struct hdr_dma_buffer){0};
    return result;
}

void hdr_dma_transition(VkCommandBuffer command, const struct hdr_dma_buffer *buffer,
                        uint32_t queue, bool acquire, bool writable)
{
    VkAccessFlags access=writable?VK_ACCESS_SHADER_WRITE_BIT:VK_ACCESS_SHADER_READ_BIT;
    VkBufferMemoryBarrier barrier = {.sType=VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER,
        .srcAccessMask=acquire?0:access,.dstAccessMask=acquire?access:0,
        .srcQueueFamilyIndex=acquire?VK_QUEUE_FAMILY_EXTERNAL:queue,
        .dstQueueFamilyIndex=acquire?queue:VK_QUEUE_FAMILY_EXTERNAL,
        .buffer=buffer->buffer,.size=VK_WHOLE_SIZE};
    vkCmdPipelineBarrier(command,acquire?VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT:VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
        acquire?VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT:VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,
        0,0,NULL,1,&barrier,0,NULL);
}

VkResult hdr_dma_retire(VkDevice device, struct hdr_dma_buffer *buffer, VkFence fence)
{
    VkResult result=vkGetFenceStatus(device,fence);
    if (result!=VK_SUCCESS) return result;
    vkDestroyBuffer(device,buffer->buffer,NULL);
    vkFreeMemory(device,buffer->memory,NULL);
    *buffer=(struct hdr_dma_buffer){0};
    return VK_SUCCESS;
}
