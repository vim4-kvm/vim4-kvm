/* Linux only: cc -O2 -Wall -Wextra -Werror -pthread rtp-udp-bench.c -o rtp-udp-bench
 * Usage: rtp-udp-bench [measured_frames=300] [warmup_frames=30] [rcvbuf=4194304]
 *                      [force-private-buffer]
 * The explicit final flag uses SO_RCVBUFFORCE on this private socket only;
 * it needs CAP_NET_ADMIN and never changes the host's socket defaults.
 * This measures socket delivery of pregenerated 1200-byte datagrams over loopback,
 * including per-frame iovec/mmsghdr preparation. It does not implement SRTP/ICE or
 * measure a production transport, encoder, network, decoder, or display latency.
 * Three paired groups rotate method order; every frame drains before the next.
 * Any send/receive/content/order error fails the run, without retrying the frame.
 */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/utsname.h>
#include <time.h>
#include <unistd.h>

enum { BYTES = 1200, MAX_PACKETS = 220, GROUPS = 3, METHODS = 4, COUNTS = 4 };
static const int packet_counts[] = {38, 48, 180, 220}, batches[] = {1, 8, 32, 64};
struct packet { uint32_t magic, frame, seq, count, marker; unsigned char data[BYTES - 20]; };
_Static_assert(sizeof(struct packet) == BYTES, "packet layout");
struct receiver {
    int fd, active, done, stop, wanted, received, receive_errno;
    ssize_t lengths[MAX_PACKETS];
    struct sockaddr_in sources[MAX_PACKETS];
    struct packet packets[MAX_PACKETS];
    pthread_mutex_t mutex;
    pthread_cond_t changed;
};
struct error { const char *type; uint32_t frame; int seq, code; };
struct round { int group, packets, batch, measured, warmed; double *samples; double failed_frame_us; };
static struct error *errors;
static size_t error_count;

