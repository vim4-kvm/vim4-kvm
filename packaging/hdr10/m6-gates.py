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
    # Vision sometimes merges the Apple icon and the Chrome menu headings
    # into one row (observed r14c). Qualify that whole menu, rather than
    # treating the icon's left edge as the Chrome word's position.
    text = chrome['text'].lstrip(' •\uf8ff')
    separate = text == 'Chrome' and 35 <= chrome['x'] <= 65
    prefix, headings, _ = text.partition('Chrome File Edit View ')
    # The Apple icon was also recognized as a single "L" in the captured
    # menu animation. Require the full adjacent Chrome headings, allowing
    # only that single icon position before them.
    merged = bool(headings) and len(prefix.strip()) <= 1 and -1 <= chrome['x'] <= 65
    # r14e's real menu is split after File, with the remaining headings
    # recognized as a separate adjacent row.
    split = (text == 'Chrome File' and -1 <= chrome['x'] <= 65
             and any(r['text'] == 'Edit View History' and 140 <= r['x'] <= 180
                     and r['y'] < 25 for r in screen['items']))
    if (screen['width'], screen['height']) != (1920, 1080) or not (separate or merged or split):
        raise GateError('Unqualified original M6 foreground')


def source_foreground(screen):
    try:
        chrome_front(screen)
        return 'Chrome'
    except GateError:
        row=find(screen,'Grok Bot',top=True)
        if (screen['width'],screen['height'])!=(1920,1080) or not 35<=row['x']<=90 or row['text']!='Grok Bot':
            raise GateError('Unknown M6 foreground')
        return 'Grok Bot'


