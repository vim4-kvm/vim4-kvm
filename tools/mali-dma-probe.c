/* Headless compute + physically contiguous DMA-buf import/readback probe.
 * Build on ARM64 Linux: cc -std=c11 -Wall -Wextra -Werror tools/mali-dma-probe.c -lvulkan -o mali-dma-probe
 * glslangValidator -V tools/mali-dma-probe.comp -o mali-dma-probe.spv
 * VK_ICD_FILENAMES=/usr/lib/vim4-kvm/gpu/mali.json ./mali-dma-probe mali-dma-probe.spv
 * Does not capture HDMI or use the encoder. This is not a video benchmark.
 */
#define _POSIX_C_SOURCE 200809L
#include <vulkan/vulkan.h>
#include <linux/dma-buf.h>
#include <linux/dma-heap.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#define VK_CHECK(call) do { VkResult result_ = (call); if (result_ != VK_SUCCESS) { \
    fprintf(stderr, "%s failed: %d\n", #call, result_); exit(1); } } while (0)
#define REQUIRE(condition, message) do { if (!(condition)) { \
    fprintf(stderr, "%s\n", message); exit(1); } } while (0)

static double milliseconds(void)
{
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return now.tv_sec * 1000.0 + now.tv_nsec / 1000000.0;
}

static void cpu_sync(int fd, uint64_t flags)
{
    struct dma_buf_sync sync = { .flags = flags };
    REQUIRE(ioctl(fd, DMA_BUF_IOCTL_SYNC, &sync) == 0, "DMA_BUF_IOCTL_SYNC failed");
}

