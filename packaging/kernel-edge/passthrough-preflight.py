#!/usr/bin/env python3
"""Offline DT resource gate for a uhd4 native HDMI passthrough experiment.

Requires dtc's fdtget. Never opens hardware or qualifies runtime support.
Supply the kernel tree that built the DTB: split VCBUS reservations come from
its driver, since the capture node still describes the whole parent window.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def split_regions(source):
    text = (source / 'drivers/media/platform/amlogic/t7-hdmirx/t7-vdin-test.c').read_text()
    function = text.split('static int t7_vdin_map_regs(', 1)[1].split('\n}', 1)[0]
    table = function.split('regions[] = {', 1)[1].split('};', 1)[0]
    regions = [(int(a, 16), int(b, 16)) for a, b in
               re.findall(r'\{\s*(0x[\da-f]+),\s*(0x[\da-f]+)\s*\}', table)]
    if not regions or any(size <= 0 for _, size in regions):
        raise ValueError('Cannot identify split VCBUS reservations in supplied kernel')
    return regions


class DeviceTree:
    def __init__(self, path):
        self.path = str(path)
        self.properties = {}
        self.nodes = []
        self.walk('/')

    def get(self, node, prop, kind='s'):
        key = (node, prop, kind)
        if key not in self.properties:
            result = subprocess.run(['fdtget', '-t' + kind, self.path, node, prop],
                                    text=True, capture_output=True)
            # fdtget also fails for corrupt input; only absent properties are optional.
            if result.returncode and 'FDT_ERR_NOTFOUND' not in result.stderr:
                raise ValueError(result.stderr.strip())
            self.properties[key] = None if result.returncode else result.stdout.strip()
        return self.properties[key]

    def walk(self, node):
        self.nodes.append(node)
        children = subprocess.check_output(['fdtget', '-l', self.path, node], text=True)
        for child in children.splitlines():
            self.walk(node.rstrip('/') + '/' + child)

    def enabled(self, node):
        while True:
            if self.get(node, 'status') not in (None, 'okay', 'ok'):
                return False
            if node == '/':
                return True
            node = node.rsplit('/', 1)[0] or '/'

    def compatible(self, name):
        return [node for node in self.nodes
                if name in (self.get(node, 'compatible') or '').split()
                and self.enabled(node)]

    def has(self, node, prop):
        return self.get(node, prop, 'x') is not None

    def regions(self, node):
        parent = node.rsplit('/', 1)[0] or '/'
        # The audited display and capture resources are direct root children.
        # Reject other buses rather than silently ignoring address translation.
        if parent != '/' or self.get('/', '#address-cells', 'x') != '2' or \
                self.get('/', '#size-cells', 'x') != '2':
            raise ValueError('Expected root resources with two address/size cells')
        cells = [int(cell, 16) for cell in (self.get(node, 'reg', 'x') or '').split()]
        if not cells or len(cells) % 4:
            raise ValueError('Invalid resource cells: ' + node)
        return [(cells[i] << 32 | cells[i + 1], cells[i + 2] << 32 | cells[i + 3])
                for i in range(0, len(cells), 4)]


def audit(tree, capture_regions):
    errors = []
    displays = tree.compatible('amlogic,t7-display')
    captures = tree.compatible('amlogic,t7-vdin-test')
    txs = tree.compatible('amlogic,t7-hdmi-tx')
    if len(displays) != 1 or len(captures) != 1:
        errors.append('Require one active native display and one VDIN capture owner')
    if tree.compatible('simple-framebuffer'):
        errors.append('Active simple-framebuffer conflicts with native display')
    for display in displays:
        if not tree.has(display, 'amlogic,video-planes'):
            errors.append('Native display has no video planes')
    if len(txs) != 1 or not tree.has(txs[0], 'amlogic,enc2-modeset'):
        errors.append('Require native ENC2 HDMI TX')
    cards = [n for n in tree.compatible('amlogic,axg-sound-card')
             if tree.get(n, 'model') == 'VIM4HDMITX']
    if len(cards) != 1:
        errors.append('Require the independent HDMI TX ASoC card')
    gpus = [n for n in tree.nodes if tree.enabled(n)
            and 'mali' in (tree.get(n, 'compatible') or '')]
    if len(gpus) > 1:
        errors.append('Multiple active Mali GPU nodes; Panfrost/kbase must be exclusive')
    effective = []
    for capture in captures:
        regions = tree.regions(capture)
        if tree.has(capture, 'amlogic,split-vcbus'):
            if regions != [(0xff000000, 0x40000)]:
                errors.append('Split VCBUS parent window differs from driver contract')
            regions = capture_regions
        effective.extend(regions)
    for display in displays:
        for start, size in tree.regions(display):
            for capture_start, capture_size in effective:
                if start < capture_start + capture_size and capture_start < start + size:
                    errors.append(f'Display/VDIN MMIO overlap at {max(start, capture_start):#x}')
    return {'offline_resource_gate': not errors, 'errors': errors,
            'display': displays, 'capture': captures, 'tx': txs, 'gpu': gpus,
            'capture_reservations': [{'start': hex(a), 'size': hex(b)} for a, b in effective],
            'runtime_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel-source', type=Path, required=True)
    parser.add_argument('--dtb', type=Path, required=True)
    args = parser.parse_args()
    try:
        report = audit(DeviceTree(args.dtb), split_regions(args.kernel_source))
        report['dtb_sha256'] = hashlib.sha256(args.dtb.read_bytes()).hexdigest()
        report['kernel_revision'] = subprocess.check_output(
            ['git', '-C', str(args.kernel_source), 'rev-parse', 'HEAD'], text=True).strip()
        report['kernel_dirty'] = bool(subprocess.check_output(
            ['git', '-C', str(args.kernel_source), 'status', '--porcelain'], text=True).strip())
    except (ValueError, IndexError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(2, f'Preflight failed: {error}\n')
    print(json.dumps(report, indent=2))
    return 0 if report['offline_resource_gate'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
