"""Exercise the real probe with a deterministic SDK substitute, without hardware."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SDK = r'''
#include <math.h>
#include <stdlib.h>
#define OUTPUT_MAX_NUM 3
#define ADLA_LOADABLE 0
#define NN_ADLA_FILE 0
#define AML_HW_NPU 0
#define AML_PROFILE_PERFORMANCE 0
#define BINARY_RAW_DATA 0
#define AML_OUTDATA_FLOAT32 0
typedef struct { int typeSize; const char *path;
 int modelType, nbgType, hw_flag, timeout_ms; } aml_config;
typedef struct { int typeSize, input_type; void *input; int size; } nn_input;
typedef struct { int typeSize, format; } aml_output_config_t;
typedef struct { unsigned size; int out_format; void *buf; } outBuf_t;
typedef struct { unsigned num; outBuf_t out[3]; } nn_output;
typedef struct { int profile_type; struct {
 unsigned long long inference_time_us, memory_usage_bytes;
 } profiling_data; } aml_profile_config_t;
static inline void *aml_module_create(aml_config *c) { return c; }
static inline int aml_module_input_set(void *c, nn_input *in) {
 (void)c; (void)in; return 0;
}
static inline nn_output *aml_module_output_get(void *c, aml_output_config_t cfg) {
 (void)c; (void)cfg;
 /* Keep elapsed above the host clock resolution without sleeping. */
 for (volatile int i = 0; i < 100000; ++i) { }
 static float data[4] = {1, 2, 3, 4};
 static nn_output out = {3, {{sizeof(data), 0, data},
 {sizeof(data), 0, data}, {sizeof(data), 0, data}}};
 if (getenv("NONFINITE")) data[2] = NAN;
 return &out;
}
static inline int aml_module_destroy(void *c) { (void)c; return 0; }
static inline int aml_util_enableProfile(void *c, aml_profile_config_t *p) {
 (void)c; (void)p; return 0;
}
static inline int aml_util_getProfileInfo(void *c, aml_profile_config_t *p) {
 (void)c; p->profiling_data.inference_time_us = 1; return 0;
}
static inline int aml_util_disableProfile(void *c, aml_profile_config_t *p) {
 (void)c; (void)p; return 0;
}
'''


@unittest.skipUnless(shutil.which('cc'), 'requires a C compiler')
class ProbeTimingTests(unittest.TestCase):
    def test_segments_preserve_outputs_and_reconcile_elapsed(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / 'nn_sdk.h').write_text(SDK)
            (root / 'input').write_bytes(b'input')
            probe = root / 'probe'
            compiled = subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                            '-I', name, str(ROOT / 'tools/npu-probe.c'),
                            '-o', str(probe)], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            outputs = []
            for mode in [[], ['--timing'], ['--profile', '--timing']]:
                target = root / str(len(outputs))
                target.mkdir()
                result = subprocess.run([str(probe), 'model', str(root / 'input'), '3',
                                         *mode], cwd=target, check=True, text=True,
                                        capture_output=True, timeout=5)
                outputs.append({p.name: p.read_bytes() for p in target.glob('*.f32')})
                lines = [line for line in result.stdout.splitlines()
                         if line.startswith('timing_iteration=')]
                self.assertEqual(len(lines), 3 if mode else 0)
                sdk = re.findall(r'^iteration=\d+ elapsed_ms=([\d.]+)', result.stdout, re.M)
                for i, line in enumerate(lines):
                    fields = dict(re.findall(r'(\w+)=([\d.]+)', line))
                    self.assertEqual(fields['sdk_ms'], sdk[i])
                    total = sum(float(fields[k + '_ms']) for k in
                                ['sdk', 'open', 'write', 'close', 'scan', 'other'])
                    self.assertAlmostEqual(total, float(fields['e2e_ms']), places=6)
                    self.assertGreaterEqual(float(fields['gap_ms']), 0)
            self.assertEqual(len(outputs[0]), 9)
            self.assertEqual(outputs[0], outputs[1])
            self.assertEqual(outputs[1], outputs[2])
            # Exercise the public runner, including its optional flag forwarding.
            (root / 'model').write_bytes(b'model')
            validated = subprocess.run([sys.executable, str(ROOT / 'tools/npu-validate.py'), 'run',
                            '--probe', str(probe), '--model', str(root / 'model'),
                            '--input', str(root / 'input'), '--iterations', '3',
                            '--model-sha256', hashlib.sha256(b'model').hexdigest(),
                            '--input-sha256', hashlib.sha256(b'input').hexdigest(),
                            '--output', str(root / 'validated'), '--timing'],
                           capture_output=True, text=True, timeout=5)
            self.assertEqual(validated.returncode, 0,
                             validated.stderr + (root / 'validated/probe.log').read_text())
            self.assertIn('timing_iteration=2', (root / 'validated/probe.log').read_text())
            report = json.loads((root / 'validated/result.json').read_text())
            self.assertEqual(len(report['outputs']), 9)
            self.assertEqual(len(report['stage_timings_ms']), 3)
            for options in [[], ['--timing']]:
                failed = subprocess.run([str(probe), 'model', str(root / 'input'), '3',
                                         *options], cwd=root, capture_output=True,
                                        env={**os.environ, 'NONFINITE': '1'}, timeout=5)
                self.assertNotEqual(failed.returncode, 0)
                self.assertIn(b'nonfinite output', failed.stderr)
            failed_output = root / 'failed-output'
            failed_output.mkdir()
            (failed_output / 'iteration-0000-output-0.f32').mkdir()
            failed = subprocess.run([str(probe), 'model', str(root / 'input'), '3',
                                     '--timing'], cwd=failed_output,
                                    capture_output=True, timeout=5)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn(b'status=1', failed.stdout)
