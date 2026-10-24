/* SPDX-License-Identifier: MIT
 * Exclusive RX stability probe, without encoding or display.
 * cc -std=c11 -O2 -Wall -Wextra -Werror hdmirx-soak.c -o hdmirx-soak
 * hdmirx-soak /dev/video0 FRAMES [--count-errors] [--markers] > NEW.jsonl
 * Caller holds board/heavy locks and stops the capture owner. Does not change
 * EDID/HPD, switch source modes, load modules, or start/stop services.
 * Each dequeued buffer is logged before validation, including ERROR buffers.
 * --count-errors continues after ERROR to measure the usable frame rate; it
 * still returns failure if any ERROR occurs. A terminal queue error stops it.
 * timestamp_ns is VDIN frame completion; dq_ns is CLOCK_MONOTONIC after DQBUF.
 * --markers checks the three frame IDs from latency-source.swift --motion
 * --verify-coherence --no-labels. Without it, no pixels are read. Sparse marker
 * agreement does not prove every pixel, and is not optical latency.
 * marker_status: 0=agreement, -1=bad levels, -2=magic/checksum, -3=torn IDs,
 * -4=unchecked/unavailable. ERROR marker agreement never makes a frame usable.
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
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
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

static int markers(const unsigned char *data, unsigned int width, unsigned int height,
                   unsigned int stride, unsigned int *id)
{
    const unsigned int rows[] = {85, 540, 995};
    for (unsigned int row = 0; row < 3; row++) {
        uint32_t word = 0;
        for (unsigned int bit = 0; bit < 32; bit++) {
            unsigned int x = (20 + (2 * bit + 1) * 1880 / 64) * width / 1920;
            unsigned int y = rows[row] * height / 1080;
            size_t uv = (size_t)stride * height + y / 2 * stride + x / 2 * 2;
            unsigned int luma = data[(size_t)y * stride + x];
            if (data[uv] < 122 || data[uv] > 134 || data[uv + 1] < 122 ||
                data[uv + 1] > 134 || !((luma >= 8 && luma <= 24) ||
                                       (luma >= 227 && luma <= 243)))
                return -1;
            word = (word << 1) | (luma >= 227);
        }
        unsigned int current = (word >> 8) & 65535;
        if ((word >> 24) != 0xa5 ||
            (word & 255) != ((current >> 8) ^ (current & 255) ^ 0xa5))
            return -2;
        if (row && *id != current)
            return -3;
        *id = current;
    }
    return 0;
}

static int capture(int fd, unsigned long frames, bool count_errors, bool check_markers)
{
    struct v4l2_format format = {.type = V4L2_BUF_TYPE_VIDEO_CAPTURE};
    struct v4l2_dv_timings timings = {0};
    struct v4l2_requestbuffers request = {
        .type = V4L2_BUF_TYPE_VIDEO_CAPTURE, .memory = V4L2_MEMORY_MMAP,
        .count = 8,
    };
    enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    uint64_t previous_ts = 0, first_dq = 0, last_dq = 0;
    uint32_t previous_sequence = 0;
    unsigned long completed = 0, valid = 0, errors = 0, errors_since_valid = 0;
    bool first_valid = false;
    bool have_metadata = false, have_marker = false;
    unsigned int previous_marker = 0;
    unsigned long error_marker_ok = 0, error_marker_bad = 0, good_marker_bad = 0;
    unsigned long repeats = 0, distinct_markers = 0;
    struct { void *data; size_t length; } views[32] = {0};
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
        pix->width < 320 || pix->width > 3840 || pix->height < 180 || pix->height > 2160 ||
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
    for (unsigned int i = 0; i < request.count; i++) {
        if (check_markers) {
            struct v4l2_buffer buffer = {.type = type, .memory = V4L2_MEMORY_MMAP, .index = i};
            if (call(fd, VIDIOC_QUERYBUF, &buffer) || buffer.length < pix->sizeimage)
                goto release;
            void *data = mmap(NULL, buffer.length, PROT_READ, MAP_SHARED, fd, buffer.m.offset);
            if (data == MAP_FAILED) {
                perror("mmap capture");
                goto release;
            }
            views[i].data = data;
            views[i].length = buffer.length;
        }
        if (enqueue(fd, i))
            goto release;
    }
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
        unsigned int id = 0;
        int marker_status = -4;
        if (check_markers && buffer.index < request.count &&
            buffer.bytesused >= (uint64_t)pix->bytesperline * pix->height * 3 / 2)
            marker_status = markers(views[buffer.index].data, pix->width, pix->height,
                                    pix->bytesperline, &id);
        printf("{\"event\":\"buffer\",\"index\":%u,\"sequence\":%u,\"flags\":%u,"
               "\"bytesused\":%u,\"timestamp_ns\":%" PRIu64 ",\"dq_ns\":%" PRIu64 ","
               "\"marker_status\":%d,\"marker_id\":%u}\n",
               buffer.index, buffer.sequence, buffer.flags, buffer.bytesused, ts, dq,
               marker_status, id);
        if (!completed) {
            first_dq = dq;
            first_valid = !(buffer.flags & V4L2_BUF_FLAG_ERROR) &&
                          (!check_markers || !marker_status);
        }
        last_dq = dq;
        completed++;
        if (buffer.index >= request.count) {
            fprintf(stderr, "invalid buffer index\n");
            break;
        }
        if (check_markers && !marker_status) {
            if (have_marker && id == previous_marker)
                repeats++;
            else
                distinct_markers++;
            previous_marker = id;
            have_marker = true;
        }
        if (buffer.flags & V4L2_BUF_FLAG_ERROR) {
            errors++;
            errors_since_valid++;
            if (check_markers) {
                error_marker_ok += marker_status == 0;
                error_marker_bad += marker_status != 0;
            }
            if (!count_errors)
                break;
            /* ERROR payload/metadata are not evidence of a complete image.
             * Older kernels also leave stale timestamps and sequences here.
             */
            if (completed < frames && enqueue(fd, buffer.index))
                break;
            continue;
        }
        if ((buffer.flags & V4L2_BUF_FLAG_TIMESTAMP_MASK) != V4L2_BUF_FLAG_TIMESTAMP_MONOTONIC ||
            buffer.bytesused != (uint64_t)pix->bytesperline * pix->height * 3 / 2 ||
            buffer.bytesused > pix->sizeimage || !ts || ts > dq ||
            (have_metadata && (ts <= previous_ts ||
                       (uint32_t)(buffer.sequence - previous_sequence) != errors_since_valid + 1))) {
            fprintf(stderr, "invalid capture completion at frame %lu\n", completed - 1);
            /* Include only validated complete frames in the usable rate. */
            break;
        }
        previous_ts = ts;
        previous_sequence = buffer.sequence;
        errors_since_valid = 0;
        have_metadata = true;
        if (check_markers && marker_status) {
            good_marker_bad++;
            if (!count_errors)
                break;
            if (completed < frames && enqueue(fd, buffer.index))
                break;
            continue;
        }
        valid++;
        if (completed < frames && enqueue(fd, buffer.index))
            break;
    }
    success = completed == frames && valid == frames && !errors;
    if (call(fd, VIDIOC_STREAMOFF, &type))
        success = false;
