"""Exercise probe outcomes with a fake TEEC service, not a firmware ABI model."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('cc'), 'C compiler required')
class HdcpProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        directory = Path(cls.temp.name)
        (directory / 'tee_client_api.h').write_text(r'''
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
typedef uint32_t TEEC_Result;
typedef struct { int unused; } TEEC_Context;
typedef struct { int unused; } TEEC_Session;
typedef struct { uint32_t a; uint16_t b, c; uint8_t d[8]; } TEEC_UUID;
typedef struct {
    uint32_t paramTypes;
    struct { struct { uint32_t a, b; } value; } params[4];
} TEEC_Operation;
#define TEEC_SUCCESS 0
#define TEEC_LOGIN_PUBLIC 0
#define TEEC_VALUE_INPUT 1
#define TEEC_NONE 0
#define TEEC_PARAM_TYPES(a,b,c,d) ((a) | ((b)<<4) | ((c)<<8) | ((d)<<12))
static TEEC_Result TEEC_InitializeContext(const char *n, TEEC_Context *c)
{ puts("initialize"); return 0; }
static TEEC_Result TEEC_OpenSession(TEEC_Context *c, TEEC_Session *s,
    const TEEC_UUID *u, uint32_t l, void *d, void *o, uint32_t *r)
{ puts("open"); *r = 4; return getenv("FAIL_OPEN") ? 0xffff000f : 0; }
static TEEC_Result TEEC_InvokeCommand(TEEC_Session *s, uint32_t command,
    TEEC_Operation *o, uint32_t *origin)
{
    const char *fail = getenv("FAIL_KEY");
    printf("invoke %u\n", o->params[0].value.a);
    *origin = 4;
    return fail && atoi(fail) == o->params[0].value.a ? 0xffff0008 : 0;
}
static void TEEC_CloseSession(TEEC_Session *s) { puts("close"); }
static void TEEC_FinalizeContext(TEEC_Context *c) { puts("finalize"); }
''')
        cls.binary = directory / 'probe'
        subprocess.run(['cc', '-I', str(directory),
                        str(ROOT / 'packaging/security-media/ta-session-probe.c'),
                        '-o', str(cls.binary)], check=True)

    def run_probe(self, *arguments, **env):
        return subprocess.run([str(self.binary), *arguments], env=env,
                              capture_output=True, text=True)

    def test_default_does_not_load_keys(self):
        result = self.run_probe()
        self.assertEqual(result.returncode, 0)
        self.assertNotIn('invoke', result.stdout)
        self.assertTrue(result.stdout.endswith('close\nfinalize\n'))

    def test_key_failures_are_not_hidden_by_session_success(self):
        for key in ('1', '2'):
            with self.subTest(key=key):
                result = self.run_probe('--load-tx-keys', FAIL_KEY=key)
                self.assertEqual(result.returncode, 1)
                self.assertIn('invoke 1', result.stdout)
                self.assertIn('invoke 2', result.stdout)
                self.assertTrue(result.stdout.endswith('close\nfinalize\n'))
        self.assertEqual(self.run_probe('--load-tx-keys').returncode, 0)

    def test_session_failure_does_not_invoke_or_close_invalid_session(self):
        result = self.run_probe('--load-tx-keys', FAIL_OPEN='1')
        self.assertEqual(result.returncode, 1)
        self.assertNotIn('invoke', result.stdout)
        self.assertNotIn('close', result.stdout)
        self.assertTrue(result.stdout.endswith('finalize\n'))

    def test_unknown_option_does_not_touch_tee(self):
        result = self.run_probe('--load-keys')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')


@unittest.skipUnless(shutil.which('cc'), 'C compiler required')
class ProvisionQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        directory = Path(cls.temp.name)
        source = directory / 'service.c'
        source.write_text(r'''
#include <stdint.h>
#include <stdlib.h>
int32_t key_provision_query(uint8_t *name, uint32_t length, uint32_t type,
                            uint32_t *storage, uint32_t *size)
{
    /* A failed provider can leave output arguments undefined. */
    *storage = 0x80000000;
    *size = 317;
    return getenv("FAIL_QUERY") ? (int32_t)0xffff0008 : 0;
}
''')
        cls.library = directory / 'service.so'
        cls.binary = directory / 'probe'
        subprocess.run(['cc', '-shared', '-fPIC', str(source),
                        '-o', str(cls.library)], check=True)
        subprocess.run(['cc', str(ROOT / 'packaging/security-media/provision-query.c'),
                        '-ldl', '-o', str(cls.binary)], check=True)

    def test_missing_objects_fail_without_reporting_stale_metadata(self):
        result = subprocess.run([str(self.binary), str(self.library)],
                                env={'FAIL_QUERY': '1'}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn('storage=', result.stdout)
        self.assertNotIn('size=', result.stdout)
        result = subprocess.run([str(self.binary), str(self.library)],
                                env={}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('storage=', result.stdout)
        self.assertIn('size=', result.stdout)

    def test_missing_library_fails(self):
        result = subprocess.run([str(self.binary), str(self.library) + '.missing'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')
