#define _POSIX_C_SOURCE 200809L
#include <stddef.h>
#include <nn_sdk.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static double now_ms(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return 1000.0 * t.tv_sec + t.tv_nsec / 1e6;
}

static unsigned char *read_input(const char *path, size_t *size) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    if (fseek(f, 0, SEEK_END)) { fclose(f); return NULL; }
    long n = ftell(f);
    if (n <= 0 || fseek(f, 0, SEEK_SET)) { fclose(f); return NULL; }
    unsigned char *data = malloc((size_t)n);
    if (!data || fread(data, 1, (size_t)n, f) != (size_t)n) {
        free(data); fclose(f); return NULL;
    }
    fclose(f);
    *size = (size_t)n;
    return data;
}

int main(int argc, char **argv) {
    if (argc < 4) {
        fprintf(stderr, "usage: probe MODEL INPUT.f32 ITERATIONS\n");
        return 2;
    }
    setvbuf(stdout, NULL, _IOLBF, 0);
    int count = atoi(argv[3]);
    if (count < 1 || count > 1000) return 2;
    size_t size = 0;
    unsigned char *input = read_input(argv[2], &size);
    if (!input) { perror("input"); return 1; }
    aml_config config = {0};
    config.typeSize = sizeof(config);
    config.path = argv[1];
    config.modelType = ADLA_LOADABLE;
    config.nbgType = NN_ADLA_FILE;
    config.hw_flag = AML_HW_NPU;
    config.timeout_ms = 3000;
    double start = now_ms();
    void *context = aml_module_create(&config);
    printf("create_ms=%.3f context=%s\n", now_ms() - start, context ? "ok" : "failed");
    if (!context) { free(input); return 1; }
    double sum = 0, low = 1e9, high = 0;
    int status = 0;
    for (int i = 0; i < count; ++i) {
        nn_input in = {0};
        in.typeSize = sizeof(in);
        in.input_type = BINARY_RAW_DATA;
        in.input = input;
        in.size = (int)size;
        start = now_ms();
        int rc = aml_module_input_set(context, &in);
        if (rc != 0) { fprintf(stderr, "input_set=%d\n", rc); status = 1; break; }
        aml_output_config_t output_config = {0};
        output_config.typeSize = sizeof(output_config);
        output_config.format = AML_OUTDATA_FLOAT32;
        nn_output *output = aml_module_output_get(context, output_config);
        double elapsed = now_ms() - start;
        if (!output || output->num == 0 || output->num > OUTPUT_MAX_NUM) {
            fprintf(stderr, "invalid output\n"); status = 1; break;
        }
        printf("iteration=%d elapsed_ms=%.9f\n", i, elapsed);
        {
            for (unsigned j = 0; j < output->num; ++j) {
                printf("output_%u bytes=%u format=%d\n", j, output->out[j].size, output->out[j].out_format);
                if (output->out[j].size % sizeof(float) || !output->out[j].buf) { status = 1; break; }
                char path[128];
                snprintf(path, sizeof(path), "iteration-%04d-output-%u.f32", i, j);
                FILE *f = fopen(path, "wb");
                if (!f || fwrite(output->out[j].buf, 1, output->out[j].size, f) != output->out[j].size) {
                    if (f) fclose(f);
                    status = 1; break;
                }
                fclose(f);
            }
            printf("first_set_and_infer_ms=%.3f\n", elapsed);
        }
        if (i > 0) {
            sum += elapsed;
            if (elapsed < low) low = elapsed;
            if (elapsed > high) high = elapsed;
        }
        if (status) break;
        for (unsigned j = 0; j < output->num; ++j) {
            const float *values = (const float *)output->out[j].buf;
            for (unsigned k = 0; k < output->out[j].size / sizeof(float); ++k) {
                if (!isfinite(values[k])) { status = 1; break; }
            }
        }
        if (status) { fprintf(stderr, "nonfinite output\n"); break; }
    }
    if (count > 1 && !status) printf("warm_iterations=%d mean_set_and_infer_ms=%.3f min_ms=%.3f max_ms=%.3f\n", count - 1, sum / (count - 1), low, high);
    start = now_ms();
    int rc = aml_module_destroy(context);
    printf("destroy_ms=%.3f rc=%d status=%d\n", now_ms() - start, rc, status);
    free(input);
    return status || rc != 0;
}
