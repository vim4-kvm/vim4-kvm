/* SPDX-License-Identifier: MIT
 * Exclusive RX stability probe, without pixel reads, encoding or display.
 * cc -std=c11 -O2 -Wall -Wextra -Werror hdmirx-soak.c -o hdmirx-soak
 * hdmirx-soak /dev/video0 FRAMES > NEW.jsonl
 * Caller holds board/heavy locks and stops the capture owner. Does not change
 * EDID/HPD, switch source modes, load modules, or start/stop services.
 * Each dequeued buffer is logged before validation, including ERROR buffers.
 * timestamp_ns is VDIN frame completion; dq_ns is CLOCK_MONOTONIC after DQBUF.
 * This checks queue/clock progress, not pixel integrity or optical latency.
 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/videodev2.h>
#include <poll.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

static int call(int fd, unsigned long request, void *argument)
{
    int ret;
    do {
        ret = ioctl(fd, request, argument);
    } while (ret < 0 && errno == EINTR);
    if (ret < 0)
        fprintf(stderr, "ioctl %#lx: errno=%d\n", request, errno);
    return ret;
}

static uint64_t now_ns(void)
{
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now)) {
        perror("CLOCK_MONOTONIC");
        exit(1);
    }
    return (uint64_t)now.tv_sec * 1000000000 + now.tv_nsec;
}

static int enqueue(int fd, unsigned int index)
{
    struct v4l2_buffer buffer = {
        .type = V4L2_BUF_TYPE_VIDEO_CAPTURE, .memory = V4L2_MEMORY_MMAP,
        .index = index,
    };
    return call(fd, VIDIOC_QBUF, &buffer);
}

static int capture(int fd, unsigned long frames)
{
    struct v4l2_format format = {.type = V4L2_BUF_TYPE_VIDEO_CAPTURE};
    struct v4l2_dv_timings timings = {0};
    struct v4l2_requestbuffers request = {
        .type = V4L2_BUF_TYPE_VIDEO_CAPTURE, .memory = V4L2_MEMORY_MMAP,
        .count = 8,
    };
    enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    uint64_t previous_ts = 0, first_ts = 0, last_ts = 0;
    uint32_t previous_sequence = 0;
    unsigned long completed = 0, errors = 0;
    bool success = false;

    if (call(fd, VIDIOC_QUERY_DV_TIMINGS, &timings) ||
        timings.type != V4L2_DV_BT_656_1120 || timings.bt.interlaced)
        return 1;
    format.fmt.pix.width = timings.bt.width;
    format.fmt.pix.height = timings.bt.height;
    format.fmt.pix.pixelformat = V4L2_PIX_FMT_NV12;
    format.fmt.pix.field = V4L2_FIELD_NONE;
    if (call(fd, VIDIOC_S_FMT, &format))
        return 1;
    const struct v4l2_pix_format *pix = &format.fmt.pix;
    if (pix->pixelformat != V4L2_PIX_FMT_NV12 || pix->field != V4L2_FIELD_NONE ||
        pix->width != timings.bt.width || pix->height != timings.bt.height ||
        pix->bytesperline < pix->width || (pix->height & 1) ||
        (uint64_t)pix->bytesperline * pix->height * 3 / 2 > pix->sizeimage) {
        fprintf(stderr, "unexpected NV12 layout\n");
        return 1;
    }
    printf("{\"event\":\"format\",\"width\":%u,\"height\":%u,\"stride\":%u,"
           "\"uv_offset\":%" PRIu64 ",\"sizeimage\":%u,\"pixelclock\":%" PRIu64 "}\n",
           pix->width, pix->height, pix->bytesperline,
           (uint64_t)pix->bytesperline * pix->height, pix->sizeimage,
           (uint64_t)timings.bt.pixelclock);
    if (call(fd, VIDIOC_REQBUFS, &request))
        return 1;
    if (request.count < 4 || request.count > 32)
        goto release;
    for (unsigned int i = 0; i < request.count; i++)
        if (enqueue(fd, i))
            goto release;
    if (call(fd, VIDIOC_STREAMON, &type))
        goto release;
    while (completed < frames) {
        struct pollfd ready = {.fd = fd, .events = POLLIN};
        struct v4l2_buffer buffer = {.type = type, .memory = V4L2_MEMORY_MMAP};
        int ret;
        do {
            ret = poll(&ready, 1, 2500);
        } while (ret < 0 && errno == EINTR);
        if (ret != 1 || !(ready.revents & POLLIN)) {
            fprintf(stderr, "capture poll: result=%d revents=%#x errno=%d\n",
                    ret, ready.revents, errno);
            break;
        }
        if (call(fd, VIDIOC_DQBUF, &buffer))
            break;
        uint64_t dq = now_ns();
        uint64_t ts = (uint64_t)buffer.timestamp.tv_sec * 1000000000 +
                      (uint64_t)buffer.timestamp.tv_usec * 1000;
        printf("{\"event\":\"buffer\",\"index\":%u,\"sequence\":%u,\"flags\":%u,"
               "\"bytesused\":%u,\"timestamp_ns\":%" PRIu64 ",\"dq_ns\":%" PRIu64 "}\n",
               buffer.index, buffer.sequence, buffer.flags, buffer.bytesused, ts, dq);
        errors += !!(buffer.flags & V4L2_BUF_FLAG_ERROR);
        if (buffer.index >= request.count || (buffer.flags & V4L2_BUF_FLAG_ERROR) ||
            (buffer.flags & V4L2_BUF_FLAG_TIMESTAMP_MASK) != V4L2_BUF_FLAG_TIMESTAMP_MONOTONIC ||
            buffer.bytesused != (uint64_t)pix->bytesperline * pix->height * 3 / 2 ||
            buffer.bytesused > pix->sizeimage || !ts || ts > dq ||
            (completed && (ts <= previous_ts ||
                           (uint32_t)(buffer.sequence - previous_sequence) != 1))) {
            fprintf(stderr, "invalid capture completion at frame %lu\n", completed);
            break;
        }
        if (!completed)
            first_ts = ts;
        last_ts = previous_ts = ts;
        previous_sequence = buffer.sequence;
        completed++;
        if (completed < frames && enqueue(fd, buffer.index))
            break;
    }
    success = completed == frames;
    if (call(fd, VIDIOC_STREAMOFF, &type))
        success = false;
release:
    request.count = 0;
    if (call(fd, VIDIOC_REQBUFS, &request))
        success = false;
    printf("{\"event\":\"summary\",\"success\":%s,\"completed\":%lu,\"errors\":%lu,"
           "\"capture_fps\":%.6f}\n", success ? "true" : "false", completed, errors,
           last_ts > first_ts ? (completed - 1) * 1e9 / (last_ts - first_ts) : 0);
    return success ? 0 : 1;
}

int main(int argc, char **argv)
{
    char *end;
    if (argc != 3) {
        fprintf(stderr, "usage: hdmirx-soak DEVICE FRAMES\n");
        return 1;
    }
    errno = 0;
    unsigned long frames = strtoul(argv[2], &end, 10);
    if (errno || *end || argv[2][0] < '0' || argv[2][0] > '9' ||
        frames < 2 || frames > 10000000)
        return 1;
    int fd = open(argv[1], O_RDWR | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) {
        perror("open capture");
        return 1;
    }
    int result = capture(fd, frames);
    if (close(fd))
        result = 1;
    return result;
}
