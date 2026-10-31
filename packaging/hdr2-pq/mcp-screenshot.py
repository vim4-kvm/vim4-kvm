#!/usr/bin/env python3
"""Read-only MCP screenshot, with a fresh curl HTTP connection per RPC.

The caller must hold the board lock. Existing credentials stay in memory and
curl's stdin, never command arguments or files. No input tools are exposed.
"""
import argparse
import base64
import json
from pathlib import Path
import subprocess
import time


def rpc(url, key, method, params, serial):
    body = json.dumps(dict(jsonrpc='2.0', id=serial, method=method, params=params))
    config = '\n'.join([
        'url = ' + json.dumps(url),
        'header = ' + json.dumps('Authorization: Bearer ' + key),
        'header = "Content-Type: application/json"',
        'header = "Accept: application/json, text/event-stream"',
        'header = "MCP-Protocol-Version: 2025-11-25"',
        'data-binary = ' + json.dumps(body),
    ])
    started = time.monotonic()
    response = subprocess.run(
        ['curl', '--silent', '--show-error', '--max-time', '20', '--config', '-',
         '--write-out', '\n%{http_code}'],
        input=config.encode(), capture_output=True, check=True, timeout=25)
    data, status = response.stdout.rsplit(b'\n', 1)
    if status != b'200':
        raise RuntimeError(f'{method}: HTTP {status.decode()}')
    result = json.loads(data)
    if 'error' in result:
        raise RuntimeError(result['error'])
    print(method, status.decode(), round(time.monotonic() - started, 3), flush=True)
    return result['result']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ssh', default='vim4')
    parser.add_argument('--url', default='http://192.168.50.210:8080/api/mcp')
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Refusing to overwrite an existing screenshot')
    credentials = subprocess.check_output(
        ['ssh', args.ssh, 'cat /var/lib/one-kvm/mcp/credentials.json'], timeout=10)
    key = json.loads(credentials)['api_key']
    rpc(args.url, key, 'initialize', dict(
        protocolVersion='2025-11-25', capabilities={},
        clientInfo=dict(name='hdr2-readonly-probe', version='1')), 1)
    rpc(args.url, key, 'tools/list', {}, 2)
    result = rpc(args.url, key, 'tools/call', dict(name='screenshot', arguments={}), 3)
    if result.get('isError'):
        raise RuntimeError('MCP screenshot tool failed')
    for content in result.get('content', []):
        if content['type'] == 'image':
            args.output.write_bytes(base64.b64decode(content['data'], validate=True))
            print(args.output)
            return
    raise RuntimeError('MCP screenshot returned no image')


if __name__ == '__main__':
    main()