static void error(const char *type, uint32_t frame, int seq, int code) {
    struct error *next = realloc(errors, (error_count + 1) * sizeof(*errors));
    if (!next) { perror("error log allocation"); exit(2); }
    errors = next; errors[error_count++] = (struct error){type, frame, seq, code};
    fprintf(stderr, "%s frame=%u seq=%d code=%d\n", type, frame, seq, code);
}
static double now_ns(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return (double)t.tv_sec * 1e9 + t.tv_nsec;
}
static void *receive_frames(void *opaque) {
    struct receiver *r = opaque;
    pthread_mutex_lock(&r->mutex);
    for (;;) {
        while (!r->active && !r->stop) pthread_cond_wait(&r->changed, &r->mutex);
        if (r->stop) break;
        pthread_mutex_unlock(&r->mutex);
        r->received = 0; r->receive_errno = 0;
        for (int i = 0; i < r->wanted; i++) {
            socklen_t size = sizeof(r->sources[i]);
            ssize_t n = recvfrom(r->fd, &r->packets[i], BYTES, MSG_TRUNC,
                                 (struct sockaddr *)&r->sources[i], &size);
            if (n < 0) { r->receive_errno = errno; break; }
            r->lengths[i] = n; r->received++;
        }
        pthread_mutex_lock(&r->mutex);
        r->active = 0; r->done = 1; pthread_cond_broadcast(&r->changed);
    }
    pthread_mutex_unlock(&r->mutex);
    return NULL;
}
static int compare_double(const void *a, const void *b) {
    double x = *(const double *)a, y = *(const double *)b;
    return (x > y) - (x < y);
}
static double percentile(const double *sorted, int n, double fraction) {
    return n ? sorted[(int)(fraction * n + .999999) - 1] : 0;
}
static int parse_positive(const char *text, long maximum) {
    char *end; errno = 0; long n = strtol(text, &end, 10);
    if (errno || !*text || *end || n < 1 || n > maximum) return 0;
    return (int)n;
}
static void make_packets(struct packet *packets, uint32_t frame, int count) {
    for (int i = 0; i < count; i++) {
        packets[i].magic = htonl(0x52545042); packets[i].frame = htonl(frame);
        packets[i].seq = htonl((uint32_t)i); packets[i].count = htonl((uint32_t)count);
        packets[i].marker = htonl(i == count - 1);
        uint32_t state = frame * 2654435761U + (uint32_t)i + 1;
        for (size_t j = 0; j < sizeof(packets[i].data); j++) {
            state ^= state << 13; state ^= state >> 17; state ^= state << 5;
            packets[i].data[j] = (unsigned char)state;
        }
    }
}
static int validate(struct receiver *r, const struct packet *expected,
                    uint32_t frame, int count, uint16_t source_port) {
    int seen[MAX_PACKETS] = {0}; size_t before = error_count;
    if (r->receive_errno) error("receive", frame, -1, r->receive_errno);
    for (int i = 0; i < r->received; i++) {
        struct packet *p = &r->packets[i]; uint32_t seq = ntohl(p->seq);
        if (r->lengths[i] != BYTES) { error("length", frame, i, (int)r->lengths[i]); continue; }
        if (r->sources[i].sin_addr.s_addr != htonl(INADDR_LOOPBACK) ||
            r->sources[i].sin_port != source_port) error("source", frame, i, 0);
        if (ntohl(p->frame) != frame) { error("frame", frame, i, 0); continue; }
        if (seq >= (uint32_t)count) { error("sequence_range", frame, i, 0); continue; }
        if (seen[seq]++) error("duplicate", frame, (int)seq, 0);
        if (seq != (uint32_t)i) error("order", frame, (int)seq, 0);
        if (memcmp(p, &expected[seq], BYTES)) error("content_or_header", frame, (int)seq, 0);
    }
    for (int i = 0; i < count; i++) if (!seen[i]) error("missing", frame, i, 0);
    /* The receiver is parked at the barrier. Any queued extra datagram fails. */
    struct packet extra; ssize_t n;
    while ((n = recv(r->fd, &extra, sizeof(extra), MSG_DONTWAIT | MSG_TRUNC)) >= 0)
        error("extra", frame, -1, (int)n);
    if (errno != EAGAIN && errno != EWOULDBLOCK) error("drain", frame, -1, errno);
    return before == error_count;
}
int main(int argc, char **argv) {
    int frames = 300, warmup = 30, requested_rcvbuf = 4194304;
    int force_private_buffer = argc == 5 && !strcmp(argv[4], "force-private-buffer");
    if (argc > 5 || (argc == 5 && !force_private_buffer) ||
        (argc > 1 && !(frames = parse_positive(argv[1], 1000000))) ||
        (argc > 2 && !(warmup = parse_positive(argv[2], 1000000))) ||
        (argc > 3 && !(requested_rcvbuf = parse_positive(argv[3], 67108864)))) {
        fprintf(stderr, "usage: %s [frames>0] [warmup>0] [rcvbuf>0] [force-private-buffer]\n", argv[0]); return 2;
    }
    struct utsname environment = {0}; uname(&environment);
    struct receiver r = {.fd = -1, .mutex = PTHREAD_MUTEX_INITIALIZER,
                         .changed = PTHREAD_COND_INITIALIZER};
    struct round rounds[GROUPS * COUNTS * METHODS] = {0};
    struct packet packets[MAX_PACKETS];
    struct sockaddr_in target = {.sin_family = AF_INET, .sin_addr.s_addr = htonl(INADDR_LOOPBACK)};
    struct sockaddr_in source = target; socklen_t address_size = sizeof(target);
    int tx = -1, actual_rcvbuf = 0, actual_sndbuf = 0, started = 0, completed = 0;
    pthread_t thread; uint32_t frame_id = 0; int round_count = 0;
    double *all_samples = calloc((size_t)GROUPS * COUNTS * METHODS * frames, sizeof(double));
    if (!all_samples) { error("allocation", 0, -1, errno); goto output; }
    r.fd = socket(AF_INET, SOCK_DGRAM, 0); tx = socket(AF_INET, SOCK_DGRAM, 0);
    if (r.fd < 0 || tx < 0) { error("socket", 0, -1, errno); goto output; }
    struct timeval timeout = {.tv_sec = 1};
    if (setsockopt(r.fd, SOL_SOCKET, force_private_buffer ? SO_RCVBUFFORCE : SO_RCVBUF,
                   &requested_rcvbuf, sizeof(int)) ||
        setsockopt(r.fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) ||
        setsockopt(tx, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)) ||
        bind(r.fd, (struct sockaddr *)&target, sizeof(target)) ||
        bind(tx, (struct sockaddr *)&source, sizeof(source)) ||
        getsockname(r.fd, (struct sockaddr *)&target, &address_size) ||
        getsockname(tx, (struct sockaddr *)&source, &address_size)) {
        error("socket_setup", 0, -1, errno); goto output;
    }
    socklen_t option_size = sizeof(int);
    if (getsockopt(r.fd, SOL_SOCKET, SO_RCVBUF, &actual_rcvbuf, &option_size) ||
        getsockopt(tx, SOL_SOCKET, SO_SNDBUF, &actual_sndbuf, &option_size)) {
        error("socket_buffers", 0, -1, errno); goto output;
    }
    int thread_error = pthread_create(&thread, NULL, receive_frames, &r);
    if (thread_error) { error("pthread_create", 0, -1, thread_error); goto output; }
    started = 1;
    for (int group = 0; group < GROUPS; group++) for (int c = 0; c < COUNTS; c++)
        for (int order = 0; order < METHODS; order++) {
            int method = (order + group + c) % METHODS, count = packet_counts[c], batch = batches[method];
            struct round *round = &rounds[round_count];
            *round = (struct round){group, count, batch, 0, 0, all_samples + (size_t)round_count * frames, 0};
            round_count++;
            for (int f = -warmup; f < frames; f++) {
                make_packets(packets, ++frame_id, count);
                pthread_mutex_lock(&r.mutex); r.wanted = count; r.done = 0; r.active = 1;
                pthread_cond_broadcast(&r.changed); pthread_mutex_unlock(&r.mutex);
                int send_errno = 0, sent = 0;
                double begin = now_ns();
                if (batch == 1) {
                    for (; sent < count; sent++) {
                        ssize_t n = sendto(tx, &packets[sent], BYTES, 0, (struct sockaddr *)&target, sizeof(target));
                        if (n != BYTES) { send_errno = n < 0 ? errno : EIO; break; }
                    }
                } else {
                    struct mmsghdr messages[64]; struct iovec vectors[64];
                    for (int offset = 0; offset < count;) {
                        int n = count - offset < batch ? count - offset : batch;
                        memset(messages, 0, (size_t)n * sizeof(*messages));
                        for (int i = 0; i < n; i++) {
                            vectors[i] = (struct iovec){&packets[offset + i], BYTES};
                            messages[i].msg_hdr.msg_name = &target;
                            messages[i].msg_hdr.msg_namelen = sizeof(target);
                            messages[i].msg_hdr.msg_iov = &vectors[i]; messages[i].msg_hdr.msg_iovlen = 1;
                        }
                        int delivered = sendmmsg(tx, messages, (unsigned)n, 0);
                        if (delivered > 0) sent += delivered;
                        if (delivered != n) { send_errno = delivered < 0 ? errno : EIO; break; }
                        for (int i = 0; i < n; i++) if (messages[i].msg_len != BYTES) send_errno = EIO;
                        if (send_errno) break;
                        offset += n;
                    }
                }
                double elapsed = (now_ns() - begin) / 1000.0;
                if (send_errno || sent != count) error("send_or_partial", frame_id, sent, send_errno);
                pthread_mutex_lock(&r.mutex);
                while (!r.done) pthread_cond_wait(&r.changed, &r.mutex);
                pthread_mutex_unlock(&r.mutex);
                int valid = validate(&r, packets, frame_id, count, source.sin_port);
                if (!valid || error_count) { round->failed_frame_us = elapsed; goto output; }
                if (f < 0) round->warmed++; else round->samples[round->measured++] = elapsed;
            }
        }
    completed = 1;