release:
    for (unsigned int i = 0; i < 32; i++)
        if (views[i].data && munmap(views[i].data, views[i].length))
            success = false;
    request.count = 0;
    if (call(fd, VIDIOC_REQBUFS, &request))
        success = false;
    printf("{\"event\":\"summary\",\"success\":%s,\"dequeued\":%lu,\"valid\":%lu,\"errors\":%lu,"
           "\"window_ns\":%" PRIu64 ",\"dequeue_fps\":%.6f,\"usable_fps\":%.6f,"
           "\"error_fraction\":%.9f,\"markers_checked\":%s,\"error_marker_ok\":%lu,"
           "\"error_marker_bad\":%lu,\"good_marker_bad\":%lu,\"marker_repeats\":%lu,"
           "\"distinct_markers\":%lu}\n", success ? "true" : "false", completed, valid, errors,
           last_dq - first_dq,
           last_dq > first_dq ? (completed - 1) * 1e9 / (last_dq - first_dq) : 0,
           last_dq > first_dq && valid ? (valid - first_valid) * 1e9 / (last_dq - first_dq) : 0,
           completed ? (double)errors / completed : 0, check_markers ? "true" : "false",
           error_marker_ok, error_marker_bad, good_marker_bad, repeats, distinct_markers);
    return success ? 0 : 1;
}

int main(int argc, char **argv)
{
    char *end;
    setvbuf(stdout, NULL, _IOLBF, 0);
    bool count_errors = false, check_markers = false;
    if (argc < 3 || argc > 5) {
        fprintf(stderr, "usage: hdmirx-soak DEVICE FRAMES [--count-errors] [--markers]\n");
        return 1;
    }
    for (int i = 3; i < argc; i++) {
        if (!count_errors && !strcmp(argv[i], "--count-errors"))
            count_errors = true;
        else if (!check_markers && !strcmp(argv[i], "--markers"))
            check_markers = true;
        else
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
    int result = capture(fd, frames, count_errors, check_markers);
    if (close(fd))
        result = 1;
    return result;
}
