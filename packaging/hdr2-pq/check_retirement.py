#!/usr/bin/env python3
"""Join allocator identities and normalized physical addresses, failing closed."""
import json
import re
import sys
from pathlib import Path


def check(lines):
    tickets, latest, jobs, blocked = {}, {}, set(), set()
    seen, submissions, generations, ended = 0, 0, set(), set()
    for line in lines:
        if 'LOST' in line.upper():
            raise ValueError('Lost trace events')
        counts = re.search(r'entries-in-buffer/entries-written:\s*(\d+)/(\d+)', line)
        if counts and counts[1] != counts[2]:
            raise ValueError('Trace ring overwritten; retirement not proven')
        dropped = re.match(r'\s*(?:overrun|commit overrun|dropped events):\s*(\d+)', line)
        if dropped and int(dropped[1]):
            raise ValueError('Per-CPU trace loss; retirement not proven')
        if not re.search(r'(t7_vdin_buffer|wave5_buffers_buffer):', line):
            continue
        seen += 1
        fields = dict(re.findall(r'(\w+)=(\S+)', line))
        if 'allocator' not in fields or 'phys' not in fields:
            raise ValueError('Unsupported identity trace; matching rebuilt modules required')
        event = {key: int(value) for key, value in fields.items() if key != 'allocator'}
        identity, phase = (fields['allocator'], event['phys']), event['phase']
        if 't7_vdin_buffer:' in line:
            gen, ticket = event['gen'], event['ticket']
            if phase == 6:
                if any(t['gen'] < gen and not t['retired'] for t in tickets.values()) or jobs:
                    raise ValueError('Old buffers or encoder jobs remain at new generation')
                generations.add(gen)
            elif phase == 8:
                blocked.add(gen)
            elif phase == 7:
                ended.add(gen)
            elif ticket:
                if phase == 0:
                    if gen not in generations or not event['phys'] or identity in jobs:
                        raise ValueError('Unknown epoch/export or DMA rearmed during encoding')
                    if ticket in tickets or (identity in latest and not tickets[latest[identity]]['retired']):
                        raise ValueError('Capture ticket reused before retirement')
                    tickets[ticket] = dict(gen=gen, identity=identity, done=False, retired=False,
                                           released=False, encoded=0)
                    latest[identity] = ticket
                elif phase == 5:
                    raise ValueError('Fault retained DMA; retirement not proven')
                elif ticket in tickets:
                    if phase == 1:
                        if tickets[ticket]['retired']:
                            raise ValueError('Capture completed after retirement')
                        tickets[ticket]['done'] = True
                    elif phase == 3:
                        if identity in jobs:
                            raise ValueError(f'Capture buffer retired while encoder still owns it: '
                                             f'identity={identity} ticket={tickets[ticket]} '
                                             f'event={line.strip()}')
                        tickets[ticket]['retired'] = True
                    elif phase == 4:
                        # buf_cleanup drops VDIN's reference, not the imported
                        # DMA-buf held by Wave5. Keep ownership outstanding
                        # until the real completion/cancellation event arrives.
                        tickets[ticket]['released'] = True
                        tickets[ticket]['retired'] = identity not in jobs
        elif phase == 0:
            if identity not in latest:
                raise ValueError('Encoder input lacks capture provenance')
            ticket = tickets[latest[identity]]
            if not ticket['done'] or ticket['retired'] or ticket['gen'] in blocked or identity in jobs:
                raise ValueError(f'Invalid encoder submission: identity={identity} ticket={ticket} '
                                 f'blocked={sorted(blocked)} event={line.strip()}')
            jobs.add(identity)
            submissions += 1
            ticket['encoded'] += 1
        elif phase == 1:
            if identity not in jobs:
                raise ValueError('Encoder completion lacks submission')
            jobs.remove(identity)
            if tickets[latest[identity]]['released']:
                tickets[latest[identity]]['retired'] = True
        elif phase == 2:
            jobs.discard(identity)
            if identity in latest and tickets[latest[identity]]['released']:
                tickets[latest[identity]]['retired'] = True
    if not seen or not tickets or not submissions or not generations or generations != ended:
        raise ValueError('Missing or incomplete generation trace')
    if jobs or any(not t['retired'] for t in tickets.values()):
        raise ValueError('Capture/encoder ownership outstanding at trace end')
    return {'generations': len(generations), 'tickets': len(tickets),
            'source_changes': len(blocked), 'encoder_submissions': submissions,
            'epochs': [dict(generation=gen,
                            armed=sum(t['gen'] == gen for t in tickets.values()),
                            completed=sum(t['gen'] == gen and t['done'] for t in tickets.values()),
                            retired=sum(t['gen'] == gen and t['retired'] for t in tickets.values()),
                            encoded=sum(t['encoded'] for t in tickets.values() if t['gen'] == gen))
                       for gen in sorted(generations)],
            'outstanding': 0, 'stale_encoder_submissions': 0}


if __name__ == '__main__':
    lines = Path(sys.argv[1]).read_text().splitlines()
    if not any(re.match(r'\s*overrun:', line) for line in lines):
        raise ValueError('Append per-CPU trace stats before checking retirement')
    result = check(lines)
    if result['generations'] < 2 or not result['source_changes']:
        raise ValueError('Cross-generation run requires source change and restart')
    print(json.dumps(result, indent=2))
