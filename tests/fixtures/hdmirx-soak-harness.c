/* Deterministic V4L2 completions; no devices, scheduling or privileges. */
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <linux/videodev2.h>
#include <poll.h>

static unsigned int frame, streamoff, released;
static const char *scenario;
static uint64_t clock_ns = UINT64_C(100000000000);

static int fake_clock_gettime(clockid_t clock, struct timespec *out)
{
    assert(clock == CLOCK_MONOTONIC);
    out->tv_sec = clock_ns / 1000000000;
    out->tv_nsec = clock_ns % 1000000000;
    return 0;
}

static int fake_poll(struct pollfd *fds, nfds_t count, int timeout)
{
    assert(count == 1 && timeout == 2500 && fds->fd == 123);
    fds->revents = frame == 250 && !strcmp(scenario, "unplug") ? POLLERR : POLLIN;
    return 1;
}

static int fake_ioctl(int fd, unsigned long request, ...)
{
    va_list args;
    va_start(args, request);
    void *arg = va_arg(args, void *);
    va_end(args);
    assert(fd == 123);
    switch (request) {
    case VIDIOC_QUERY_DV_TIMINGS: {
        struct v4l2_dv_timings *t = arg;
        t->type = V4L2_DV_BT_656_1120;
        t->bt.width = 1920;
        t->bt.height = 1080;
        t->bt.pixelclock = 148500000;
        break;
    }
    case VIDIOC_S_FMT: {
        struct v4l2_pix_format *p = &((struct v4l2_format *)arg)->fmt.pix;
        p->bytesperline = 1952;
        p->sizeimage = 1952 * 1080 * 3 / 2 + 64;
        break;
    }
    case VIDIOC_REQBUFS:
        if (!((struct v4l2_requestbuffers *)arg)->count)
            released++;
        break;
    case VIDIOC_QBUF:
    case VIDIOC_STREAMON:
        break;
    case VIDIOC_STREAMOFF:
        streamoff++;
        if (!strcmp(scenario, "stop-failure"))
            return -1;
        break;
    case VIDIOC_DQBUF: {
        struct v4l2_buffer *b = arg;
        clock_ns += 16666667;
        b->index = frame % 8;
        b->sequence = UINT32_MAX - 5 + frame;
        b->flags = V4L2_BUF_FLAG_TIMESTAMP_MONOTONIC;
        b->bytesused = 1952 * 1080 * 3 / 2;
        b->timestamp.tv_sec = clock_ns / 1000000000;
        b->timestamp.tv_usec = clock_ns % 1000000000 / 1000;
        if (frame == 250) {
            if (!strcmp(scenario, "error")) {
                b->flags |= V4L2_BUF_FLAG_ERROR;
                b->sequence = 0;
                b->timestamp.tv_sec = b->timestamp.tv_usec = 0;
            } else if (!strcmp(scenario, "gap")) {
                b->sequence++;
            } else if (!strcmp(scenario, "stale")) {
                b->timestamp.tv_sec--;
            }
        }
        frame++;
        break;
    }
    default:
        assert(!"unexpected V4L2 operation");
    }
    return 0;
}

#define clock_gettime fake_clock_gettime
#define ioctl fake_ioctl
#define poll fake_poll
#define main soak_main
#include "../../tools/hdmirx-soak.c"
#undef main

int main(int argc, char **argv)
{
    assert(argc == 2);
    scenario = argv[1];
    int result = capture(123, 600);
    assert(streamoff == 1 && released == 1);
    return result;
}