output:
    if (started) {
        pthread_mutex_lock(&r.mutex); r.stop = 1; pthread_cond_broadcast(&r.changed);
        pthread_mutex_unlock(&r.mutex); pthread_join(thread, NULL);
    }
    if (r.fd >= 0) close(r.fd);
    if (tx >= 0) close(tx);
    printf("{\"environment\":{\"sysname\":\"%s\",\"release\":\"%s\",\"machine\":\"%s\",\"online_cpus\":%ld,\"clock\":\"CLOCK_MONOTONIC\",\"receiver_threads\":1},",
           environment.sysname, environment.release, environment.machine, sysconf(_SC_NPROCESSORS_ONLN));
    printf("\"config\":{\"source\":\"127.0.0.1\",\"target\":\"127.0.0.1\",\"packet_bytes\":%d,\"paired_groups\":%d,\"frames_per_round\":%d,\"warmup_per_round\":%d,\"requested_rcvbuf\":%d,\"actual_rcvbuf\":%d,\"actual_sndbuf\":%d,\"force_private_rcvbuf\":%s,\"frame_barrier\":true,\"timing\":\"prepare_iovec_mmsghdr_and_send_only_us\",\"scope\":\"pregenerated_datagrams_socket_delivery_only\"},\"samples\":[",
           BYTES, GROUPS, frames, warmup, requested_rcvbuf, actual_rcvbuf, actual_sndbuf,
           force_private_buffer ? "true" : "false");
    for (int i = 0; i < round_count; i++) {
        struct round *v = &rounds[i];
        printf("%s{\"group\":%d,\"packets\":%d,\"method\":\"%s\",\"batch\":%d,\"warmed\":%d,\"count\":%d,\"failed_frame_us\":%.3f,\"frame_us\":[",
               i ? "," : "", v->group, v->packets, v->batch == 1 ? "sendto" : "sendmmsg", v->batch, v->warmed, v->measured, v->failed_frame_us);
        for (int j = 0; j < v->measured; j++) printf("%s%.3f", j ? "," : "", v->samples[j]);
        qsort(v->samples, (size_t)v->measured, sizeof(double), compare_double);
        printf("],\"p50_us\":%.3f,\"p95_us\":%.3f,\"p99_us\":%.3f}",
               percentile(v->samples, v->measured, .5), percentile(v->samples, v->measured, .95), percentile(v->samples, v->measured, .99));
    }
    printf("],\"completion\":{\"complete\":%s,\"passed\":%s,\"rounds_started\":%d,\"rounds_expected\":%d,\"last_frame\":%u},\"errors\":[",
           completed ? "true" : "false", completed && !error_count ? "true" : "false", round_count, GROUPS * COUNTS * METHODS, frame_id);
    for (size_t i = 0; i < error_count; i++) printf("%s{\"type\":\"%s\",\"frame\":%u,\"seq\":%d,\"code\":%d}",
        i ? "," : "", errors[i].type, errors[i].frame, errors[i].seq, errors[i].code);
    puts("]}"); free(all_samples); free(errors);
    return completed && !error_count ? 0 : 1;
}
