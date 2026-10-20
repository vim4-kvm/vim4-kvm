/* SPDX-License-Identifier: MIT
 * Board-only, exclusive 7.3 HDMI capture check. Requires the moving HDMI source:
 * latency-source.swift --motion --verify-coherence
 * gcc -O2 -Wall -Wextra -Werror tools/hdmirx-stream-check.c -o /tmp/hdmirx-stream-check
 * /tmp/hdmirx-stream-check /dev/video0 FRAMES CYCLES OUTPUT_DIRECTORY [--dmabuf [--hold-exports]] [--check-colors]
 * OUTPUT_DIRECTORY must already exist. Each cycle holds all four buffers,
 * verifies their immutability and empty-queue poll, then resumes streaming.
 * Saves the first/last frame of each cycle and prints per-frame JSON evidence.
 * --dmabuf reads exported DMA-buf mappings and tests queue orphaning/reallocation.
 * --hold-exports waits for one newline after closing capture, allowing a separate
 * controller to unload the capture module before the exports are remapped/read.
 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <linux/dma-buf.h>
#include <linux/videodev2.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

static unsigned int width, height, frame_bytes;
static int nv12;
#define BUFFERS 4

struct mapping {
    unsigned char *data;
    size_t length;
    int dma_fd;
};

static void require(int condition, const char *message)
{
    if (!condition) {
        fprintf(stderr, "%s (errno=%d: %s)\n", message, errno, strerror(errno));
        exit(EXIT_FAILURE);
    }
}

static int call(int fd, unsigned long request, void *argument)
{
    int result;
    do {
        result = ioctl(fd, request, argument);
    } while (result < 0 && errno == EINTR);
    return result;
}

static uint64_t now_ns(void)
{
    struct timespec now;
    require(clock_gettime(CLOCK_MONOTONIC, &now) == 0, "monotonic clock");
    return (uint64_t)now.tv_sec * 1000000000 + now.tv_nsec;
}

static unsigned int marker_id(const unsigned char *data)
{
    const unsigned int rows[] = {85, 540, 995};
    unsigned int id = 0;
    for (unsigned int row = 0; row < 3; row++) {
        uint32_t word = 0;
        for (unsigned int bit = 0; bit < 32; bit++) {
            unsigned int x = 20 + (2 * bit + 1) * 1880 / 64;
            unsigned int y = rows[row] * height / 1080;
            x = x * width / 1920;
            unsigned char neutral[3];
            const unsigned char *pixel;
            if (nv12) {
                unsigned int uv = width * height + y / 2 * width + x / 2 * 2;
                int luma = data[y * width + x];
                require(data[uv] >= 122 && data[uv] <= 134 &&
                        data[uv + 1] >= 122 && data[uv + 1] <= 134 &&
                        ((luma >= 8 && luma <= 24) || (luma >= 227 && luma <= 243)),
                        "damaged monochrome NV12 marker");
                memset(neutral, luma >= 227 ? 255 : 0, sizeof(neutral));
                pixel = neutral;
            } else {
                pixel = data + (y * width + x) * 3;
            }
            unsigned int minimum = pixel[0], maximum = pixel[0];
            unsigned int sum = pixel[0] + pixel[1] + pixel[2];
            for (unsigned int c = 1; c < 3; c++) {
                if (pixel[c] < minimum) minimum = pixel[c];
                if (pixel[c] > maximum) maximum = pixel[c];
            }
            require(maximum - minimum <= 12 && (sum <= 48 || sum >= 717),
                    "damaged monochrome marker");
            word = (word << 1) | (sum >= 717);
        }
        unsigned int current = (word >> 8) & 0xffff;
        require(word >> 24 == 0xa5 &&
                (word & 255) == ((current >> 8) ^ (current & 255) ^ 0xa5),
                "invalid marker magic/checksum");
        require(row == 0 || id == current, "torn frame: marker rows disagree");
        id = current;
    }
    return id;
}

static void check_colors(const unsigned char *data)
{
    for (unsigned int c = 0; c < 3; c++) {
        unsigned int x = (240 + c * 480) * width / 1920, y = 800 * height / 1080;
        double rgb[3];
        if (nv12) {
            unsigned int uv = width * height + y / 2 * width + x / 2 * 2;
            double luma = (data[y * width + x] - 16) * 1.164384;
            double u = data[uv] - 128, v = data[uv + 1] - 128;
            rgb[0] = luma + 1.792741 * v;
            rgb[1] = luma - .213249 * u - .532909 * v;
            rgb[2] = luma + 2.112402 * u;
        } else {
            for (unsigned int i = 0; i < 3; i++) rgb[i] = data[(y * width + x) * 3 + i];
        }
        for (unsigned int i = 0; i < 3; i++)
            require(i == c ? rgb[i] >= 180 : rgb[i] <= 60, "incorrect primary-colour mapping");
    }
}

static uint64_t fingerprint(const unsigned char *data)
{
    uint64_t value = UINT64_C(14695981039346656037);
    for (unsigned int i = 0; i < frame_bytes; i++)
        value = (value ^ data[i]) * UINT64_C(1099511628211);
    return value;
}

static void cpu_access(const struct mapping *mapping, uint64_t phase)
{
    if (mapping->dma_fd >= 0) {
        struct dma_buf_sync sync = {.flags = phase | DMA_BUF_SYNC_READ};
        require(call(mapping->dma_fd, DMA_BUF_IOCTL_SYNC, &sync) == 0, "DMA-buf CPU sync");
    }
}

static uint64_t mapping_fingerprint(const struct mapping *mapping)
{
    cpu_access(mapping, DMA_BUF_SYNC_START);
    uint64_t value = fingerprint(mapping->data);
    cpu_access(mapping, DMA_BUF_SYNC_END);
    return value;
}

static void enqueue(int fd, unsigned int index)
{
    struct v4l2_buffer buffer = {
        .type = V4L2_BUF_TYPE_VIDEO_CAPTURE, .memory = V4L2_MEMORY_MMAP, .index = index
    };
    require(call(fd, VIDIOC_QBUF, &buffer) == 0, "QBUF");
}

static struct v4l2_buffer dequeue(int fd)
{
    struct pollfd pollfd = {.fd = fd, .events = POLLIN};
    struct v4l2_buffer buffer = {
        .type = V4L2_BUF_TYPE_VIDEO_CAPTURE, .memory = V4L2_MEMORY_MMAP
    };
    require(poll(&pollfd, 1, 2500) == 1 && (pollfd.revents & POLLIN), "frame poll");
    require(call(fd, VIDIOC_DQBUF, &buffer) == 0, "DQBUF");
    require(buffer.index < BUFFERS && buffer.bytesused == frame_bytes &&
            !(buffer.flags & V4L2_BUF_FLAG_ERROR), "buffer geometry/error");
    require((buffer.flags & V4L2_BUF_FLAG_TIMESTAMP_MASK) ==
            V4L2_BUF_FLAG_TIMESTAMP_MONOTONIC, "timestamp clock");
    return buffer;
}

static void save_frame(const char *directory, unsigned int cycle,
                       const char *label, const void *data)
{
    char path[4096];
    int length = snprintf(path, sizeof(path), "%s/cycle-%u-%s.raw", directory, cycle, label);
    require(length > 0 && (size_t)length < sizeof(path), "output path length");
    FILE *output = fopen(path, "wbx");
    require(output != NULL, "create new output frame");
    require(fwrite(data, 1, frame_bytes, output) == frame_bytes, "save frame");
    require(fclose(output) == 0, "close frame");
}

int main(int argc, char **argv)
{
    require(argc >= 5 && argc <= 8,
            "usage: hdmirx-stream-check DEVICE FRAMES CYCLES OUTPUT_DIRECTORY [--dmabuf [--hold-exports]] [--check-colors]");
    int export_mode = 0, hold_exports = 0, colors = 0;
    for (int i = 5; i < argc; i++) {
        if (!export_mode && strcmp(argv[i], "--dmabuf") == 0) export_mode = 1;
        else if (!hold_exports && strcmp(argv[i], "--hold-exports") == 0) hold_exports = 1;
        else if (!colors && strcmp(argv[i], "--check-colors") == 0) colors = 1;
        else require(0, "unknown or repeated option");
    }
    require(!hold_exports || export_mode, "--hold-exports requires --dmabuf");
    unsigned int frames = (unsigned int)strtoul(argv[2], NULL, 10);
    unsigned int cycles = (unsigned int)strtoul(argv[3], NULL, 10);
    require(frames >= 8 && frames <= 10000 && cycles >= 1 && cycles <= 100,
            "frames must be 8..10000; cycles 1..100");
    int fd = open(argv[1], O_RDWR | O_NONBLOCK | O_CLOEXEC);
    require(fd >= 0, "open V4L2 device");
    struct v4l2_capability cap = {0};
    require(call(fd, VIDIOC_QUERYCAP, &cap) == 0, "QUERYCAP");
    require(strcmp((const char *)cap.driver, "t7-vdin-test") == 0 &&
            (cap.device_caps & (V4L2_CAP_VIDEO_CAPTURE | V4L2_CAP_STREAMING)) ==
            (V4L2_CAP_VIDEO_CAPTURE | V4L2_CAP_STREAMING), "experimental capture device");
    struct v4l2_format format = {.type = V4L2_BUF_TYPE_VIDEO_CAPTURE};
    require(call(fd, VIDIOC_G_FMT, &format) == 0, "G_FMT");
    width = format.fmt.pix.width;
    height = format.fmt.pix.height;
    nv12 = format.fmt.pix.pixelformat == V4L2_PIX_FMT_NV12;
    require((width == 1920 && height == 1080) || (width == 3840 && height == 2160),
            "supported capture dimensions");
    require(nv12 || format.fmt.pix.pixelformat == V4L2_PIX_FMT_RGB24, "NV12 or RGB24 format");
    frame_bytes = nv12 ? width * height * 3 / 2 : width * height * 3;
    unsigned int allocation_bytes = nv12 ? width * ((height + 15U) & ~15U) * 3 / 2 : frame_bytes;
    require(format.fmt.pix.sizeimage == allocation_bytes &&
            format.fmt.pix.bytesperline == width * (nv12 ? 1U : 3U), "packed capture geometry");
    printf("{\"width\":%u,\"height\":%u,\"format\":\"%s\"}\n", width, height, nv12 ? "NV12" : "RGB24");
    struct v4l2_requestbuffers request = {
        .count = BUFFERS, .type = V4L2_BUF_TYPE_VIDEO_CAPTURE, .memory = V4L2_MEMORY_MMAP
    };
    require(call(fd, VIDIOC_REQBUFS, &request) == 0 && request.count == BUFFERS, "REQBUFS");
    int other = open(argv[1], O_RDWR | O_NONBLOCK | O_CLOEXEC);
    require(other >= 0, "second open");
    struct v4l2_requestbuffers competing = request;
    require(call(other, VIDIOC_REQBUFS, &competing) < 0 && errno == EBUSY,
            "queue ownership must exclude a second file");
    require(close(other) == 0, "close second file");
    struct mapping mappings[BUFFERS];
    for (unsigned int i = 0; i < BUFFERS; i++) {
        struct v4l2_buffer buffer = {
            .type = request.type, .memory = request.memory, .index = i
        };
        require(call(fd, VIDIOC_QUERYBUF, &buffer) == 0, "QUERYBUF");
        mappings[i].length = buffer.length;
        mappings[i].dma_fd = -1;
        int map_fd = fd;
        off_t offset = buffer.m.offset;
        if (export_mode) {
            struct v4l2_exportbuffer exported = {
                .type = request.type, .index = i, .flags = O_CLOEXEC | O_RDONLY
            };
            require(call(fd, VIDIOC_EXPBUF, &exported) == 0, "EXPBUF");
            mappings[i].dma_fd = exported.fd;
            map_fd = exported.fd;
            offset = 0;
            int flags = fcntl(map_fd, F_GETFD);
            require(flags >= 0 && (flags & FD_CLOEXEC), "export must be close-on-exec");
        }
        mappings[i].data = mmap(NULL, buffer.length, export_mode ? PROT_READ : PROT_READ | PROT_WRITE,
                                MAP_SHARED, map_fd, offset);
        require(mappings[i].data != MAP_FAILED, "MMAP");
    }
    require(call(fd, VIDIOC_S_FMT, &format) < 0 && errno == EBUSY,
            "format change with allocated buffers must fail");
    unsigned int previous_id = 0;
    int have_id = 0;
    for (unsigned int cycle = 0; cycle < cycles; cycle++) {
        enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        for (unsigned int i = 0; i < BUFFERS; i++) enqueue(fd, i);
        require(call(fd, VIDIOC_STREAMON, &type) == 0, "STREAMON");
        int snapshot = open("/sys/kernel/debug/ff000000.video-capture/frame", O_RDONLY);
        require(snapshot < 0 && errno == EBUSY, "snapshot must exclude a V4L2 stream");
        printf("{\"cycle\":%u,\"streaming\":true}\n", cycle);
        fflush(stdout);
        uint64_t previous_timestamp = 0, first_timestamp = 0;
        unsigned int held[BUFFERS];
        uint64_t hashes[BUFFERS];
        for (unsigned int i = 0; i < frames; i++) {
            struct v4l2_buffer buffer = dequeue(fd);
            uint64_t timestamp = (uint64_t)buffer.timestamp.tv_sec * 1000000000 +
                                 (uint64_t)buffer.timestamp.tv_usec * 1000;
            cpu_access(&mappings[buffer.index], DMA_BUF_SYNC_START);
            unsigned int id = marker_id(mappings[buffer.index].data);
            if (colors) check_colors(mappings[buffer.index].data);
            unsigned int delta = (id - previous_id) & 0xffff;
            require(!have_id || (delta > 0 && delta < 0x8000), "stale/backward source frame");
            require(buffer.sequence == i && timestamp > previous_timestamp &&
                    timestamp <= now_ns(), "sequence/timestamp progression");
            previous_id = id;
            have_id = 1;
            previous_timestamp = timestamp;
            if (i == 0) first_timestamp = timestamp;
            printf("{\"cycle\":%u,\"sequence\":%u,\"id\":%u,\"timestamp_ns\":%llu}\n",
                   cycle, i, id, (unsigned long long)timestamp);
            if (i == 0 || i == frames - 1)
                save_frame(argv[4], cycle, i == 0 ? "first" : "last", mappings[buffer.index].data);
            if (i < BUFFERS) {
                held[i] = buffer.index;
                hashes[i] = fingerprint(mappings[buffer.index].data);
            }
            cpu_access(&mappings[buffer.index], DMA_BUF_SYNC_END);
            if (i < BUFFERS) {
                if (i == BUFFERS - 1) {
                    struct pollfd empty = {.fd = fd, .events = POLLIN};
                    require(poll(&empty, 1, 200) == 0, "exhausted queue must wait");
                    for (unsigned int j = 0; j < BUFFERS; j++) {
                        require(mapping_fingerprint(&mappings[held[j]]) == hashes[j],
                                "dequeued buffer changed while held");
                        enqueue(fd, held[j]);
                    }
                }
            } else {
                enqueue(fd, buffer.index);
            }
        }
        uint64_t stop_start = now_ns();
        require(call(fd, VIDIOC_STREAMOFF, &type) == 0, "STREAMOFF");
        uint64_t stop_ns = now_ns() - stop_start;
        require(stop_ns < UINT64_C(2000000000), "bounded STREAMOFF");
        printf("{\"cycle\":%u,\"frames\":%u,\"span_ns\":%llu,\"stop_ns\":%llu,"
               "\"held_buffers\":4,\"starvation_resumed\":true}\n", cycle, frames,
               (unsigned long long)(previous_timestamp - first_timestamp),
               (unsigned long long)stop_ns);
        fflush(stdout);
    }
    uint64_t orphan_hashes[BUFFERS];
    if (export_mode) {
        for (unsigned int i = 0; i < BUFFERS; i++)
            orphan_hashes[i] = mapping_fingerprint(&mappings[i]);
        request.count = 0;
        require(call(fd, VIDIOC_REQBUFS, &request) == 0, "orphan exported buffers with REQBUFS(0)");
        request.count = BUFFERS;
        require(call(fd, VIDIOC_REQBUFS, &request) == 0 && request.count == BUFFERS,
                "allocate a fresh queue while old exports survive");
    }
    /* close() must also stop an active stream without an explicit STREAMOFF. */
    for (unsigned int i = 0; i < BUFFERS; i++) enqueue(fd, i);
    enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    require(call(fd, VIDIOC_STREAMON, &type) == 0, "final STREAMON");
    (void)dequeue(fd);
    uint64_t close_start = now_ns();
    require(close(fd) == 0, "close streaming file");
    if (export_mode) {
        require(now_ns() - close_start < UINT64_C(2000000000), "bounded streaming close");
        for (unsigned int i = 0; i < BUFFERS; i++)
            require(mapping_fingerprint(&mappings[i]) == orphan_hashes[i],
                    "orphaned export changed after fresh queue capture/close");
        if (hold_exports) {
            puts("{\"exports_orphaned\":true,\"waiting_for_controller\":true}");
            fflush(stdout);
            require(getchar() == '\n', "controller must release held exports with a newline");
        }
        for (unsigned int i = 0; i < BUFFERS; i++) {
            require(munmap(mappings[i].data, mappings[i].length) == 0, "unmap orphaned export");
            mappings[i].data = mmap(NULL, mappings[i].length, PROT_READ, MAP_SHARED,
                                    mappings[i].dma_fd, 0);
            require(mappings[i].data != MAP_FAILED, "remap export after capture file closes");
            require(mapping_fingerprint(&mappings[i]) == orphan_hashes[i],
                    "orphaned export changed after remapping");
        }
    }
    for (unsigned int i = 0; i < BUFFERS; i++)
        require(munmap(mappings[i].data, mappings[i].length) == 0, "MUNMAP after close");
    /* MMAP retains file references; the final unmap triggers the actual release. */
    if (!export_mode)
        require(now_ns() - close_start < UINT64_C(2000000000), "bounded streaming release");
    if (export_mode) {
        for (unsigned int i = 0; i < BUFFERS; i++)
            require(close(mappings[i].dma_fd) == 0, "close orphaned export");
        puts("{\"dmabuf_export\":true,\"orphan_remap\":true}");
    }
    puts("{\"closed_while_streaming\":true,\"result\":\"pass\"}");
    return EXIT_SUCCESS;
}
