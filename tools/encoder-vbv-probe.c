/* SPDX-License-Identifier: MIT
 * Experiment-only VPU_EncOpen interposer. Build against the matching vendor
 * headers; never install globally. VBV_MS=0 observes without changing params.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "vpuapi.h"

RetCode VPU_EncOpen(EncHandle *handle, EncOpenParam *param)
{
    typedef RetCode (*Open)(EncHandle *, EncOpenParam *);
    Open next = (Open)dlsym(RTLD_NEXT, "VPU_EncOpen");
    if (!next) {
        void *lib = dlopen("libamvenc_api.so", RTLD_NOW | RTLD_NOLOAD);
        if (lib) next = (Open)dlsym(lib, "VPU_EncOpen");
    }
    const char *text = getenv("VBV_MS");
    char *end = NULL;
    long requested = text ? strtol(text, &end, 10) : 0;
    if (!next || !param || (text && (!*text || *end)) ||
        (requested != 0 && (requested < 10 || requested > 3000))) {
        fprintf(stderr, "VBV_PROBE invalid experiment setup\n");
        abort();
    }
    /* Refuse a different ABI/configuration instead of guessing an offset. */
    if (param->picWidth != 3840 || param->picHeight != 2160 ||
        param->frameRateInfo != 60 || param->rcEnable != 1 ||
        param->vbvBufferSize != 3000 || param->lowLatencyMode != 0) {
        fprintf(stderr, "VBV_PROBE unexpected ABI/config w=%d h=%d fps=%d rc=%d vbv=%d lowLatency=%d\n",
                param->picWidth, param->picHeight, param->frameRateInfo,
                param->rcEnable, param->vbvBufferSize, param->lowLatencyMode);
        abort();
    }
    EncOpenParam before = *param;
    if (requested) param->vbvBufferSize = (int)requested;
    unsigned changed = 0;
    for (size_t i = 0; i < sizeof(*param); i++) {
        if (((unsigned char *)&before)[i] == ((unsigned char *)param)[i]) continue;
        if (i < offsetof(EncOpenParam, vbvBufferSize) ||
            i >= offsetof(EncOpenParam, vbvBufferSize) + sizeof(param->vbvBufferSize)) abort();
        changed++;
    }
    fprintf(stderr, "VBV_PROBE before=3000 after=%d offset=%zu size=%zu changed_bytes=%u bitrate=%d codec=%d\n",
            param->vbvBufferSize, offsetof(EncOpenParam, vbvBufferSize),
            sizeof(*param), changed, param->bitRate, param->bitstreamFormat);
    RetCode result = next(handle, param);
    fprintf(stderr, "VBV_PROBE open_result=%d\n", result);
    return result;
}
