/* SPDX-License-Identifier: LGPL-2.1-or-later */
/* Local broker v1 source; never opens a capture device. */
#define _GNU_SOURCE
#include <gst/base/gstpushsrc.h>
#include <gst/allocators/gstdmabuf.h>
#include <gst/video/video.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#define PACKAGE "vim4-passthrough73"
typedef struct { GstPushSrc parent; gint socket, flushing, height; guint64 origin; } BrokerSrc;
typedef struct { GstPushSrcClass parent; } BrokerSrcClass;
G_DEFINE_TYPE(BrokerSrc, broker_src, GST_TYPE_PUSH_SRC)
typedef struct { int socket; guint64 token, generation; } Lease;

static gboolean send_text(int fd, const char *text)
{ return send(fd, text, strlen(text), MSG_NOSIGNAL | MSG_DONTWAIT) == (ssize_t)strlen(text); }

static void retired(gpointer data, GstMiniObject *unused)
{
    (void)unused;
    Lease *lease = data;
    gchar *ack = g_strdup_printf("{\"version\":1,\"op\":\"release\",\"token\":%" G_GUINT64_FORMAT
                                ",\"generation\":%" G_GUINT64_FORMAT "}", lease->token, lease->generation);
    send_text(lease->socket, ack); /* Failure pins the server lease; never fake completion. */
    g_free(ack); close(lease->socket); g_free(lease);
}

/* Broker emits a fixed JSON schema. Require exactly one scalar of each key;
 * metadata string values are separately qualified before importing memory.
 */
static gboolean number(const char *json, const char *key, guint64 *out)
{
    gchar *pattern = g_strdup_printf("\"%s\"\\s*:\\s*([0-9]+)\\s*[,}]", key);
    GRegex *regex = g_regex_new(pattern, 0, 0, NULL);
    GMatchInfo *match = NULL;
    gboolean valid = g_regex_match(regex, json, 0, &match);
    if (valid) {
        gchar *value = g_match_info_fetch(match, 1), *end;
        errno = 0; *out = g_ascii_strtoull(value, &end, 10);
        valid = !errno && !*end && !g_match_info_next(match, NULL);
        g_free(value);
    }
    g_match_info_free(match); g_regex_unref(regex); g_free(pattern);
    return valid;
}

static gboolean text(const char *json, const char *key, const char *value)
{
    gchar *pattern = g_strdup_printf("\"%s\"\\s*:\\s*\"%s\"", key, value);
    gboolean valid = g_regex_match_simple(pattern, json, 0, 0);
    g_free(pattern); return valid;
}

static gboolean start(GstBaseSrc *base)
{
    BrokerSrc *self = (BrokerSrc *)base;
    const gchar *path = g_getenv("VIM4_BROKER_SOCKET");
    struct sockaddr_un address = {.sun_family = AF_UNIX};
    if (!path || path[0] != '/' || strlen(path) >= sizeof(address.sun_path)) return FALSE;
    strcpy(address.sun_path, path);
    self->socket = socket(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0);
    if (self->socket < 0) return FALSE;
    struct timeval timeout = {.tv_usec = 200000};
    if (connect(self->socket, (struct sockaddr *)&address, sizeof(address)) ||
        setsockopt(self->socket, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) ||
        !send_text(self->socket, "{\"version\":1,\"op\":\"subscribe\",\"name\":\"gstreamer\",\"in_flight_limit\":7}")) {
        close(self->socket); self->socket = -1; return FALSE;
    }
    self->origin = GST_CLOCK_TIME_NONE;
    g_atomic_int_set(&self->flushing, 0);
    return TRUE;
}

static gboolean stop(GstBaseSrc *base)
{
    BrokerSrc *self = (BrokerSrc *)base;
    if (self->socket >= 0) close(self->socket);
    self->socket = -1; return TRUE;
}
static gboolean unlock(GstBaseSrc *base)
{ g_atomic_int_set(&((BrokerSrc *)base)->flushing, 1); return TRUE; }
static gboolean unlock_stop(GstBaseSrc *base)
{ g_atomic_int_set(&((BrokerSrc *)base)->flushing, 0); return TRUE; }

