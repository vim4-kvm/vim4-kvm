/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Read-mode capture fixture for the actual v4l2src plugin using /dev/zero. */
#define _GNU_SOURCE
#include <errno.h>
#include <linux/videodev2.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>

#define YUV24 v4l2_fourcc('Y', 'U', 'V', '3')

int ioctl(int fd, unsigned long request, ...)
{
    va_list args;
    va_start(args, request);
    void *arg = va_arg(args, void *);
    va_end(args);
    struct stat st, zero;
    if (fstat(fd, &st) || stat("/dev/zero", &zero) || st.st_rdev != zero.st_rdev)
        return syscall(SYS_ioctl, fd, request, arg);

    unsigned int fourcc = getenv("TEST_V308") ? YUV24 : V4L2_PIX_FMT_NV12;
    switch (request) {
    case VIDIOC_QUERYCAP: {
        struct v4l2_capability *cap = arg;
        strcpy((char *)cap->driver, "t7-vdin-test");
        strcpy((char *)cap->card, "VDIN fixture");
        cap->capabilities = V4L2_CAP_VIDEO_CAPTURE | V4L2_CAP_READWRITE;
        return 0;
    }
    case VIDIOC_ENUM_FMT: {
        struct v4l2_fmtdesc *fmt = arg;
        if (fmt->index || fmt->type != V4L2_BUF_TYPE_VIDEO_CAPTURE) break;
        fmt->pixelformat = fourcc;
        return 0;
    }
    case VIDIOC_ENUM_FRAMESIZES: {
        struct v4l2_frmsizeenum *size = arg;
        if (size->index || size->pixel_format != fourcc) break;
        size->type = V4L2_FRMSIZE_TYPE_DISCRETE;
        size->discrete = (struct v4l2_frmsize_discrete){640, 480};
        return 0;
    }
    case VIDIOC_ENUM_FRAMEINTERVALS: {
        struct v4l2_frmivalenum *ival = arg;
        if (ival->index || ival->pixel_format != fourcc || ival->width != 640 || ival->height != 480) break;
        int base = atoi(getenv("TEST_VRR_BASE"));
        if (base) {
            ival->type = V4L2_FRMIVAL_TYPE_CONTINUOUS;
            ival->stepwise.min = (struct v4l2_fract){1, base > 0 ? base : 120};
            ival->stepwise.max = (struct v4l2_fract){1, 20};
            ival->stepwise.step = (struct v4l2_fract){1, 1};
        } else {
            ival->type = V4L2_FRMIVAL_TYPE_DISCRETE;
            ival->discrete = (struct v4l2_fract){atoi(getenv("TEST_TICKS")), 60000};
        }
        return 0;
    }

    case VIDIOC_G_INPUT:
        *(int *)arg = 0;
        return 0;
    case VIDIOC_ENUMINPUT: {
        struct v4l2_input *input = arg;
        if (input->index) break;
        input->type = V4L2_INPUT_TYPE_CAMERA;
        strcpy((char *)input->name, "HDMI");
        return 0;
    }
    case VIDIOC_G_FMT:
    case VIDIOC_TRY_FMT:
    case VIDIOC_S_FMT: {
        struct v4l2_format *fmt = arg;
        if (fmt->type != V4L2_BUF_TYPE_VIDEO_CAPTURE) break;
        fmt->fmt.pix = (struct v4l2_pix_format){
            .width=640, .height=480, .pixelformat=fourcc, .field=V4L2_FIELD_NONE,
            .bytesperline=(fourcc == YUV24 ? 640*3 : 640),
            .sizeimage=(fourcc == YUV24 ? 640*480*3 : 640*480*3/2), .colorspace=V4L2_COLORSPACE_REC709,
        };
        return 0;
    }
    case VIDIOC_G_PARM:
        ((struct v4l2_streamparm *)arg)->parm.capture.timeperframe =
            (struct v4l2_fract){atoi(getenv("TEST_TICKS")), 60000};
        return 0;
    }
    errno = EINVAL;
    return -1;
}
