/* SPDX-License-Identifier: MIT
 * One 16 KiB kernel and checked readback. Always run with an external timeout.
 * cc -std=c11 -Wall -Wextra -Werror mali-cl-probe.c -lOpenCL -o mali-cl-probe
 */
#define _POSIX_C_SOURCE 200809L
#define CL_TARGET_OPENCL_VERSION 120
#include <CL/cl.h>
#include <CL/cl_ext.h>
#include <linux/dma-heap.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#define CHECK(call) do { cl_int e = (call); if (e) { fprintf(stderr, "%s: %d\n", #call, e); return 1; } } while (0)

int main(int argc, char **argv)
{
    setvbuf(stdout, NULL, _IOLBF, 0);
    if (argc != 2) {
        fprintf(stderr, "Usage: mali-cl-probe device-local|host-visible|/dev/dma_heap/NAME\n");
        return 2;
    }
    cl_platform_id platform;
    cl_device_id device;
    cl_int error;
    CHECK(clGetPlatformIDs(1, &platform, NULL));
    CHECK(clGetDeviceIDs(platform, CL_DEVICE_TYPE_GPU, 1, &device, NULL));
    char name[256];
    CHECK(clGetDeviceInfo(device, CL_DEVICE_NAME, sizeof(name), name, NULL));
    if (!strstr(name, "Mali-G52")) { fprintf(stderr, "Expected Mali-G52, got %s\n", name); return 1; }
    printf("device=%s mode=%s\n", name, argv[1]);
    cl_context context = clCreateContext(NULL, 1, &device, NULL, NULL, &error);
    CHECK(error);
    cl_command_queue queue = clCreateCommandQueue(context, device, 0, &error);
    CHECK(error);
    const size_t count = 4096, bytes = count * sizeof(cl_uint);
    cl_mem buffer;
    int dma_fd = -1;
    if (!strcmp(argv[1], "device-local") || !strcmp(argv[1], "host-visible")) {
        /* CL does not promise physical device-local residency on a UMA GPU. */
        buffer = clCreateBuffer(context, CL_MEM_READ_WRITE |
            (!strcmp(argv[1], "host-visible") ? CL_MEM_ALLOC_HOST_PTR : 0), bytes, NULL, &error);
    } else {
        int heap = open(argv[1], O_RDONLY | O_CLOEXEC);
        if (heap < 0) { perror(argv[1]); return 1; }
        struct dma_heap_allocation_data allocation = { .len = bytes, .fd_flags = O_RDWR | O_CLOEXEC };
        if (ioctl(heap, DMA_HEAP_IOCTL_ALLOC, &allocation)) { perror("DMA_HEAP_IOCTL_ALLOC"); return 1; }
        close(heap);
        dma_fd = (int)allocation.fd;
        clImportMemoryARM_fn import = (clImportMemoryARM_fn)
            clGetExtensionFunctionAddressForPlatform(platform, "clImportMemoryARM");
        if (!import) { fprintf(stderr, "clImportMemoryARM unavailable\n"); return 1; }
        const cl_import_properties_arm properties[] = { CL_IMPORT_TYPE_ARM, CL_IMPORT_TYPE_DMA_BUF_ARM, 0 };
        buffer = import(context, CL_MEM_READ_WRITE, properties, &dma_fd, bytes, &error);
    }
    CHECK(error);
    const char *source = "__kernel void write_words(__global uint *out) { uint i=get_global_id(0); out[i]=i^0x5a39c6e1u; }";
    cl_program program = clCreateProgramWithSource(context, 1, &source, NULL, &error);
    CHECK(error);
    error = clBuildProgram(program, 1, &device, "", NULL, NULL);
    if (error) {
        char log[8192] = {0};
        clGetProgramBuildInfo(program, device, CL_PROGRAM_BUILD_LOG, sizeof(log)-1, log, NULL);
        fprintf(stderr, "Build: %s\n", log);
        CHECK(error);
    }
    cl_kernel kernel = clCreateKernel(program, "write_words", &error);
    CHECK(error);
    CHECK(clSetKernelArg(kernel, 0, sizeof(buffer), &buffer));
    printf("stage=dispatch words=%zu\n", count);
    CHECK(clEnqueueNDRangeKernel(queue, kernel, 1, NULL, &count, NULL, 0, NULL, NULL));
    cl_uint output[4096];
    CHECK(clEnqueueReadBuffer(queue, buffer, CL_TRUE, 0, bytes, output, 0, NULL, NULL));
    for (cl_uint i = 0; i < count; i++) {
        if (output[i] != (i ^ 0x5a39c6e1u)) { fprintf(stderr, "Mismatch word=%u value=%#x\n", i, output[i]); return 1; }
    }
    CHECK(clReleaseKernel(kernel));
    CHECK(clReleaseProgram(program));
    CHECK(clReleaseMemObject(buffer));
    CHECK(clReleaseCommandQueue(queue));
    CHECK(clReleaseContext(context));
    if (dma_fd >= 0) close(dma_fd);
    puts("PASS 4096 words");
    return 0;
}
