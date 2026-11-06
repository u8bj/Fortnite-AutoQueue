"""Fortnite Auto-Queue: dark dashboard around the preserved game shortcuts."""
import copy
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import shutil
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

import cv2
from PIL import Image, ImageTk

import game_input
from instance_lock import InstanceLock
from runtime import QueueRuntime, screenshot_bgr
from settings import CUES, default_config, load_config, save_config
from vision import TemplateDetector


BASE = Path(__file__).resolve().parent
BG, PANEL, BORDER = '#10151f', '#1a2230', '#303e52'
FG, MUTED, ACCENT, GREEN, RED = '#edf3fa', '#9eafc5', '#64d5ec', '#72e2a7', '#ff8892'
STATE_TEXT = {'LOBBY': 'Checking lobby', 'MATCHMAKING': 'Matchmaking in progress',
              'DETECTING': 'Detecting game state · monitoring',
              'LOADING': 'Loading match', 'BATTLE_BUS': 'Battle Bus detected',
              'JUMPING': 'Sending Space', 'IN_MATCH': 'In match · monitoring only',
              'SPECTATING': 'Spectating · waiting for team', 'TEAM_ELIMINATED': 'Team elimination confirmed',
              'WAITING_FOR_RESULTS': 'Waiting for results', 'SKIP_XP': 'XP animation skipped',
              'MATCH_SUMMARY': 'Match summary', 'RETURNING_TO_LOBBY': 'Returning to lobby · waiting for lobby',
              'ERROR': 'Checking recognition · monitoring'}


def button(parent, text, command, accent=False, danger=False):
    color = '#225568' if accent else '#4c2935' if danger else '#29364a'
    return tk.Button(parent, text=text, command=command, bg=color, fg=FG, activebackground=BORDER,
                     activeforeground=FG, relief='flat', borderwidth=0, padx=15, pady=10,
                     font=('Segoe UI', 10, 'bold'), cursor='hand2')


def label(parent, text='', size=10, color=FG, bold=False, **kwargs):
    return tk.Label(parent, text=text, bg=parent.cget('bg'), fg=color,
                    font=('Segoe UI', size, 'bold' if bold else 'normal'), **kwargs)


