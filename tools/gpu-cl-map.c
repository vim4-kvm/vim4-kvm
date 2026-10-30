/* SPDX-License-Identifier: MIT
 * Isolated CL map reproducer; run with an external 60s timeout and private ICD.
 * cc -O2 -Wall -Wextra -Werror gpu-cl-map.c -lOpenCL -o gpu-cl-map
 */
#define CL_TARGET_OPENCL_VERSION 120
#include <CL/cl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(call) do { cl_int e = (call); if (e) { fprintf(stderr, "%s: %d\n", #call, e); return 1; } } while (0)
#define STAGE(name) do { printf("bytes=%zu host_alloc=%d iteration=%d stage=%s\n", size, host, i, name); fflush(stdout); } while (0)

int main(void)
{
    cl_platform_id platform;
    cl_device_id device;
    cl_int error;
    CHECK(clGetPlatformIDs(1, &platform, NULL));
    CHECK(clGetDeviceIDs(platform, CL_DEVICE_TYPE_GPU, 1, &device, NULL));
    char name[256];
    CHECK(clGetDeviceInfo(device, CL_DEVICE_NAME, sizeof(name), name, NULL));
    if (!strstr(name, "Mali")) { fprintf(stderr, "Expected Mali, got %s\n", name); return 1; }
    printf("device=%s\n", name);
    cl_context context = clCreateContext(NULL, 1, &device, NULL, NULL, &error);
    CHECK(error);
    cl_command_queue queue = clCreateCommandQueue(context, device, CL_QUEUE_PROFILING_ENABLE, &error);
    CHECK(error);
    const size_t sizes[] = {4096, 1 << 20, 64 << 20};
    for (unsigned s = 0; s < sizeof(sizes) / sizeof(sizes[0]); s++) {
        size_t size = sizes[s];
        for (int host = 0; host < 2; host++) {
            int i = -1;
            STAGE("allocate");
            cl_mem buffer = clCreateBuffer(context, CL_MEM_READ_WRITE | (host ? CL_MEM_ALLOC_HOST_PTR : 0), size, NULL, &error);
            CHECK(error);
            unsigned char pattern = 0x5a;
            STAGE("fill");
            CHECK(clEnqueueFillBuffer(queue, buffer, &pattern, sizeof(pattern), 0, size, 0, NULL, NULL));
            CHECK(clFinish(queue));
            for (i = 0; i < 3; i++) {
                cl_event event;
                STAGE("map-begin");
                unsigned char *ptr = clEnqueueMapBuffer(queue, buffer, CL_TRUE, CL_MAP_READ, 0, size, 0, NULL, &event, &error);
                CHECK(error);
                STAGE("map-returned");
                CHECK(clFinish(queue));
                cl_ulong start, end;
                CHECK(clGetEventProfilingInfo(event, CL_PROFILING_COMMAND_START, sizeof(start), &start, NULL));
                CHECK(clGetEventProfilingInfo(event, CL_PROFILING_COMMAND_END, sizeof(end), &end, NULL));
                if (ptr[0] != pattern || ptr[size-1] != pattern) return 1;
                printf("map_event_ns=%llu\n", (unsigned long long)(end-start));
                CHECK(clReleaseEvent(event));
                STAGE("unmap-begin");
                CHECK(clEnqueueUnmapMemObject(queue, buffer, ptr, 0, NULL, NULL));
                STAGE("unmap-enqueued");
                CHECK(clFinish(queue));
                STAGE("unmap-complete");
            }
            CHECK(clReleaseMemObject(buffer));
        }
    }
    CHECK(clReleaseCommandQueue(queue));
    CHECK(clReleaseContext(context));
    return 0;
}
