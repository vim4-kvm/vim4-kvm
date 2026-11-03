/* Exclusive, live 4K YUV24 queue qualification after capture-integrity. */
#include <errno.h>
#include <fcntl.h>
#include <linux/dma-buf.h>
#include <linux/videodev2.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>

static void require(int condition, const char *operation)
{
    if (!condition) {
        perror(operation);
        exit(EXIT_FAILURE);
    }
}

int main(int argc, char **argv)
{
    require(argc == 2, "expected capture device");
    int fd = open(argv[1], O_RDWR | O_NONBLOCK);
    require(fd >= 0, "open VDIN");
    struct v4l2_format format = {.type = V4L2_BUF_TYPE_VIDEO_CAPTURE};
    format.fmt.pix.width = 3840;
    format.fmt.pix.height = 2160;
    format.fmt.pix.pixelformat = v4l2_fourcc('Y', 'U', 'V', '3');
    require(ioctl(fd, VIDIOC_S_FMT, &format) == 0, "set YUV24");
    require(format.fmt.pix.pixelformat == v4l2_fourcc('Y', 'U', 'V', '3') &&
            format.fmt.pix.bytesperline >= 3840 * 3, "YUV24 layout");
    struct v4l2_create_buffers over = {.format = format, .memory = V4L2_MEMORY_MMAP, .count = 1};
    over.format.fmt.pix.sizeimage = 25 * 1024 * 1024;
    require(ioctl(fd, VIDIOC_CREATE_BUFS, &over) == -1 && errno == EINVAL, "oversized CREATE_BUFS");
    struct v4l2_requestbuffers req = {.type = format.type, .memory = V4L2_MEMORY_MMAP, .count = 8};
    require(ioctl(fd, VIDIOC_REQBUFS, &req) == 0 && req.count == 7, "seven-buffer limit");
    struct v4l2_buffer buf = {.type = format.type, .memory = V4L2_MEMORY_MMAP};
    for (unsigned int i = 0; i < req.count; i++) {
        buf.index = i;
        require(ioctl(fd, VIDIOC_QBUF, &buf) == 0, "queue YUV24 buffer");
    }
    require(ioctl(fd, VIDIOC_STREAMON, &format.type) == 0, "stream on");
    struct pollfd ready = {.fd = fd, .events = POLLIN};
    require(poll(&ready, 1, 3000) == 1 && ioctl(fd, VIDIOC_DQBUF, &buf) == 0, "first YUV24 frame");
    struct v4l2_exportbuffer exp = {.type = format.type, .index = buf.index, .flags = O_RDONLY};
    require(ioctl(fd, VIDIOC_EXPBUF, &exp) == 0, "export frame");
    require(ioctl(fd, VIDIOC_STREAMOFF, &format.type) == 0, "stream off");
    close(fd);
    unsigned char *frame = mmap(NULL, buf.length, PROT_READ, MAP_SHARED, exp.fd, 0);
    require(frame != MAP_FAILED, "map export after closing VDIN");
    struct dma_buf_sync sync = {.flags = DMA_BUF_SYNC_READ | DMA_BUF_SYNC_START};
    require(ioctl(exp.fd, DMA_BUF_IOCTL_SYNC, &sync) == 0, "start CPU read");
    printf("buffers=%u stride=%u sizeimage=%u exported_first_y=%u\n",
           req.count, format.fmt.pix.bytesperline, format.fmt.pix.sizeimage, frame[0]);
    sync.flags = DMA_BUF_SYNC_READ | DMA_BUF_SYNC_END;
    require(ioctl(exp.fd, DMA_BUF_IOCTL_SYNC, &sync) == 0, "finish CPU read");
    munmap(frame, buf.length);
    close(exp.fd);
    return 0;
}