int main(int argc, char **argv)
{
    REQUIRE(argc == 2, "Usage: mali-dma-probe shader.spv");
    FILE *shader_file = fopen(argv[1], "rb");
    REQUIRE(shader_file != NULL, "Cannot open shader");
    REQUIRE(fseek(shader_file, 0, SEEK_END) == 0, "Cannot seek shader");
    long shader_size = ftell(shader_file);
    REQUIRE(shader_size > 0 && shader_size % 4 == 0, "Invalid SPIR-V size");
    rewind(shader_file);
    uint32_t *shader_code = malloc((size_t)shader_size);
    REQUIRE(shader_code != NULL, "Cannot allocate shader");
    REQUIRE(fread(shader_code, 1, (size_t)shader_size, shader_file) == (size_t)shader_size, "Cannot read shader");
    fclose(shader_file);

    VkApplicationInfo app = { .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
        .pApplicationName = "VIM4 DMA compute probe", .apiVersion = VK_API_VERSION_1_1 };
    VkInstanceCreateInfo instance_info = { .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
        .pApplicationInfo = &app };
    VkInstance instance;
    VK_CHECK(vkCreateInstance(&instance_info, NULL, &instance));
    uint32_t device_count = 0;
    VK_CHECK(vkEnumeratePhysicalDevices(instance, &device_count, NULL));
    REQUIRE(device_count == 1, "Select the private Mali ICD; expected exactly one device");
    VkPhysicalDevice physical;
    VK_CHECK(vkEnumeratePhysicalDevices(instance, &device_count, &physical));
    VkPhysicalDeviceProperties properties;
    vkGetPhysicalDeviceProperties(physical, &properties);
    REQUIRE(properties.vendorID == 0x13b5 && strstr(properties.deviceName, "Mali-G52"), "Expected real Mali-G52");
    printf("device=%s api=%u.%u.%u\n", properties.deviceName,
        VK_VERSION_MAJOR(properties.apiVersion), VK_VERSION_MINOR(properties.apiVersion), VK_VERSION_PATCH(properties.apiVersion));

    VkPhysicalDeviceExternalBufferInfo external_query = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTERNAL_BUFFER_INFO,
        .usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT,
        .handleType = VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT };
    VkExternalBufferProperties external = { .sType = VK_STRUCTURE_TYPE_EXTERNAL_BUFFER_PROPERTIES };
    vkGetPhysicalDeviceExternalBufferProperties(physical, &external_query, &external);
    REQUIRE(external.externalMemoryProperties.externalMemoryFeatures & VK_EXTERNAL_MEMORY_FEATURE_IMPORTABLE_BIT,
            "Storage buffers cannot import DMA-buf");
    uint32_t family_count = 0;
    vkGetPhysicalDeviceQueueFamilyProperties(physical, &family_count, NULL);
    VkQueueFamilyProperties *families = calloc(family_count, sizeof(*families));
    REQUIRE(families != NULL, "Cannot allocate queue properties");
    vkGetPhysicalDeviceQueueFamilyProperties(physical, &family_count, families);
    uint32_t family = 0;
    while (family < family_count && !(families[family].queueFlags & VK_QUEUE_COMPUTE_BIT)) family++;
    free(families);
    REQUIRE(family < family_count, "No compute queue");
    float priority = 1;
    VkDeviceQueueCreateInfo queue_info = { .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
        .queueFamilyIndex = family, .queueCount = 1, .pQueuePriorities = &priority };
    const char *extensions[] = { VK_KHR_EXTERNAL_MEMORY_FD_EXTENSION_NAME, VK_EXT_EXTERNAL_MEMORY_DMA_BUF_EXTENSION_NAME };
    VkDeviceCreateInfo device_info = { .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
        .queueCreateInfoCount = 1, .pQueueCreateInfos = &queue_info,
        .enabledExtensionCount = 2, .ppEnabledExtensionNames = extensions };
    VkDevice device;
    VK_CHECK(vkCreateDevice(physical, &device_info, NULL, &device));
    VkQueue queue;
    vkGetDeviceQueue(device, family, 0, &queue);

    /* One packed 4K P010 frame (Y + UV). Encoder import needs contiguous codecmm. */
    const VkDeviceSize bytes = 3840 * 2160 * 3;
    VkExternalMemoryBufferCreateInfo external_buffer = {
        .sType = VK_STRUCTURE_TYPE_EXTERNAL_MEMORY_BUFFER_CREATE_INFO,
        .handleTypes = VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT };
    VkBufferCreateInfo buffer_info = { .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
        .pNext = &external_buffer, .size = bytes, .usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT,
        .sharingMode = VK_SHARING_MODE_EXCLUSIVE };
    VkBuffer buffer;
    VK_CHECK(vkCreateBuffer(device, &buffer_info, NULL, &buffer));
    VkMemoryRequirements requirements;
    vkGetBufferMemoryRequirements(device, buffer, &requirements);
    int heap_fd = open("/dev/dma_heap/heap-codecmm", O_RDONLY | O_CLOEXEC);
    REQUIRE(heap_fd >= 0, "Cannot open contiguous codecmm heap");
    struct dma_heap_allocation_data allocation = { .len = requirements.size, .fd_flags = O_RDWR | O_CLOEXEC };
    REQUIRE(ioctl(heap_fd, DMA_HEAP_IOCTL_ALLOC, &allocation) == 0, "Contiguous DMA heap allocation failed");
    close(heap_fd);
    int dma_fd = (int)allocation.fd;
    uint32_t *mapped = mmap(NULL, requirements.size, PROT_READ | PROT_WRITE, MAP_SHARED, dma_fd, 0);
    REQUIRE(mapped != MAP_FAILED, "Cannot map DMA buffer");
    cpu_sync(dma_fd, DMA_BUF_SYNC_START | DMA_BUF_SYNC_WRITE);
    memset(mapped, 0, bytes);
    cpu_sync(dma_fd, DMA_BUF_SYNC_END | DMA_BUF_SYNC_WRITE);
    PFN_vkGetMemoryFdPropertiesKHR get_fd_properties = (PFN_vkGetMemoryFdPropertiesKHR)
        vkGetDeviceProcAddr(device, "vkGetMemoryFdPropertiesKHR");
    REQUIRE(get_fd_properties != NULL, "No external memory fd API");
    VkMemoryFdPropertiesKHR fd_properties = { .sType = VK_STRUCTURE_TYPE_MEMORY_FD_PROPERTIES_KHR };
    VK_CHECK(get_fd_properties(device, VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT, dma_fd, &fd_properties));
    uint32_t memory_bits = requirements.memoryTypeBits & fd_properties.memoryTypeBits;
    REQUIRE(memory_bits != 0, "No compatible DMA-buf memory type");
    uint32_t memory_type = 0;
    while (!(memory_bits & (1u << memory_type))) memory_type++;
    int import_fd = dup(dma_fd);
    REQUIRE(import_fd >= 0, "Cannot duplicate DMA fd");
    VkMemoryDedicatedAllocateInfo dedicated = { .sType = VK_STRUCTURE_TYPE_MEMORY_DEDICATED_ALLOCATE_INFO, .buffer = buffer };
    VkImportMemoryFdInfoKHR import = { .sType = VK_STRUCTURE_TYPE_IMPORT_MEMORY_FD_INFO_KHR,
        .pNext = &dedicated, .handleType = VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT, .fd = import_fd };
    VkMemoryAllocateInfo memory_info = { .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
        .pNext = &import, .allocationSize = requirements.size, .memoryTypeIndex = memory_type };
    VkDeviceMemory memory;
    VK_CHECK(vkAllocateMemory(device, &memory_info, NULL, &memory)); /* Vulkan owns import_fd on success. */
    VK_CHECK(vkBindBufferMemory(device, buffer, memory, 0));

    VkDescriptorSetLayoutBinding binding = { .binding = 0, .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
        .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT };
    VkDescriptorSetLayoutCreateInfo set_info = { .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,
        .bindingCount = 1, .pBindings = &binding };
    VkDescriptorSetLayout set_layout;
    VK_CHECK(vkCreateDescriptorSetLayout(device, &set_info, NULL, &set_layout));
    VkPipelineLayoutCreateInfo layout_info = { .sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
        .setLayoutCount = 1, .pSetLayouts = &set_layout };
    VkPipelineLayout layout;
    VK_CHECK(vkCreatePipelineLayout(device, &layout_info, NULL, &layout));
    VkShaderModuleCreateInfo shader_info = { .sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,
        .codeSize = (size_t)shader_size, .pCode = shader_code };
    VkShaderModule shader;
    VK_CHECK(vkCreateShaderModule(device, &shader_info, NULL, &shader));
    free(shader_code);
    VkComputePipelineCreateInfo pipeline_info = { .sType = VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO,
        .stage = { .sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
            .stage = VK_SHADER_STAGE_COMPUTE_BIT, .module = shader, .pName = "main" }, .layout = layout };
    VkPipeline pipeline;
    VK_CHECK(vkCreateComputePipelines(device, VK_NULL_HANDLE, 1, &pipeline_info, NULL, &pipeline));
    VkDescriptorPoolSize pool_size = { .type = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, .descriptorCount = 1 };
    VkDescriptorPoolCreateInfo pool_info = { .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO,
        .maxSets = 1, .poolSizeCount = 1, .pPoolSizes = &pool_size };
    VkDescriptorPool descriptor_pool;
    VK_CHECK(vkCreateDescriptorPool(device, &pool_info, NULL, &descriptor_pool));
    VkDescriptorSetAllocateInfo set_allocate = { .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,
        .descriptorPool = descriptor_pool, .descriptorSetCount = 1, .pSetLayouts = &set_layout };
    VkDescriptorSet set;
    VK_CHECK(vkAllocateDescriptorSets(device, &set_allocate, &set));
    VkDescriptorBufferInfo descriptor_buffer = { .buffer = buffer, .range = bytes };
    VkWriteDescriptorSet write = { .sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,
        .dstSet = set, .dstBinding = 0, .descriptorCount = 1,
        .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, .pBufferInfo = &descriptor_buffer };
    vkUpdateDescriptorSets(device, 1, &write, 0, NULL);
    VkCommandPoolCreateInfo command_pool_info = { .sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,
        .queueFamilyIndex = family };
    VkCommandPool command_pool;
    VK_CHECK(vkCreateCommandPool(device, &command_pool_info, NULL, &command_pool));
    VkCommandBufferAllocateInfo command_info = { .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
        .commandPool = command_pool, .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY, .commandBufferCount = 1 };
    VkCommandBuffer command;
    VK_CHECK(vkAllocateCommandBuffers(device, &command_info, &command));
    VkCommandBufferBeginInfo begin = { .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO };
    VK_CHECK(vkBeginCommandBuffer(command, &begin));
    VkBufferMemoryBarrier barrier = { .sType = VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER,
        .srcAccessMask = 0, .dstAccessMask = VK_ACCESS_SHADER_WRITE_BIT,
        .srcQueueFamilyIndex = VK_QUEUE_FAMILY_EXTERNAL, .dstQueueFamilyIndex = family,
        .buffer = buffer, .size = VK_WHOLE_SIZE };
    vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
        0, 0, NULL, 1, &barrier, 0, NULL);
    vkCmdBindPipeline(command, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline);
    vkCmdBindDescriptorSets(command, VK_PIPELINE_BIND_POINT_COMPUTE, layout, 0, 1, &set, 0, NULL);
    vkCmdDispatch(command, (uint32_t)((bytes / 4 + 255) / 256), 1, 1);
    barrier.srcAccessMask = VK_ACCESS_SHADER_WRITE_BIT;
    barrier.dstAccessMask = 0;
    barrier.srcQueueFamilyIndex = family;
    barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_EXTERNAL;
    vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,
        0, 0, NULL, 1, &barrier, 0, NULL);
    VK_CHECK(vkEndCommandBuffer(command));
    VkFenceCreateInfo fence_info = { .sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO };
    VkFence fence;
    VK_CHECK(vkCreateFence(device, &fence_info, NULL, &fence));
    VkSubmitInfo submit = { .sType = VK_STRUCTURE_TYPE_SUBMIT_INFO,
        .commandBufferCount = 1, .pCommandBuffers = &command };
    double start = milliseconds();
    VK_CHECK(vkQueueSubmit(queue, 1, &submit, fence));
    VK_CHECK(vkWaitForFences(device, 1, &fence, VK_TRUE, UINT64_C(10000000000)));
    double elapsed = milliseconds() - start;
    cpu_sync(dma_fd, DMA_BUF_SYNC_START | DMA_BUF_SYNC_READ);
    for (uint32_t i = 0; i < bytes / 4; i++) {
        if (mapped[i] != (i ^ 0x5a39c6e1u)) {
            fprintf(stderr, "Readback mismatch at %u: %08x\n", i, mapped[i]);
            return 1;
        }
    }
    cpu_sync(dma_fd, DMA_BUF_SYNC_END | DMA_BUF_SYNC_READ);
    printf("PASS heap=heap-codecmm bytes=%" PRIu64 " words=%" PRIu64 " submit_wait_ms=%.3f\n",
        (uint64_t)bytes, (uint64_t)(bytes / 4), elapsed);
    vkDestroyFence(device, fence, NULL);
    vkDestroyCommandPool(device, command_pool, NULL);
    vkDestroyDescriptorPool(device, descriptor_pool, NULL);
    vkDestroyPipeline(device, pipeline, NULL);
    vkDestroyShaderModule(device, shader, NULL);
    vkDestroyPipelineLayout(device, layout, NULL);
    vkDestroyDescriptorSetLayout(device, set_layout, NULL);
    vkDestroyBuffer(device, buffer, NULL);
    vkFreeMemory(device, memory, NULL);
    munmap(mapped, requirements.size);
    close(dma_fd);
    vkDestroyDevice(device, NULL);
    vkDestroyInstance(instance, NULL);
    return 0;
}