static GstFlowReturn create(GstPushSrc *base, GstBuffer **buffer)
{
    BrokerSrc *self = (BrokerSrc *)base;
    if (!send_text(self->socket, "{\"version\":1,\"op\":\"take\"}")) return GST_FLOW_ERROR;
    while (!g_atomic_int_get(&self->flushing)) {
        char packet[16385];
        union { struct cmsghdr alignment; char bytes[CMSG_SPACE(sizeof(int) * 8)]; } control;
        struct iovec iov = {.iov_base = packet, .iov_len = sizeof(packet)-1};
        struct msghdr msg = {.msg_iov = &iov, .msg_iovlen = 1,
                            .msg_control = control.bytes, .msg_controllen = sizeof(control)};
        ssize_t n = recvmsg(self->socket, &msg, MSG_CMSG_CLOEXEC);
        if (n < 0 && (errno == EAGAIN || errno == EINTR)) continue;
        if (n <= 0) return GST_FLOW_ERROR;
        int fd = -1; unsigned count = 0;
        for (struct cmsghdr *c = CMSG_FIRSTHDR(&msg); c; c = CMSG_NXTHDR(&msg,c)) {
            if (c->cmsg_level != SOL_SOCKET || c->cmsg_type != SCM_RIGHTS) continue;
            unsigned size = (c->cmsg_len - CMSG_LEN(0)) / sizeof(int);
            for (unsigned i = 0; i < size; i++) {
                int received = ((int *)CMSG_DATA(c))[i];
                if (!count++) fd = received; else close(received);
            }
        }
        packet[n] = 0;
        guint64 version;
        if ((msg.msg_flags & (MSG_TRUNC | MSG_CTRUNC)) || count > 1 ||
            !number(packet,"version",&version) || version != 1) goto invalid;
        if (count == 0) {
            if (text(packet,"type","ready") || text(packet,"type","release-pending")) continue;
            if (text(packet,"type","idle")) {
                g_usleep(2000);
                if (send_text(self->socket,"{\"version\":1,\"op\":\"take\"}")) continue;
            }
            goto invalid;
        }
        guint64 width,height,pitch,uv,bytes,modifier,token,generation,timestamp;
        if (!text(packet,"type","frame") || !text(packet,"format","NV12") ||
            !text(packet,"colorspace","rec709") || !text(packet,"quantization","limited") ||
            !number(packet,"width",&width) || !number(packet,"height",&height) ||
            !number(packet,"pitch",&pitch) || !number(packet,"uv_offset",&uv) ||
            !number(packet,"allocation_size",&bytes) || !number(packet,"modifier",&modifier) ||
            !number(packet,"token",&token) || !number(packet,"generation",&generation) ||
            !number(packet,"timestamp_ns",&timestamp) || modifier || !width || !height ||
            width > 4096 || height > 2160 || (width&1) || (height&1) || pitch < width ||
            pitch > 16384 || uv != pitch*height || bytes < uv+pitch*height/2 ||
            (self->height && self->height != (gint)height)) goto invalid;
        GstCaps *caps = gst_caps_new_simple("video/x-raw", "format", G_TYPE_STRING,"NV12",
            "width",G_TYPE_INT,(gint)width,"height",G_TYPE_INT,(gint)height,
            "colorimetry",G_TYPE_STRING,"bt709",NULL);
        gboolean accepted = gst_base_src_set_caps(GST_BASE_SRC(self),caps);
        gst_caps_unref(caps);
        if (!accepted) goto invalid;
        GstAllocator *allocator = gst_dmabuf_allocator_new();
        GstMemory *memory = gst_dmabuf_allocator_alloc(allocator,fd,bytes);
        gst_object_unref(allocator);
        if (!memory) goto invalid;
        Lease *lease = g_new0(Lease,1);
        lease->socket = fcntl(self->socket,F_DUPFD_CLOEXEC,0); lease->token = token; lease->generation = generation;
        if (lease->socket < 0) { g_free(lease); gst_memory_unref(memory); return GST_FLOW_ERROR; }
        gst_mini_object_weak_ref(GST_MINI_OBJECT(memory),retired,lease);
        *buffer = gst_buffer_new(); gst_buffer_append_memory(*buffer,memory);
        gsize offsets[GST_VIDEO_MAX_PLANES] = {0,uv};
        gint strides[GST_VIDEO_MAX_PLANES] = {(gint)pitch,(gint)pitch};
        gst_buffer_add_video_meta_full(*buffer,0,GST_VIDEO_FORMAT_NV12,width,height,2,offsets,strides);
        if (self->origin == GST_CLOCK_TIME_NONE) self->origin = timestamp;
        GST_BUFFER_PTS(*buffer) = timestamp >= self->origin ? timestamp-self->origin : 0;
        return GST_FLOW_OK;
invalid:
        if (fd >= 0) close(fd);
        GST_ELEMENT_ERROR(self,RESOURCE,READ,("Invalid broker frame or unsupported pixel domain"),(NULL));
        return GST_FLOW_ERROR;
    }
    return GST_FLOW_FLUSHING;
}

