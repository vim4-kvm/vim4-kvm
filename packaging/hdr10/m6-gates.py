#!/usr/bin/env python3
"""M6-only screenshot-confirmed HDR setup, using board-window's MCP transport.

No fixed scroll sequence: each scroll requires foreground Settings/Displays,
and each toggle requires the visible HDR label and observed switch colour.
The runner supplies the existing MCP client, source EOTF reader and output dir.
"""
import json
from pathlib import Path
import subprocess
import time


class GateError(RuntimeError):
    pass


def find(screen, text, *, top=False):
    hits = [row for row in screen['items'] if text.lower() in row['text'].lower()
            and (not top or row['y'] < 25)]
    if not hits:
        raise GateError('Screenshot lacks ' + text)
    return hits[0]


def front_settings(screen):
    if (screen['width'], screen['height']) != (1920, 1080):
        raise GateError('M6 screenshot dimensions changed')
    find(screen, 'System Settings', top=True)


def chrome_front(screen):
    chrome = find(screen, 'Chrome', top=True)
    # r13 OCR places the left edge at 41.8px; the manually reviewed anchor
    # was 53px. Both describe this same 1920x1080 menu bar.
    if (screen['width'], screen['height']) != (1920, 1080) or not 35 <= chrome['x'] <= 65:
        raise GateError('Unqualified original M6 foreground')


def settings(screen):
    front_settings(screen)
    title = [row for row in screen['items'] if row['text'].lstrip('> ') == 'Displays' and row['x'] > 1200]
    if len(title) != 1:
        raise GateError('Displays window is not confirmed in foreground')
    find(screen, 'RTK UHD HDR')
    return title[0]


class M6:
    def __init__(self, client, source_hdr, observer, output):
        self.client, self.source_hdr = client, source_hdr
        self.observer, self.output = observer, Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.sequence = 0
        self.initial_hdr = None
        self.restore_needed = False

    def qualify(self, initial_hdr):
        # This window only knows how to return to its original Chrome window.
        # Reject a pre-existing Settings foreground without touching it.
        screen = self.screen()
        chrome_front(screen)
        self.initial_hdr = initial_hdr

    def hid(self, name, arguments=None):
        if self.initial_hdr is None:
            raise GateError('M6 was not qualified; no source actions allowed')
        # Establish responsibility before dispatch: an MCP failure can mean
        # the action happened but its reply was lost.
        self.restore_needed = True
        return self.client.call(name, arguments)

    def screen(self, xy=None):
        self.sequence += 1
        path = self.output / f'step-{self.sequence:03}.jpg'
        self.client.screenshot(path)
        command = [str(self.observer), str(path)]
        if xy: command.extend(map(str, xy))
        result = json.loads(subprocess.check_output(command, text=True))
        path.with_suffix('.json').write_text(json.dumps(result, indent=2))
        return result

    def click(self, xy):
        self.hid('mouse_move', {'coordinate': list(xy)})
        # HID failure is never retried. The caller's finally must reobserve.
        self.hid('left_click')

    def open(self):
        before = self.screen()
        if any('System Settings' in row['text'] and row['y'] < 25 for row in before['items']):
            self.displays(before)
            return
        chrome_front(before)
        self.click((27, 13))  # r13 Apple menu, qualified by the captured menu bar.
        menu = self.screen()
        item = find(menu, 'System Settings')
        if item['x'] > 250 or item['y'] > 160:
            raise GateError('System Settings menu item is not the Apple menu')
        self.click((round(item['x'] + item['w']/2), round(item['y'] + item['h']/2)))
        deadline = time.monotonic() + 8
        while True:
            current = self.screen()
            try:
                front_settings(current)
                break
            except GateError:
                if time.monotonic() >= deadline: raise
                time.sleep(.25)
        # Only observation is repeated while Settings launches. A failed
        # post-click screenshot must escape to recovery, never replay the click.
        self.displays(current)

    def displays(self, screen):
        front_settings(screen)
        try:
            settings(screen)
            return
        except GateError:
            choices = [r for r in screen['items'] if r['text'] == 'Displays' and 900 < r['x'] < 1200 and 200 < r['y'] < 800]
            if len(choices) != 1: raise GateError('Displays sidebar target is not visible')
            row = choices[0]
            self.click((round(row['x']+row['w']/2), round(row['y']+row['h']/2)))
            settings(self.screen())

    def toggle(self, enabled):
        if self.source_hdr() == enabled:
            return
        self.open()
        for _ in range(8):
            screen = self.screen()
            title = settings(screen)
            labels = [r for r in screen['items'] if 'High Dynamic Range' in r['text']]
            if labels: break
            # Confirmed right pane only; never scroll Chrome.
            self.hid('mouse_move', {'coordinate': [round(title['x']+300), 700]})
            self.hid('scroll', {'scroll_direction': 'down', 'scroll_amount': 2})
            settings(self.screen())
        else: raise GateError('HDR control did not become visible')
        label = labels[0]
        xy = (round(title['x'] + 366), round(label['y'] + label['h']/2))
        current = self.screen(xy)
        settings(current)
        find(current, 'High Dynamic Range')
        pixels = current['pixels']
        blue = sum(b > .6 and b > r + .25 for r, g, b in pixels) / max(1, len(pixels))
        gray = sum(.65 < r < .95 and abs(r-g) < .05 and abs(g-b) < .05 for r,g,b in pixels) / max(1,len(pixels))
        observed = True if blue > .2 else False if gray > .2 else None
        if observed is None or observed != self.source_hdr():
            raise GateError('HDR switch pixels and source EOTF disagree')
        self.click(xy)
        deadline = time.monotonic() + 15
        while self.source_hdr() != enabled:
            if time.monotonic() >= deadline: raise GateError('HDR EOTF transition timed out; no replay')
            time.sleep(.25)
        settings(self.screen())

    def close(self):
        screen = self.screen()
        if any(r['text']=='About This Mac' and r['x']<250 and r['y']<180 for r in screen['items']):
            self.hid('key', {'text':'Escape'})
            screen=self.screen()
        if any('System Settings' in r['text'] and r['y'] < 25 for r in screen['items']):
            front_settings(screen)
            search = find(screen, 'Search')
            if not 900 < search['x'] < 1300 or not 150 < search['y'] < 350:
                raise GateError('Settings close control geometry is not qualified')
            try:
                title = settings(screen)
                xy = (round(title['x'] - 299), round(title['y'] + title['h']/2))
            except GateError:
                # The verified General pane uses the same window header. OCR
                # includes its magnifying icon as "Q" in the saved r13 frame.
                if search['text'] != 'Q Search': raise GateError('Unknown Settings header')
                xy = (round(search['x'] + 6), round(search['y'] + search['h']/2 - 50))
            self.click(xy)
        find(self.screen(), 'Chrome', top=True)

    def restore(self):
        if not self.restore_needed: return
        self.toggle(self.initial_hdr)
        self.close()
        if self.source_hdr() != self.initial_hdr:
            raise GateError('M6 HDR was not restored to its saved state')
        self.restore_needed = False
