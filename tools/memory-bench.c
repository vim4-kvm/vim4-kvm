/* Linux host/board microbenchmark. Build once with -O2 -Wall -Wextra -Werror. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdint.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/statfs.h>
#include <time.h>
#include <unistd.h>

static void fail(const char *what)
{
    perror(what);
    exit(1);
}

static uint64_t clock_ns(void)
{
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts)) fail("clock_gettime");
    return (uint64_t)ts.tv_sec * 1000000000 + ts.tv_nsec;
}

static struct rusage before;
static uint64_t begin;
static int cpu_begin;
static char frequency_begin[32];

static void frequency(int cpu, char result[32])
{
    char path[160];
    snprintf(path, sizeof(path), "/sys/devices/system/cpu/cpu%d/cpufreq/scaling_cur_freq", cpu);
    FILE *file = fopen(path, "r");
    long value;
    if (file && fscanf(file, "%ld", &value) == 1 && value > 0)
        snprintf(result, 32, "%ld", value);
    else
        strcpy(result, "null");
    if (file) fclose(file);
}

static void start(void)
{
    cpu_begin = sched_getcpu();
    if (cpu_begin < 0) fail("sched_getcpu");
    frequency(cpu_begin, frequency_begin);
    if (getrusage(RUSAGE_SELF, &before)) fail("getrusage");
    begin = clock_ns();
}

static void report(const char *phase, size_t size, unsigned rep, size_t bytes)
{
    uint64_t elapsed = clock_ns() - begin;
    struct rusage after;
    if (getrusage(RUSAGE_SELF, &after)) fail("getrusage");
    int cpu_end = sched_getcpu();
    if (cpu_end < 0) fail("sched_getcpu");
    char frequency_end[32];
    frequency(cpu_end, frequency_end);
    if (!elapsed) { fprintf(stderr, "clock resolution too low\n"); exit(1); }
    printf("{\"phase\":\"%s\",\"size\":%zu,\"rep\":%u,\"bytes\":%zu,"
           "\"ns\":%" PRIu64 ",\"begin_ns\":%" PRIu64 ",\"minflt\":%ld,\"majflt\":%ld,"
           "\"nvcsw\":%ld,\"nivcsw\":%ld,\"mib_s\":%.3f,\"minor_faults_s\":%.3f,"
           "\"cpu_begin\":%d,\"cpu_end\":%d,\"freq_begin_khz\":%s,\"freq_end_khz\":%s}\n", phase, size, rep, bytes, elapsed, begin,
           after.ru_minflt - before.ru_minflt, after.ru_majflt - before.ru_majflt,
           after.ru_nvcsw - before.ru_nvcsw, after.ru_nivcsw - before.ru_nivcsw,
           (double)bytes * 1e9 / elapsed / (1024 * 1024),
           (after.ru_minflt - before.ru_minflt) * 1e9 / elapsed,
           cpu_begin, cpu_end, frequency_begin, frequency_end);
}

static void transfer(int fd, void *buffer, size_t size, int reading)
{
    size_t offset = 0;
    while (offset < size) {
        ssize_t n = reading ? pread(fd, (char *)buffer + offset, size - offset, offset)
                            : pwrite(fd, (char *)buffer + offset, size - offset, offset);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) fail("transfer");
        offset += (size_t)n;
    }
}

int main(int argc, char **argv)
{
    if (argc != 3) {
        fprintf(stderr, "usage: memory-bench EMPTY_TMPFS_DIRECTORY REPEATS(1..9)\n");
        return 2;
    }
    char *end;
    long repeats = strtol(argv[2], &end, 10);
    if (*end || repeats < 1 || repeats > 9) return 2;
    cpu_set_t mask;
    if (sched_getaffinity(0, sizeof(mask), &mask)) fail("sched_getaffinity");
    if (CPU_COUNT(&mask) != 1) {
        fprintf(stderr, "requires a single pinned CPU (use the Python runner)\n");
        return 2;
    }
    struct statfs fs;
    if (statfs(argv[1], &fs)) fail("statfs");
    if ((unsigned long)fs.f_type != 0x01021994UL) {
        fprintf(stderr, "requires tmpfs\n");
        return 2;
    }
    alarm(150);
    const size_t maximum = 64 * 1024 * 1024;
    if ((uint64_t)fs.f_bavail * fs.f_bsize < 4 * maximum) {
        fprintf(stderr, "requires 256 MiB tmpfs headroom\n");
        return 2;
    }
    unsigned char *src = malloc(maximum), *dst = malloc(maximum);
    if (!src || !dst) fail("malloc");
    memset(src, 0x5a, maximum);
    memset(dst, 0, maximum);
    void *(*volatile copy)(void *, const void *, size_t) = memcpy;
    const size_t sizes[] = {4096, 65536, 131072, 262144, 524288, 1048576,
                           2097152, 4838400, 8388608, 16777216, 67108864};
    for (size_t k = 0; k < sizeof(sizes) / sizeof(sizes[0]); ++k) {
        size_t size = sizes[k];
        unsigned loops = (unsigned)(maximum / size);
        for (unsigned rep = 0; rep < (unsigned)repeats; ++rep) {
            start();
            for (unsigned i = 0; i < loops; ++i) copy(dst, src, size);
            report("memcpy_hot", size, rep, size * loops);
            if (memcmp(dst, src, size)) fail("memcpy verification");
        }
    }
    long page = sysconf(_SC_PAGESIZE);
    if (page <= 0) fail("page size");
    for (int small = 0; small < 2; ++small) {
        for (unsigned rep = 0; rep < (unsigned)repeats; ++rep) {
            void *mapping = mmap(NULL, maximum, PROT_READ | PROT_WRITE,
                                 MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
            if (mapping == MAP_FAILED) fail("mmap");
            if (small && madvise(mapping, maximum, MADV_NOHUGEPAGE)) fail("madvise");
            volatile unsigned char *p = mapping;
            start();
            for (size_t offset = 0; offset < maximum; offset += (size_t)page) p[offset] = 1;
            report(small ? "anon_touch_nohuge" : "anon_touch_default", maximum, rep, maximum);
            start();
            for (size_t offset = 0; offset < maximum; offset += (size_t)page) p[offset] = 2;
            report(small ? "anon_retouch_nohuge" : "anon_retouch_default", maximum, rep, maximum);
            if (munmap(mapping, maximum)) fail("munmap");
        }
    }
    /* pread goes through the resident tmpfs -> user buffer copy path. */
    const size_t file_sizes[] = {4096, 65536, 1048576, 4838400, 16777216};
    for (size_t k = 0; k < sizeof(file_sizes) / sizeof(file_sizes[0]); ++k) {
        size_t size = file_sizes[k];
        for (unsigned rep = 0; rep < (unsigned)repeats; ++rep) {
            char path[4096];
            int n = snprintf(path, sizeof(path), "%s/data-XXXXXX", argv[1]);
            if (n < 0 || (size_t)n >= sizeof(path)) return 2;
            int fd = mkstemp(path);
            if (fd < 0) fail("mkstemp");
            start(); transfer(fd, src, size, 0); report("tmpfs_fresh_write", size, rep, size);
            start(); transfer(fd, src, size, 0); report("tmpfs_rewrite", size, rep, size);
            start(); transfer(fd, dst, size, 1); report("tmpfs_read_copy_to_user", size, rep, size);
            if (memcmp(src, dst, size)) fail("read verification");
            if (ftruncate(fd, 0) || lseek(fd, 0, SEEK_SET) < 0) fail("truncate");
            FILE *file = fdopen(fd, "wb");
            if (!file) fail("fdopen");
            start();
            if (fwrite(src, 1, size, file) != size) fail("fwrite");
            if (fclose(file)) fail("fclose");
            report("tmpfs_fwrite_close_fresh", size, rep, size);
            if (unlink(path)) fail("unlink");
        }
    }
    free(dst); free(src);
    return 0;
}