class App:
    def __init__(self, root):
        self.root = root
        self.root.title('Fortnite Auto-Queue | Screen recognition')
        self.root.geometry('1000x820')
        self.root.minsize(900, 760)
        self.root.configure(bg=BG)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.events = queue.Queue()
        self.config, self.config_warning = load_config(BASE / 'config.json')
        self.capture_pending = False
        self.operation_id = 0
        self.closed = False
        self.manual_mode = tk.BooleanVar(value=False)
        self.debug_mode = tk.BooleanVar(value=self.config['debug'])
        self.active = tk.StringVar(value='INACTIVE')
        self.state = tk.StringVar(value='Ready for setup')
        self.counter = tk.StringVar(value='0')
        self.last_action = tk.StringVar(value='No input sent yet')
        self.error = tk.StringVar(value=self.config_warning)
        self.focus = tk.StringVar(value='Fortnite will be focused on start')
        self.evidence = tk.StringVar(value='Bus: waiting  ·  Jump: waiting  ·  Team elimination: unconfirmed')
        self.calibration = tk.StringVar()
        self._build_ui()
        self.runtime = QueueRuntime(BASE, self.config, self.events.put)
        self.refresh_calibration()
        self.root.after(100, self._drain_events)
        self.root.bind('<F8>', lambda event: self.stop())
        if self.config_warning:
            self.append_log(self.config_warning)
        self.append_log('Ready up with P; F8 stops even in game. Capture any missing templates first.')

    def _build_ui(self):
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('Treeview', background=PANEL, foreground=FG, fieldbackground=PANEL,
                        rowheight=27, borderwidth=0, font=('Segoe UI', 9))
        style.configure('Treeview.Heading', background=BORDER, foreground=FG, font=('Segoe UI', 9, 'bold'))
        style.map('Treeview', background=[('selected', '#285568')])
        outer = tk.Frame(self.root, bg=BG)
        outer.pack(fill='both', expand=True, padx=26, pady=22)
        header = tk.Frame(outer, bg=BG)
        header.pack(fill='x')
        label(header, 'FORTNITE AUTO-QUEUE', 22, bold=True).pack(side='left')
        self.badge = label(header, size=10, color=MUTED, bold=True, textvariable=self.active)
        self.badge.pack(side='right')
        label(outer, 'Battle Royale · Zero Build · Squads · Unranked · Fill', color=MUTED).pack(anchor='w', pady=(4, 16))
        panel = tk.Frame(outer, bg=PANEL, padx=20, pady=16)
        panel.pack(fill='x')
        line = tk.Frame(panel, bg=PANEL)
        line.pack(fill='x')
        left = tk.Frame(line, bg=PANEL)
        left.pack(side='left', fill='x', expand=True)
        label(left, 'CURRENT STATE', 9, MUTED, bold=True).pack(anchor='w')
        label(left, size=17, color=ACCENT, bold=True, textvariable=self.state,
              wraplength=700, justify='left').pack(anchor='w', pady=(7, 5))
        right = tk.Frame(line, bg=PANEL)
        right.pack(side='right', padx=(15, 0))
        label(right, size=25, bold=True, textvariable=self.counter).pack()
        label(right, 'Confirmed rounds', 9, MUTED).pack()
        label(panel, textvariable=self.focus, color=MUTED).pack(anchor='w', pady=(6, 3))
        label(panel, textvariable=self.evidence, color=MUTED, wraplength=880, justify='left').pack(anchor='w', pady=3)
        label(panel, textvariable=self.last_action, color=FG).pack(anchor='w', pady=(6, 0))
        label(outer, textvariable=self.error, color=RED, wraplength=930, justify='left').pack(anchor='w', fill='x', pady=(10, 4))
        tk.Checkbutton(outer, text='Mode checked: Zero Build · Squads · Unranked · Fill enabled',
                       variable=self.manual_mode, bg=BG, fg=FG, activebackground=BG,
                       activeforeground=FG, selectcolor=PANEL, font=('Segoe UI', 10)).pack(anchor='w', pady=3)
        bar = tk.Frame(outer, bg=BG)
        bar.pack(fill='x', pady=(10, 12))
        self.start_button = button(bar, 'START', self.start, accent=True)
        self.start_button.pack(side='left')
        button(bar, 'STOP', self.stop, danger=True).pack(side='left', padx=10)
        label(bar, 'F8 · EMERGENCY STOP', color=MUTED, bold=True).pack(side='left', padx=8)
        tk.Checkbutton(bar, text='Debug mode', variable=self.debug_mode, command=self.toggle_debug,
                       bg=BG, fg=MUTED, activebackground=BG, activeforeground=FG,
                       selectcolor=PANEL).pack(side='right')
        label(outer, textvariable=self.calibration, color=ACCENT, wraplength=930, justify='left').pack(anchor='w')
        controls = tk.Frame(outer, bg=BG)
        controls.pack(fill='x', pady=(10, 16))
        for text, command in [('Capture template', self.capture_dialog), ('Test recognition', self.test_recognition),
                              ('Settings', self.settings_dialog), ('Open logs', self.open_logs)]:
            button(controls, text, command).pack(side='left', padx=(0, 9))
        log_header = tk.Frame(outer, bg=BG)
        log_header.pack(fill='x')
        label(log_header, 'ACTIVITY', 9, MUTED, bold=True).pack(side='left')
        admin_text = 'Running as administrator' if game_input.is_admin() else 'Not elevated – start.bat recommended'
        label(log_header, admin_text, 9, MUTED).pack(side='right')
        logs = tk.Frame(outer, bg=PANEL)
        logs.pack(fill='both', expand=True, pady=(8, 10))
        self.log_text = tk.Text(logs, bg=PANEL, fg=MUTED, font=('Consolas', 10), height=10,
                                relief='flat', padx=12, pady=10, state='disabled', wrap='word')
        scrollbar = ttk.Scrollbar(logs, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.log_text.pack(fill='both', expand=True)
        label(outer, 'Screen recognition only. No gameplay input after jumping. Use at your own risk.',
              9, MUTED, wraplength=930).pack(anchor='w')

    def append_log(self, text):
        self.log_text.configure(state='normal')
        self.log_text.insert('end', text + '\n')
        lines = int(self.log_text.index('end-1c').split('.')[0])
        if lines > 400:
            self.log_text.delete('1.0', f'{lines - 400}.0')
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    def refresh_calibration(self):
        missing = set(self.runtime.missing_templates)
        active = [name for name, spec in self.config['templates'].items() if spec['enabled'] and name not in missing]
        pending = [CUES[name][0] for name in ('jump', 'team_eliminated', 'placement', 'match_summary', 'skip', 'return_lobby')
                   if not self.config['templates'][name]['enabled'] and
                   not (name == 'team_eliminated' and self.config.get('team_end_from_results'))]
        if not any(self.config['templates'][name]['enabled'] for name in ('glider', 'falling', 'in_match')):
            pending.insert(1, 'Jump confirmation')
        text = f'{len(active)}/{len(CUES)} templates available.'
        if missing:
            text += ' Missing or invalid file: ' + ', '.join(sorted(missing)) + '.'
        if pending:
            text += ' Still to configure: ' + ', '.join(pending) + '.'
        text += ' Mode check: ' + ('screen templates' if self.config['mode_check'] == 'templates' else 'manual confirmation on each start')
        if self.config.get('team_end_from_results'):
            text += ' · Team elimination: confirmed result screens'
        self.calibration.set(text)

    def start(self):
        if self.runtime.busy or self.capture_pending:
            return
        if self.config_warning:
            messagebox.showwarning('Check configuration', self.config_warning + '\nPlease review and save the settings first.', parent=self.root)
            return
        self.root.iconify()
        game_input.focus_game()
        if not self.runtime.start(mode_confirmed=self.manual_mode.get()):
            self.root.deiconify()

    def stop(self):
        self.runtime.stop()
        self.capture_pending = False
        self.operation_id = getattr(self, 'operation_id', 0) + 1

    def close(self):
        self.closed = True
        self.capture_pending = False
        self.operation_id += 1
        self.runtime.close()
        self.root.destroy()

    def _drain_events(self):
        if self.closed:
            return
        for _ in range(200):
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            kind = event['type']
            if kind == 'log':
                self.append_log(event['text'])
            elif kind == 'active':
                self.active.set('ACTIVE' if event['active'] else 'INACTIVE')
                self.badge.configure(fg=GREEN if event['active'] else MUTED)
                self.start_button.configure(state='disabled' if event['active'] else 'normal')
                if not event['active'] and self.runtime.engine.error:
                    self.error.set(self.runtime.engine.error)
                    self.root.deiconify()
            elif kind == 'error':
                self.error.set(event['text'])
                self.root.deiconify()
            elif kind == 'warning':
                self.error.set(event['text'])
            elif kind == 'status':
                text = STATE_TEXT.get(event['state'], event['state'])
                if event['state'] == 'LOBBY' and self.runtime.last_executed_action == 'ready':
                    text = 'P sent · waiting for matchmaking confirmation'
                self.state.set(text)
                self.counter.set(str(event['rounds']))
                self.last_action.set(event['last_action'] or 'No input sent yet')
                self.error.set(event['error'])
                self.focus.set('Fortnite has focus' if event['focused'] else 'Paused · Fortnite is not in the foreground')
                jump = event['state'] in ('IN_MATCH', 'SPECTATING')
                terminal = event['state'] in ('TEAM_ELIMINATED', 'WAITING_FOR_RESULTS', 'SKIP_XP', 'MATCH_SUMMARY', 'RETURNING_TO_LOBBY')
                sent = self.runtime.last_executed_action == 'jump'
                self.evidence.set(f"Bus: {'detected' if 'jump' in event['visible'] else 'waiting'}  ·  Space: {'sent' if sent else 'waiting'}  ·  Team elimination: {'confirmed' if terminal else 'unconfirmed'}")
            elif kind == 'test_result':
                if event.get('operation_id') != self.operation_id or not self.capture_pending:
                    continue
                self.capture_pending = False
                self.show_test_report(event['detections'], event['path'])
            elif kind == 'capture_frame':
                if self.capture_pending and event.get('operation_id') == self.operation_id:
                    self._select_crop(event['name'], event['frame'])
            elif kind == 'capture_error':
                self.capture_pending = False
                self.root.deiconify()
                messagebox.showerror('Capture failed', event['text'], parent=self.root)
        self.root.after(100, self._drain_events)

    def _idle_required(self):
        if self.runtime.busy or self.capture_pending:
            messagebox.showinfo('Stop first', 'Please stop Auto-Queue and finish the current operation first.', parent=self.root)
            return False
        return True

    def _rebuild_runtime(self):
        self.runtime.close()
        self.runtime = QueueRuntime(BASE, self.config, self.events.put)
        self.refresh_calibration()

    def toggle_debug(self):
        self.config['debug'] = self.debug_mode.get()
        if not self.config_warning:
            save_config(BASE / 'config.json', self.config)

    def open_logs(self):
        os.startfile(BASE / 'logs')

    def settings_dialog(self):
        if not self._idle_required():
            return
        window = tk.Toplevel(self.root)
        window.title('Settings and templates')
        window.geometry('920x770')
        window.configure(bg=BG)
        window.transient(self.root)
        window.grab_set()
        draft = copy.deepcopy(self.config)
        label(window, 'Capture and verify recognition templates', 17, bold=True).pack(anchor='w', padx=20, pady=(16, 5))
        label(window, 'Confidence and repeated matches reduce false detections. Exclude changing numbers and backgrounds.', color=MUTED, wraplength=860).pack(anchor='w', padx=20)
        tree = ttk.Treeview(window, columns=('active', 'score', 'hits'), height=10)
        tree.heading('#0', text='Cue')
        tree.heading('active', text='Enabled')
        tree.heading('score', text='Confidence')
        tree.heading('hits', text='Matches')
        tree.column('#0', width=410)
        for col in ('active', 'score', 'hits'):
            tree.column(col, width=110, anchor='center')
        tree.pack(fill='x', padx=20, pady=12)
        for name, (title, _, _) in CUES.items():
            spec = draft['templates'][name]
            tree.insert('', 'end', iid=name, text=title, values=('yes' if spec['enabled'] else 'no', spec['threshold'], spec['confirmations']))
        selected = {'name': 'lobby'}
        enabled = tk.BooleanVar()
        threshold, confirmations, roi = tk.StringVar(), tk.StringVar(), tk.StringVar()
        guide = tk.StringVar()
        edit = tk.Frame(window, bg=BG)
        edit.pack(fill='x', padx=20)
        tk.Checkbutton(edit, text='Template enabled', variable=enabled, bg=BG, fg=FG, selectcolor=PANEL,
                       activebackground=BG, activeforeground=FG).grid(row=0, column=0, sticky='w')
        for row, (title, var) in enumerate((('Confidence (0.5–1)', threshold), ('Confirmations (2–10)', confirmations),
                                          ('Search region x,y,width,height (0–1)', roi)), start=1):
            label(edit, title).grid(row=row, column=0, sticky='w', pady=4)
            tk.Entry(edit, textvariable=var, width=48, bg=PANEL, fg=FG, insertbackground=FG, relief='flat').grid(row=row, column=1, sticky='w', padx=12)
        label(window, textvariable=guide, color=MUTED, wraplength=860, justify='left').pack(anchor='w', padx=20, pady=8)

        def read_selected(event=None):
            if not tree.selection():
                return
            name = tree.selection()[0]
            selected['name'] = name
            spec = draft['templates'][name]
            enabled.set(spec['enabled'])
            threshold.set(str(spec['threshold']))
            confirmations.set(str(spec['confirmations']))
            roi.set(', '.join(str(v) for v in spec['roi']))
            guide.set(CUES[name][1])

        def apply_selected():
            try:
                name = selected['name']
                spec = draft['templates'][name]
                candidate = copy.deepcopy(draft)
                candidate['templates'][name].update(enabled=enabled.get(), threshold=float(threshold.get()),
                                                     confirmations=int(confirmations.get()), roi=[float(v.strip()) for v in roi.get().split(',')])
                from settings import validate_config
                validate_config(candidate)
                if enabled.get() and not (BASE / spec['file']).is_file():
                    raise ValueError('Template file missing. Please capture it first.')
                draft.update(candidate)
                tree.item(name, values=('yes' if enabled.get() else 'no', threshold.get(), confirmations.get()))
                return True
            except (ValueError, TypeError) as exc:
                messagebox.showerror('Invalid setting', str(exc), parent=window)
                return False

        button(edit, 'Apply cue settings', apply_selected).grid(row=0, column=1, sticky='w', padx=12)
        tree.bind('<<TreeviewSelect>>', read_selected)
        tree.selection_set('lobby')
        read_selected()
        global_bar = tk.Frame(window, bg=BG)
        global_bar.pack(fill='x', padx=20, pady=8)
        mode = tk.StringVar(value=draft['mode_check'])
        label(global_bar, 'Mode check').pack(side='left')
        ttk.Combobox(global_bar, textvariable=mode, values=('manual', 'templates'), state='readonly', width=14).pack(side='left', padx=8)
        poll = tk.StringVar(value=str(draft['poll_interval']))
        label(global_bar, 'Poll interval (s)').pack(side='left', padx=(12, 0))
        tk.Entry(global_bar, textvariable=poll, width=6, bg=PANEL, fg=FG, insertbackground=FG).pack(side='left', padx=8)
        label(window, 'manual = mode checkbox above · templates = all four mode cues required. Other timeouts are in config.json.',
              9, MUTED, wraplength=860).pack(anchor='w', padx=20)
        result_proof = tk.BooleanVar(value=draft.get('team_end_from_results', False))
        tk.Checkbutton(window, text='Infer team elimination from confirmed final result screens',
                       variable=result_proof, bg=BG, fg=FG, selectcolor=PANEL,
                       activebackground=BG, activeforeground=FG).pack(anchor='w', padx=20, pady=5)

        def save():
            if not apply_selected():
                return
            try:
                draft['mode_check'] = mode.get()
                draft['poll_interval'] = float(poll.get())
                draft['team_end_from_results'] = result_proof.get()
                save_config(BASE / 'config.json', draft)
            except (ValueError, OSError) as exc:
                messagebox.showerror('Save failed', str(exc), parent=window)
                return
            self.config = draft
            self.config_warning = ''
            self.error.set('')
            self._rebuild_runtime()
            window.destroy()

        button(window, 'Save settings', save, accent=True).pack(anchor='e', padx=20, pady=12)

    def test_recognition(self):
        if not self._idle_required():
            return
        self.capture_pending = True
        self.operation_id += 1
        operation_id = self.operation_id
        self.append_log('Recognition test starts in 5 seconds. Switch to the game screen to test. No input will be sent.')
        self.root.iconify()
        game_input.focus_game()

        def run():
            try:
                time.sleep(5)
                if not self.capture_pending or operation_id != self.operation_id or self.closed:
                    return
                detector = TemplateDetector(BASE, self.config)
                detections = {}
                count = max(spec['confirmations'] for spec in self.config['templates'].values())
                for _ in range(count):
                    frame = screenshot_bgr()
                    detections = detector.detect(frame)
                    time.sleep(.15)
                path = self.runtime.save_debug(frame, 'Manual recognition test', force=True)
                self.events.put({'type': 'test_result', 'detections': detections, 'path': path, 'operation_id': operation_id})
            except Exception as exc:
                self.events.put({'type': 'capture_error', 'text': f'Recognition test failed: {exc}'})

        threading.Thread(target=run, daemon=True).start()

    def show_test_report(self, detections, path):
        self.root.deiconify()
        window = tk.Toplevel(self.root)
        window.title('Recognition · Read-only test')
        window.geometry('800x680')
        window.configure(bg=BG)
        label(window, 'Recognition of the current screen', 17, bold=True).pack(anchor='w', padx=18, pady=18)
        tree = ttk.Treeview(window, columns=('score', 'result', 'hits'), height=21)
        for key, title in (('#0', 'Cue'), ('score', 'Confidence'), ('result', 'Result'), ('hits', 'Matches')):
            tree.heading(key, text=title)
            tree.column(key, width=330 if key == '#0' else 130)
        for name, (title, _, _) in CUES.items():
            detection = detections.get(name)
            spec = self.config['templates'][name]
            result = 'disabled / missing' if not spec['enabled'] else 'confirmed' if detection and detection.confirmed else 'unconfirmed'
            tree.insert('', 'end', text=title, values=(f'{detection.score:.3f}' if detection else '—', result,
                                                     f'{detection.streak}/{spec["confirmations"]}' if detection else '—'))
        tree.pack(fill='both', expand=True, padx=18)
        label(window, f'Debug screenshot: {path.name if path else "not saved"}. Results do not guarantee recognition in other scenes.',
              9, MUTED, wraplength=750).pack(anchor='w', padx=18, pady=14)

    def capture_dialog(self):
        if not self._idle_required():
            return
        window = tk.Toplevel(self.root)
        window.title('Capture template')
        window.geometry('720x370')
        window.configure(bg=BG)
        window.transient(self.root)
        window.grab_set()
        label(window, 'Capture a visible cue', 17, bold=True).pack(anchor='w', padx=22, pady=(20, 12))
        names = list(CUES)
        selection = tk.StringVar(value=CUES['jump'][0])
        combo = ttk.Combobox(window, textvariable=selection, values=[CUES[n][0] for n in names], state='readonly', width=55)
        combo.pack(anchor='w', padx=22)
        instruction = tk.StringVar(value=CUES['jump'][1])
        label(window, textvariable=instruction, color=ACCENT, wraplength=660, justify='left').pack(anchor='w', padx=22, pady=15)
        combo.bind('<<ComboboxSelected>>', lambda event: instruction.set(CUES[names[combo.current()]][1]))
        combo.current(names.index('jump'))
        label(window, 'After clicking: wait 5 seconds, then drag a box around the text.\nENTER saves · ESC cancels. No input is sent to the game during selection.',
              color=MUTED, wraplength=660, justify='left').pack(anchor='w', padx=22)

        def begin():
            name = names[combo.current()]
            window.destroy()
            self.capture_pending = True
            self.operation_id += 1
            operation_id = self.operation_id
            self.root.iconify()
            game_input.focus_game()

            def grab():
                try:
                    time.sleep(5)
                    if self.capture_pending and not self.closed and operation_id == self.operation_id:
                        self.events.put({'type': 'capture_frame', 'name': name, 'frame': screenshot_bgr(), 'operation_id': operation_id})
                except Exception as exc:
                    self.events.put({'type': 'capture_error', 'text': str(exc)})
            threading.Thread(target=grab, daemon=True).start()

        button(window, 'Capture in 5 seconds', begin, accent=True).pack(anchor='e', padx=22, pady=22)

    def _select_crop(self, name, frame):
        overlay = tk.Toplevel(self.root)
        overlay.overrideredirect(True)
        overlay.attributes('-topmost', True)
        height, width = frame.shape[:2]
        display_w, display_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        overlay.geometry(f'{display_w}x{display_h}+0+0')
        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).resize((display_w, display_h))
        photo = ImageTk.PhotoImage(image)
        canvas = tk.Canvas(overlay, width=display_w, height=display_h, highlightthickness=0, cursor='crosshair')
        canvas.pack(fill='both', expand=True)
        canvas.create_image(0, 0, anchor='nw', image=photo)
        canvas.image = photo
        canvas.create_rectangle(0, 0, display_w, 60, fill=BG, outline=BG)
        canvas.create_text(20, 17, anchor='nw', text=f'{CUES[name][0]}: Drag around text · ENTER saves · ESC cancels',
                           fill=FG, font=('Segoe UI', 14, 'bold'))
        selected = {'start': None, 'rect': None, 'box': None}

        def press(event):
            selected['start'] = (event.x, event.y)
            if selected['rect']:
                canvas.delete(selected['rect'])
            selected['rect'] = canvas.create_rectangle(event.x, event.y, event.x, event.y, outline=ACCENT, width=3)

        def drag(event):
            if selected['start']:
                x, y = selected['start']
                canvas.coords(selected['rect'], x, y, event.x, event.y)
                selected['box'] = (min(x, event.x), min(y, event.y), max(x, event.x), max(y, event.y))

        def cancel(event=None):
            self.capture_pending = False
            overlay.destroy()
            self.root.deiconify()

        def save(event=None):
            if not selected['box']:
                return
            x0, y0, x1, y1 = selected['box']
            x0, x1 = max(0, round(x0 * width / display_w)), min(width, round(x1 * width / display_w))
            y0, y1 = max(0, round(y0 * height / display_h)), min(height, round(y1 * height / display_h))
            if x1 - x0 < 12 or y1 - y0 < 6:
                return
            crop = frame[y0:y1, x0:x1]
            try:
                path = BASE / self.config['templates'][name]['file']
                path.parent.mkdir(exist_ok=True)
                if path.exists():
                    originals = BASE / 'templates' / 'originals'
                    originals.mkdir(exist_ok=True)
                    backup = originals / path.name
                    if not backup.exists():
                        shutil.copy2(path, backup)
                ok, data = cv2.imencode('.png', crop)
                if not ok:
                    raise OSError('Could not encode image')
                data.tofile(path)
                captures = BASE / 'tests' / 'captures'
                captures.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
                fixture = captures / f'{name}-{stamp}.png'
                cv2.imencode('.png', frame)[1].tofile(fixture)
                fixture.with_suffix('.json').write_text(json.dumps({
                    'expected': [name], 'source': 'supervised_capture',
                    'note': 'Calibration image; not independent of the template created from it.'
                }, ensure_ascii=False, indent=2), encoding='utf-8')
                spec = self.config['templates'][name]
                left, top = max(0, x0 - 80), max(0, y0 - 80)
                right, bottom = min(width, x1 + 80), min(height, y1 + 80)
                spec.update(enabled=True, reference_size=[width, height],
                            roi=[left / width, top / height, (right - left) / width, (bottom - top) / height])
                save_config(BASE / 'config.json', self.config)
                self.config_warning = ''
                self._rebuild_runtime()
                self.append_log(f'Template captured: {CUES[name][0]}. Use Test recognition before relying on it.')
            except (OSError, ValueError) as exc:
                messagebox.showerror('Save failed', str(exc), parent=overlay)
                return
            cancel()

        canvas.bind('<ButtonPress-1>', press)
        canvas.bind('<B1-Motion>', drag)
        overlay.bind('<Return>', save)
        overlay.bind('<Escape>', cancel)
        overlay.bind('<F8>', cancel)
        overlay.focus_force()


def main():
    # Keep screenshot coordinates and Tk selection coordinates in physical pixels.
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    lock = InstanceLock(BASE)
    if not lock.acquire():
        root.withdraw()
        messagebox.showinfo('Auto-Queue already running', 'Another instance is running or the project lock is unavailable. Use or close the existing instance.', parent=root)
        root.destroy()
        return
    try:
        App(root)
        root.mainloop()
    finally:
        lock.release()


if __name__ == '__main__':
    main()
