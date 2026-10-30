#!/usr/bin/env python3
"""Exclusive board GPU capability/benchmark window; never changes services or HID.

Usage: gpu-compare.py {vendor,system,private} --runtime /opt/vim4-mesa-26.2.6
       --output NEW_DIRECTORY [--seconds 20] [--capabilities-only]
Tools come from the private archive; system mode selects system libraries only.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import time

GPU_ENV = ('LD_LIBRARY_PATH', 'LD_PRELOAD', 'LIBGL_DRIVERS_PATH', 'EGL_PLATFORM',
           '__EGL_VENDOR_LIBRARY_FILENAMES', 'VK_DRIVER_FILES', 'VK_ICD_FILENAMES',
           'OCL_ICD_VENDORS', 'RUSTICL_ENABLE', 'PAN_I_WANT_A_BROKEN_VULKAN_DRIVER',
           'GALLIUM_DRIVER', 'MESA_LOADER_DRIVER_OVERRIDE', 'GPU_UNROLL128')


def environment(mode, runtime):
    env = {k: v for k, v in os.environ.items() if k not in GPU_ENV}
    env['EGL_PLATFORM'] = 'surfaceless'
    env['LD_LIBRARY_PATH'] = '/usr/lib/aarch64-linux-gnu:/lib/aarch64-linux-gnu:' + str(runtime / 'lib')
    if mode == 'private':
        env.update(LD_LIBRARY_PATH=str(runtime / 'lib'),
                   LIBGL_DRIVERS_PATH=str(runtime / 'lib/dri'),
                   __EGL_VENDOR_LIBRARY_FILENAMES=str(runtime / 'share/glvnd/egl_vendor.d/50_mesa.json'),
                   VK_DRIVER_FILES=str(runtime / 'share/vulkan/icd.d/panfrost_icd.aarch64.json'),
                   OCL_ICD_VENDORS=str(runtime / 'etc/OpenCL/vendors'),
                   RUSTICL_ENABLE='panfrost', PAN_I_WANT_A_BROKEN_VULKAN_DRIVER='1',
                   CLANG_RESOURCE_DIR=str(runtime / 'share/clang/19'))
    elif mode == 'vendor':
        if not platform.release().startswith('5.15.'):
            raise ValueError('Vendor libmali requires the 5.15 kbase kernel')
        env.update(LD_PRELOAD='/usr/lib/vim4-kvm/gpu/libMali.so',
                   VK_DRIVER_FILES='/usr/lib/vim4-kvm/gpu/mali.json')
        # ocl-icd uses a directory containing the selected vendor library path.
    return env


def bounded(command, env, timeout):
    start = time.monotonic()
    with subprocess.Popen(command, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, start_new_session=True, text=True) as proc:
        try:
            output, _ = proc.communicate(timeout=timeout)
            return {'command': command, 'exit': proc.returncode, 'seconds': time.monotonic()-start, 'output': output}
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                output, _ = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                output, _ = proc.communicate()
            return {'command': command, 'timeout': True, 'output': output}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('vendor', 'system', 'private'))
    parser.add_argument('--runtime', type=Path, default=Path('/opt/vim4-mesa-26.2.6'))
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--seconds', type=int, choices=range(1, 61), default=20)
    parser.add_argument('--capabilities-only', action='store_true')
    parser.add_argument('--probe', type=Path, help='Override the versioned GLES probe binary')
    parser.add_argument('--gbm-device', type=Path, help='Use GBM with a fixed-size offscreen FBO')
    parser.add_argument('--unroll128', action='store_true', help='Explicitly unroll the diagnostic shader')
    args = parser.parse_args()
    env = environment(args.mode, args.runtime)
    if args.unroll128:
        env['GPU_UNROLL128'] = '1'
    args.output.mkdir(parents=True, exist_ok=False)
    if args.mode == 'vendor':
        icd = args.output.resolve() / 'opencl'
        icd.mkdir()
        (icd / 'mali.icd').write_text('/usr/lib/vim4-kvm/gpu/libMali.so\n')
        env['OCL_ICD_VENDORS'] = str(icd)
    # Load the same utility binary through the system loader. Its RUNPATH makes
    # bundled dependencies available; API dispatch is controlled above.
    probe = [str(args.probe or args.runtime / 'bin/gpu-probe'), str(0 if args.capabilities_only else args.seconds)]
    if args.gbm_device:
        probe.append(str(args.gbm_device))
    commands = [tuple(probe),
                (str(args.runtime / 'bin/vulkaninfo'),), (str(args.runtime / 'bin/clinfo'),)]
    if not args.capabilities_only:
        commands.append((str(args.runtime / 'bin/clpeak'),))
        commands.append((str(args.runtime / 'bin/vkmark'), '--data-dir', str(args.runtime / 'share/vkmark'), '--winsys-dir', str(args.runtime / 'lib/vkmark'), '--size', '512x512', '--benchmark', ':duration=2'))
    results = [bounded(list(command), env, 40 if i < 3 else 120) for i, command in enumerate(commands)]
    if 'Mali-G52' not in results[0]['output']:
        results[0]['error'] = 'Expected Mali-G52 hardware renderer'
    for index in (1, 2):
        if 'mali' not in results[index]['output'].lower():
            results[index]['error'] = 'No Mali device reported; missing capability is not a pass'
    result = {'kernel': platform.release(), 'mode': args.mode,
              'environment': {k: env[k] for k in (*GPU_ENV, 'CLANG_RESOURCE_DIR') if k in env}, 'results': results}
    (args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(args.output / 'result.json')
    return int(any(r.get('timeout') or r.get('exit') or r.get('error') for r in results))


if __name__ == '__main__':
    raise SystemExit(main())