def settings(screen):
    front_settings(screen)
    title = [row for row in screen['items'] if row['text'].lstrip('> •') == 'Displays' and row['x'] > 1200]
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
        self.initial_app = 'Chrome'
        self.restore_needed = False
        self.deadline = None

    def remaining(self, maximum):
        if self.deadline is None: return maximum
        remaining = self.deadline - time.monotonic()
        if remaining <= 0: raise GateError('M6 recovery deadline expired')
        return min(maximum, remaining)

    def read_source(self):
        if self.deadline is None: return self.source_hdr()
        return self.source_hdr(timeout=self.remaining(30))

    def qualify(self, initial_hdr):
        screen = self.screen()
        # User explicitly allowed the observed Grok Bot -> Chrome preparation
        # and requires restoring that original foreground at the end.
        self.initial_app=source_foreground(screen)
        self.initial_hdr = initial_hdr

    def activate_recent(self,target):
        expected={'Google Chrome':'Chrome','Grok Bot':'Grok Bot'}[target]
        if source_foreground(self.screen())==expected:return expected
        self.click((27,13))
        deadline=time.monotonic()+8
        while True:
            menu=self.screen()
            try:
                row=find(menu,'Recent Items')
                if row['x']>250 or not 25<row['y']<220:raise GateError('Unqualified Recent Items menu')
                break
            except GateError:
                if time.monotonic()>=deadline:raise
                time.sleep(self.remaining(.25))
        self.hid('mouse_move',{'coordinate':[round(row['x']+row['w']/2),round(row['y']+row['h']/2)]})
        deadline=time.monotonic()+8
        while True:
            menu=self.screen()
            choices=[r for r in menu['items'] if r['text'].lstrip('• ')==target and 250<r['x']<700 and 25<r['y']<950]
            if len(choices)==1:break
            if time.monotonic()>=deadline:raise GateError('Requested recent application is not visible')
            time.sleep(self.remaining(.25))
        row=choices[0]
        self.click((round(row['x']+row['w']/2),round(row['y']+row['h']/2)))
        deadline=time.monotonic()+8
        while True:
            try:
                if source_foreground(self.screen())==expected:return expected
            except GateError:pass
            if time.monotonic()>=deadline:raise GateError('Application foreground did not change')
            time.sleep(self.remaining(.25))

    def hid(self, name, arguments=None):
        if self.initial_hdr is None:
            raise GateError('M6 was not qualified; no source actions allowed')
        # Establish responsibility before dispatch: an MCP failure can mean
        # the action happened but its reply was lost.
        self.restore_needed = True
        self.remaining(30)
        if self.deadline is None: return self.client.call(name, arguments)
        return self.client.call(name, arguments, deadline=self.deadline)

    def screen(self, xy=None):
        self.sequence += 1
        path = self.output / f'step-{self.sequence:03}.jpg'
        self.remaining(30)
        if self.deadline is None: self.client.screenshot(path)
        else: self.client.screenshot(path, deadline=self.deadline)
        command = [str(self.observer), str(path)]
        if xy: command.extend(map(str, xy))
        timeout=None if self.deadline is None else self.remaining(30)
        result = json.loads(subprocess.check_output(command, text=True,timeout=timeout))
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
        # A stopped preparation can leave our Apple menu open. Reuse its
        # visible Settings entry; clicking the Apple icon again would close it.
        menu = before
        visible_menu = any('System Settings' in r['text'] and r['x'] < 250
                           and 25 < r['y'] < 160 for r in before['items'])
        if not visible_menu:
            self.click((27, 13))  # r13 Apple menu, qualified by the captured menu bar.
        deadline = time.monotonic() + 8
        while True:
            if not visible_menu: menu = self.screen()
            try:
                chrome_front(menu)
                item = find(menu, 'System Settings')
                break
            except GateError:
                if time.monotonic() >= deadline: raise
                time.sleep(self.remaining(.25))
        if item['x'] > 250 or item['y'] > 160:
            raise GateError('System Settings menu item is not the Apple menu')
        self.click((round(item['x'] + item['w']/2), round(item['y'] + item['h']/2)))
        deadline = time.monotonic() + 8
        while True:
            current = self.screen()
            try:
                front_settings(current)
                # The menu bar changes before Settings has painted its
                # sidebar. Do not decide where to click from that empty frame.
                find(current, 'Displays')
                break
            except GateError:
                if time.monotonic() >= deadline: raise
                time.sleep(self.remaining(.25))
        # Only observation is repeated while Settings launches. A failed
        # post-click screenshot must escape to recovery, never replay the click.
        self.displays(current)

    def displays(self, screen):
        front_settings(screen)
        try:
            settings(screen)
            return
        except GateError:
            choices = [r for r in screen['items'] if r['text'].lstrip('• ') == 'Displays' and 900 < r['x'] < 1200 and 200 < r['y'] < 800]
            if len(choices) != 1: raise GateError('Displays sidebar target is not visible')
            row = choices[0]
            self.click((round(row['x']+row['w']/2), round(row['y']+row['h']/2)))
            deadline = time.monotonic() + 8
            while True:
                current = self.screen()
                front_settings(current)
                try:
                    settings(current)
                    break
                except GateError:
                    if time.monotonic() >= deadline: raise
                    time.sleep(self.remaining(.25))

    def toggle(self, enabled):
        if self.read_source() == enabled:
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
        if observed is None or observed != self.read_source():
            raise GateError('HDR switch pixels and source EOTF disagree')
        self.click(xy)
        deadline = time.monotonic() + 15
        while self.read_source() != enabled:
            if time.monotonic() >= deadline: raise GateError('HDR EOTF transition timed out; no replay')
            time.sleep(self.remaining(.25))
        settings(self.screen())

    def close(self, expected='Chrome'):
        screen = self.screen()
        def apple_menu(current):
            return any(r['text'].lstrip('• ') == 'About This Mac' and r['x']<250
                       and r['y']<180 for r in current['items'])
        if apple_menu(screen):
            self.hid('key', {'text':'Escape'})
            deadline = time.monotonic() + 8
            while True:
                screen=self.screen()
                if not apple_menu(screen): break
                if time.monotonic() >= deadline: raise GateError('Apple menu did not close')
                time.sleep(self.remaining(.25))
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
        deadline = time.monotonic() + 8
        while True:
            current = self.screen()
            try:
                app=source_foreground(current)
                if expected is not None and app!=expected:raise GateError('Original foreground did not return')
                if apple_menu(current): raise GateError('Apple menu remains open')
                return app
            except GateError:
                if time.monotonic() >= deadline: raise
                time.sleep(self.remaining(.25))

    def restore(self, *, deadline=None):
        if not self.restore_needed: return
        self.deadline = deadline
        self.remaining(30)
        self.toggle(self.initial_hdr)
        app=self.close(expected=None if self.initial_app=='Grok Bot' else 'Chrome')
        if app!=self.initial_app:
            self.activate_recent('Grok Bot')
        if self.read_source() != self.initial_hdr:
            raise GateError('M6 HDR was not restored to its saved state')
        self.restore_needed = False
