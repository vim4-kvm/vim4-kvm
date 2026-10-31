/* Headless compute + native memory or DMA-buf import/readback probe.
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
#include <errno.h>
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

static void sample_marker(long sample, const char *stage)
{
    const char *path = getenv("GPU_TRACE_MARKER");
    if (!path) return;
    FILE *stream = fopen(path, "w");
    if (!stream) { perror("GPU_TRACE_MARKER"); exit(1); }
    fprintf(stream, "mali-dma sample=%ld stage=%s\n", sample, stage);
    if (fclose(stream)) { perror("trace marker close"); exit(1); }
}

static void sample_frequency(long sample, const char *stage)
{
    const char *path = getenv("GPU_FREQ_PATH");
    if (!path) return;
    FILE *stream = fopen(path, "r");
    unsigned long long hz;
    if (!stream) { perror("GPU_FREQ_PATH"); exit(1); }
    REQUIRE(fscanf(stream, "%llu", &hz) == 1, "Cannot read GPU frequency");
    fclose(stream);
    printf("sample=%ld stage=%s frequency_readback=%llu path=%s\n", sample, stage, hz, path);
}

static void cpu_sync(int fd, uint64_t flags)
{
    struct dma_buf_sync sync = { .flags = flags };
    REQUIRE(ioctl(fd, DMA_BUF_IOCTL_SYNC, &sync) == 0, "DMA_BUF_IOCTL_SYNC failed");
}

int main(int argc, char **argv)
{
    setvbuf(stdout, NULL, _IOLBF, 0);
    REQUIRE(argc >= 2 && argc <= 5, "Usage: mali-dma-probe shader.spv [heap-path|device-local|host-visible] [iterations:1..100] [bytes:1024..24883200, multiple of 4]");
    const char *heap_path = argc >= 3 ? argv[2] : "/dev/dma_heap/heap-codecmm";
    int host_visible = !strcmp(heap_path, "host-visible");
    int native = !strcmp(heap_path, "device-local") || host_visible;
    char *end = NULL;
    long iterations = argc >= 4 ? strtol(argv[3], &end, 10) : 1;
    REQUIRE(iterations >= 1 && iterations <= 100 && (!end || (*argv[3] && !*end)), "Invalid iteration count");
    end = NULL;
    long requested = argc == 5 ? strtol(argv[4], &end, 10) : 3840 * 2160 * 3;
    REQUIRE(requested >= 1024 && requested <= 3840 * 2160 * 3 && requested % 4 == 0 &&
            (!end || (*argv[4] && !*end)), "Invalid byte count");
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
    uint32_t timestamp_bits = family < family_count ? families[family].timestampValidBits : 0;
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
    VkQueryPool timestamps = VK_NULL_HANDLE;
    if (getenv("GPU_TIMESTAMP") && timestamp_bits) {
        VkQueryPoolCreateInfo query = { .sType = VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO,
            .queryType = VK_QUERY_TYPE_TIMESTAMP, .queryCount = 2 };
        VK_CHECK(vkCreateQueryPool(device, &query, NULL, &timestamps));
        printf("timestamp_bits=%u timestamp_period_ns=%g\n", timestamp_bits, properties.limits.timestampPeriod);
    }

    /* One packed 4K P010 frame (Y + UV). Encoder import needs contiguous codecmm. */
    const VkDeviceSize bytes = (VkDeviceSize)requested;
    VkExternalMemoryBufferCreateInfo external_buffer = {
        .sType = VK_STRUCTURE_TYPE_EXTERNAL_MEMORY_BUFFER_CREATE_INFO,
        .handleTypes = VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT };
    VkBufferCreateInfo buffer_info = { .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
        .pNext = native ? NULL : &external_buffer, .size = bytes,
        .usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_SRC_BIT,
        .sharingMode = VK_SHARING_MODE_EXCLUSIVE };
    VkBuffer buffer;
    VK_CHECK(vkCreateBuffer(device, &buffer_info, NULL, &buffer));
    VkMemoryRequirements requirements;
    vkGetBufferMemoryRequirements(device, buffer, &requirements);
    int dma_fd = -1;
    uint32_t *mapped = NULL;
    uint32_t memory_type = 0;
    VkMemoryAllocateInfo memory_info = { .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
        .allocationSize = requirements.size };
    VkDeviceMemory memory, staging_memory = VK_NULL_HANDLE;
    VkBuffer staging = VK_NULL_HANDLE;
    VkPhysicalDeviceMemoryProperties memory_properties;
    vkGetPhysicalDeviceMemoryProperties(physical, &memory_properties);
    if (native) {
        VkMemoryPropertyFlags wanted = !strcmp(heap_path, "device-local") ?
            VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT : VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT;
        while (memory_type < memory_properties.memoryTypeCount &&
               (!(requirements.memoryTypeBits & (1u << memory_type)) ||
                (memory_properties.memoryTypes[memory_type].propertyFlags & wanted) != wanted)) memory_type++;
        REQUIRE(memory_type < memory_properties.memoryTypeCount, "Requested native memory type unavailable");
        memory_info.memoryTypeIndex = memory_type;
        VK_CHECK(vkAllocateMemory(device, &memory_info, NULL, &memory));
        VK_CHECK(vkBindBufferMemory(device, buffer, memory, 0));
        VkBufferCreateInfo staging_info = { .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
            .size = bytes, .usage = VK_BUFFER_USAGE_TRANSFER_DST_BIT };
        VK_CHECK(vkCreateBuffer(device, &staging_info, NULL, &staging));
        VkMemoryRequirements staging_requirements;
        vkGetBufferMemoryRequirements(device, staging, &staging_requirements);
        uint32_t staging_type = 0;
        while (staging_type < memory_properties.memoryTypeCount &&
               (!(staging_requirements.memoryTypeBits & (1u << staging_type)) ||
                !(memory_properties.memoryTypes[staging_type].propertyFlags & VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT))) staging_type++;
        REQUIRE(staging_type < memory_properties.memoryTypeCount, "No host-visible staging memory");
        VkMemoryAllocateInfo staging_allocate = { .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
            .allocationSize = staging_requirements.size, .memoryTypeIndex = staging_type };
        VK_CHECK(vkAllocateMemory(device, &staging_allocate, NULL, &staging_memory));
        VK_CHECK(vkBindBufferMemory(device, staging, staging_memory, 0));
        VK_CHECK(vkMapMemory(device, staging_memory, 0, VK_WHOLE_SIZE, 0, (void **)&mapped));
    } else {
        int heap_fd = open(heap_path, O_RDONLY | O_CLOEXEC);
        if (heap_fd < 0) fprintf(stderr, "open %s: %s\n", heap_path, strerror(errno));
        REQUIRE(heap_fd >= 0, "Cannot open requested DMA heap");
        struct dma_heap_allocation_data allocation = { .len = requirements.size, .fd_flags = O_RDWR | O_CLOEXEC };
        REQUIRE(ioctl(heap_fd, DMA_HEAP_IOCTL_ALLOC, &allocation) == 0, "DMA heap allocation failed");
        close(heap_fd);
        dma_fd = (int)allocation.fd;
        mapped = mmap(NULL, requirements.size, PROT_READ | PROT_WRITE, MAP_SHARED, dma_fd, 0);
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
        while (!(memory_bits & (1u << memory_type))) memory_type++;
        int import_fd = dup(dma_fd);
        REQUIRE(import_fd >= 0, "Cannot duplicate DMA fd");
        VkMemoryDedicatedAllocateInfo dedicated = { .sType = VK_STRUCTURE_TYPE_MEMORY_DEDICATED_ALLOCATE_INFO, .buffer = buffer };
        VkImportMemoryFdInfoKHR import = { .sType = VK_STRUCTURE_TYPE_IMPORT_MEMORY_FD_INFO_KHR,
            .pNext = &dedicated, .handleType = VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT, .fd = import_fd };
        memory_info.pNext = &import;
        memory_info.memoryTypeIndex = memory_type;
        VK_CHECK(vkAllocateMemory(device, &memory_info, NULL, &memory)); /* Vulkan owns import_fd on success. */
        VK_CHECK(vkBindBufferMemory(device, buffer, memory, 0));
    }
    printf("mode=%s bytes=%" PRIu64 " memory_type=%u flags=%#x (UMA types may overlap)\n",
           heap_path, (uint64_t)bytes, memory_type, memory_properties.memoryTypes[memory_type].propertyFlags);

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
    if (timestamps) {
        vkCmdResetQueryPool(command, timestamps, 0, 2);
        vkCmdWriteTimestamp(command, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, timestamps, 0);
    }
    VkBufferMemoryBarrier barrier = { .sType = VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER,
        .srcAccessMask = 0, .dstAccessMask = VK_ACCESS_SHADER_WRITE_BIT,
        .srcQueueFamilyIndex = native ? VK_QUEUE_FAMILY_IGNORED : VK_QUEUE_FAMILY_EXTERNAL,
        .dstQueueFamilyIndex = native ? VK_QUEUE_FAMILY_IGNORED : family,
        .buffer = buffer, .size = VK_WHOLE_SIZE };
    vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
        0, 0, NULL, 1, &barrier, 0, NULL);
    vkCmdBindPipeline(command, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline);
    vkCmdBindDescriptorSets(command, VK_PIPELINE_BIND_POINT_COMPUTE, layout, 0, 1, &set, 0, NULL);
    vkCmdDispatch(command, (uint32_t)((bytes / 4 + 255) / 256), 1, 1);
    barrier.srcAccessMask = VK_ACCESS_SHADER_WRITE_BIT;
    barrier.dstAccessMask = native ? VK_ACCESS_TRANSFER_READ_BIT : 0;
    if (host_visible) barrier.dstAccessMask |= VK_ACCESS_HOST_READ_BIT;
    barrier.srcQueueFamilyIndex = native ? VK_QUEUE_FAMILY_IGNORED : family;
    barrier.dstQueueFamilyIndex = native ? VK_QUEUE_FAMILY_IGNORED : VK_QUEUE_FAMILY_EXTERNAL;
    vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
        native ? (VK_PIPELINE_STAGE_TRANSFER_BIT | (host_visible ? VK_PIPELINE_STAGE_HOST_BIT : 0)) : VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,
        0, 0, NULL, 1, &barrier, 0, NULL);
    if (native) {
        VkBufferCopy copy = { .size = bytes };
        vkCmdCopyBuffer(command, buffer, staging, 1, &copy);
        barrier.buffer = staging;
        barrier.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
        barrier.dstAccessMask = VK_ACCESS_HOST_READ_BIT;
        vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_HOST_BIT,
            0, 0, NULL, 1, &barrier, 0, NULL);
    }
    if (timestamps) vkCmdWriteTimestamp(command, VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT, timestamps, 1);
    VK_CHECK(vkEndCommandBuffer(command));
    VkFenceCreateInfo fence_info = { .sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO };
    VkFence fence;
    VK_CHECK(vkCreateFence(device, &fence_info, NULL, &fence));
    VkSubmitInfo submit = { .sType = VK_STRUCTURE_TYPE_SUBMIT_INFO,
        .commandBufferCount = 1, .pCommandBuffers = &command };
    double elapsed = 0;
    /* Keep the original cold sample, then report warm samples separately. */
    for (long i = -3; i < iterations; i++) {
        VK_CHECK(vkResetFences(device, 1, &fence));
        sample_frequency(i, "before");
        sample_marker(i, "begin");
        double start = milliseconds();
        VK_CHECK(vkQueueSubmit(queue, 1, &submit, fence));
        double submitted = milliseconds();
        VK_CHECK(vkWaitForFences(device, 1, &fence, VK_TRUE, UINT64_C(10000000000)));
        double complete = milliseconds();
        sample_marker(i, "end");
        sample_frequency(i, "after");
        if (timestamps) {
            uint64_t values[2];
            VK_CHECK(vkGetQueryPoolResults(device, timestamps, 0, 2, sizeof(values), values,
                                          sizeof(values[0]), VK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WAIT_BIT));
            uint64_t mask = timestamp_bits >= 64 ? UINT64_MAX : (UINT64_C(1) << timestamp_bits) - 1;
            printf("sample=%ld diagnostic_gpu_ms=%.6f\n", i,
                   (double)((values[1] - values[0]) & mask) * properties.limits.timestampPeriod / 1e6);
        }
        printf("sample=%ld warmup=%d submit_ms=%.6f wait_ms=%.6f total_ms=%.6f\n",
               i, i < 0, submitted-start, complete-submitted, complete-start);
        if (i >= 0) elapsed += complete-start;
    }
    elapsed /= iterations;
    if (native) {
        if (host_visible) {
            vkUnmapMemory(device, staging_memory);
            VK_CHECK(vkMapMemory(device, memory, 0, VK_WHOLE_SIZE, 0, (void **)&mapped));
        }
        VkMappedMemoryRange range = { .sType = VK_STRUCTURE_TYPE_MAPPED_MEMORY_RANGE,
            .memory = host_visible ? memory : staging_memory, .size = VK_WHOLE_SIZE };
        VK_CHECK(vkInvalidateMappedMemoryRanges(device, 1, &range));
        printf("readback=%s\n", host_visible ? "host-visible target" : "staging after device-local copy");
    } else cpu_sync(dma_fd, DMA_BUF_SYNC_START | DMA_BUF_SYNC_READ);
    for (uint32_t i = 0; i < bytes / 4; i++) {
        if (mapped[i] != (i ^ 0x5a39c6e1u)) {
            fprintf(stderr, "Readback mismatch at %u: %08x\n", i, mapped[i]);
            return 1;
        }
    }
    if (!native) cpu_sync(dma_fd, DMA_BUF_SYNC_END | DMA_BUF_SYNC_READ);
    printf("PASS heap=%s bytes=%" PRIu64 " words=%" PRIu64 " submit_wait_ms=%.3f\n",
        heap_path, (uint64_t)bytes, (uint64_t)(bytes / 4), elapsed);
    vkDestroyFence(device, fence, NULL);
    vkDestroyCommandPool(device, command_pool, NULL);
    vkDestroyDescriptorPool(device, descriptor_pool, NULL);
    vkDestroyPipeline(device, pipeline, NULL);
    vkDestroyShaderModule(device, shader, NULL);
    vkDestroyPipelineLayout(device, layout, NULL);
    vkDestroyDescriptorSetLayout(device, set_layout, NULL);
    vkDestroyBuffer(device, buffer, NULL);
    if (native) {
        vkUnmapMemory(device, host_visible ? memory : staging_memory);
        vkDestroyBuffer(device, staging, NULL);
        vkFreeMemory(device, staging_memory, NULL);
    } else {
        munmap(mapped, requirements.size);
        close(dma_fd);
    }
    vkFreeMemory(device, memory, NULL);
    if (timestamps) vkDestroyQueryPool(device, timestamps, NULL);
    vkDestroyDevice(device, NULL);
    vkDestroyInstance(instance, NULL);
    return 0;
}