static void set_property(GObject *object, guint id, const GValue *v, GParamSpec *spec)
{ if (id == 1) ((BrokerSrc *)object)->height = g_value_get_int(v); else G_OBJECT_WARN_INVALID_PROPERTY_ID(object,id,spec); }
static gint input_rate(void)
{
    const gchar *capture = g_getenv("VIM4_BROKER_SOCKET");
    if (!capture) return 0;
    gchar *directory = g_path_get_dirname(capture);
    gchar *path = g_build_filename(directory,"control.sock",NULL);
    struct sockaddr_un address = {.sun_family = AF_UNIX};
    gint rate = 0, fd = -1;
    if (strlen(path) >= sizeof(address.sun_path)) goto done;
    strcpy(address.sun_path,path);
    fd = socket(AF_UNIX,SOCK_SEQPACKET | SOCK_CLOEXEC,0);
    if (fd < 0) goto done;
    struct timeval timeout = {.tv_usec = 200000};
    if (connect(fd,(struct sockaddr *)&address,sizeof(address)) ||
        setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout)) ||
        !send_text(fd,"{\"version\":1,\"op\":\"status\"}")) goto done;
    char data[4097];
    ssize_t size = recv(fd,data,sizeof(data)-1,0);
    if (size > 0) {
        guint64 value; data[size] = 0;
        if (number(data,"inputRate",&value) && value <= 12000) rate = value;
    }
done:
    if (fd >= 0) close(fd);
    g_free(path); g_free(directory); return rate;
}
static void get_property(GObject *object, guint id, GValue *v, GParamSpec *spec)
{ if (id == 1) g_value_set_int(v,((BrokerSrc *)object)->height); else if (id == 2) g_value_set_int(v,input_rate()); else G_OBJECT_WARN_INVALID_PROPERTY_ID(object,id,spec); }
static void broker_src_class_init(BrokerSrcClass *klass)
{
    GObjectClass *object = G_OBJECT_CLASS(klass);
    object->set_property = set_property; object->get_property = get_property;
    g_object_class_install_property(object,1,g_param_spec_int("height","Height","Zero or native height only",0,2160,0,G_PARAM_READWRITE));
    g_object_class_install_property(object,2,g_param_spec_int("input-rate","Input rate","Unknown until qualified by controller",0,12000,0,G_PARAM_READABLE));
    GstBaseSrcClass *source = GST_BASE_SRC_CLASS(klass);
    source->start = start; source->stop = stop; source->unlock = unlock; source->unlock_stop = unlock_stop;
    GST_PUSH_SRC_CLASS(klass)->create = create;
    GstElementClass *element = GST_ELEMENT_CLASS(klass);
    GstCaps *caps = gst_caps_from_string("video/x-raw,format=NV12,width=[2,4096],height=[2,2160]");
    gst_element_class_add_pad_template(element,gst_pad_template_new("src",GST_PAD_SRC,GST_PAD_ALWAYS,caps));
    gst_caps_unref(caps);
    gst_element_class_set_static_metadata(element,"Independent VIM4 broker","Source/Video","Leased DMA-buf IPC source","vim4-kvm");
}
static void broker_src_init(BrokerSrc *self)
{ self->socket = -1; gst_base_src_set_live(GST_BASE_SRC(self),TRUE); gst_base_src_set_format(GST_BASE_SRC(self),GST_FORMAT_TIME); }
static gboolean plugin_init(GstPlugin *plugin)
{ return gst_element_register(plugin,"vim4brokersrc",GST_RANK_NONE,broker_src_get_type()); }
GST_PLUGIN_DEFINE(GST_VERSION_MAJOR,GST_VERSION_MINOR,vim4broker,"Independent broker source",plugin_init,"0.1","LGPL",PACKAGE,"https://github.com/vim4-kvm/vim4-kvm")
