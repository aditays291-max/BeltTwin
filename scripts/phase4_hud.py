"""Compact history browser, raw camera trend and selectable 24-channel scans."""
import omni.ui as ui
from phase3_hud import Phase3HUD
from phase2_hud import label, CYAN, MUTED, BACKGROUND
from splice_tracker import SPLICES


class Phase4HUD(Phase3HUD):
    def __init__(self, window, store, history):
        self._ready = False
        self.history = history
        self.active_splice = 'S01'
        self.live_splice = 'S01'
        self.follow_live = True
        self.mode = 'history'
        self.selected_index = -1
        super().__init__(window, store)
        self.subtitle.text = 'INSPECTION MEMORY / PHASE 4'
        self.counter.text = 'RUN INSPECTIONS: 0'
        self.baseline_frame = window.get_frame('BeltTwinFingerprints')
        self.history_frame = window.get_frame('BeltTwinHistory')
        self.trend_bars, self.trend_spaces, self.trend_labels = [], [], []
        with window.get_frame('BeltTwinHistoryControls'):
            with ui.Placer(offset_x=338, offset_y=432, draggable=False):
                with ui.HStack(width=570, height=30, spacing=4):
                    ui.Button('Baseline', width=68, clicked_fn=lambda: self.set_mode('baseline'))
                    ui.Button('History', width=68, clicked_fn=lambda: self.set_mode('history'))
                    for splice in SPLICES:
                        ui.Button(splice, width=34, clicked_fn=lambda s=splice: self.select_splice(s))
                    self.live_button = ui.Button('Live: ON', width=66, clicked_fn=self.toggle_live)
                    ui.Button('< Scan', width=64, clicked_fn=lambda: self.browse(-1))
                    ui.Button('Scan >', width=64, clicked_fn=lambda: self.browse(1))
        with self.history_frame:
            with ui.Placer(offset_x=338, offset_y=470, draggable=False):
                with ui.ZStack(width=570, height=204):
                    ui.Rectangle(style={'background_color': BACKGROUND, 'border_radius': 8})
                    with ui.Placer(offset_x=14, offset_y=10, draggable=False):
                        with ui.HStack(width=540, spacing=16):
                            with ui.VStack(width=300, spacing=2):
                                self.history_title = label('INSPECTION HISTORY', 21, 16, CYAN)
                                self.overview = label('', 18, 11, MUTED)
                                label('SEQ / INSPECTION / CAMERA / PROFILE mm / TENSION', 18, 9, MUTED)
                                self.history_rows = [label('--', 18, 11) for _ in range(4)]
                                self.storage = label('', 34, 10, MUTED)
                            with ui.VStack(width=224, spacing=2):
                                label('CAMERA RAW SCORE', 21, 14, CYAN)
                                label('Scale 0-1 / last 8 inspections', 16, 10, MUTED)
                                with ui.HStack(height=62, spacing=3):
                                    for _ in range(8):
                                        with ui.VStack(width=24, height=62, spacing=0):
                                            self.trend_spaces.append(ui.Spacer(height=44))
                                            self.trend_bars.append(ui.Rectangle(height=1, style={'background_color': CYAN}))
                                            self.trend_labels.append(label('--', 17, 9, MUTED))
                                self.selection = label('', 18, 11, CYAN)
                                self.first_latest = label('', 35, 11)
                                self.baseline_summary = label('', 18, 10, MUTED)
        self._ready = True
        self.refresh_view()

    def set_mode(self, mode):
        self.mode = mode
        self.refresh_view()

    def select_splice(self, splice):
        self.active_splice = splice
        self.follow_live = False
        self.selected_index = -1
        self.refresh_view()

    def toggle_live(self):
        self.follow_live = not self.follow_live
        if self.follow_live:
            self.active_splice = self.live_splice
            self.selected_index = -1
        self.refresh_view()

    def browse(self, direction):
        rows = self.history.records(self.active_splice)
        self.mode = 'history'
        self.follow_live = False
        index = self.selected_index if self.selected_index >= 0 else len(rows) - 1
        self.selected_index = max(0, min(len(rows) - 1, index + direction)) if rows else -1
        self.refresh_view()

    def on_inspection(self, record, count):
        # Keep the live Phase 2 sensor card independent of the history selection.
        from phase2_hud import Phase2HUD
        Phase2HUD.on_inspection(self, record, count)
        self.counter.text = f'RUN INSPECTIONS: {count}'
        self.live_splice = record['splice_id']
        if self.follow_live:
            self.active_splice = self.live_splice
            self.selected_index = -1
        self.refresh_view()

    def on_complete(self, record):
        super().on_complete(record)
        self.refresh_view()

    def on_history_saved(self, record):
        if self.follow_live:
            self.active_splice = record['splice_id']
            self.selected_index = -1
        self.refresh_view()

    def show_fingerprint(self, fp, notice):
        if not self._ready:
            super().show_fingerprint(fp, notice)
        else:
            self.refresh_view(notice if fp['splice_id'] == self.active_splice else 'BASELINE STORED')

    def refresh_view(self, notice='BASELINE STORED / PRESERVED'):
        if not self._ready:
            return
        self.baseline_frame.visible = self.mode == 'baseline'
        self.history_frame.visible = self.mode == 'history'
        self.live_button.text = 'Live: ON' if self.follow_live else 'Live: OFF'
        fp = self.store.get(self.active_splice)
        if fp:
            Phase3HUD.show_fingerprint(self, fp, notice)
        elif self.mode == 'baseline':
            self.refresh()
            self.detail_title.text = f'DIGITAL FINGERPRINT / {self.active_splice}'
            self.detail.text = 'Waiting for completed healthy scan'
            self.notice.text = 'WAITING FOR BASELINE'
            self.show_mfl([0.0] * 24, 'No stored baseline for this splice', f'MFL BASELINE - {self.active_splice} / EMPTY')
        rows = self.history.records(self.active_splice)
        self.history_title.text = f'HISTORY / {self.active_splice} / {len(rows)} INSPECTIONS'
        self.overview.text = '  '.join(f'{s}: {n}' for s, n in self.history.counts().items())
        index = self.selected_index if self.selected_index >= 0 else len(rows) - 1
        index = min(index, len(rows) - 1)
        selected = rows[index] if rows else None
        end = max(4, index + 1)
        visible = rows[max(0, end - 4):end]
        for widget, record in zip(self.history_rows, visible + [None] * (4 - len(visible))):
            widget.text = (f'{">" if record is selected else " "} #{record["inspection_sequence"]}  '
                           f'{record["inspection_id"]}  {record["camera"]["score"]:.3f}  '
                           f'{record["profile"]["deviation"]:.4f}  {record["tension"]["score"]:.3f}') if record else '--'
        self.storage.text = ('Stored: YES | 24-channel MFL: YES\nCamera / profile / tension history: YES'
                             if rows else 'HISTORY: EMPTY / awaiting completed inspection')
        self.first_latest.text = (f'First: {rows[0]["inspection_id"]}\nLatest: {rows[-1]["inspection_id"]}'
                                  if rows else 'First: --\nLatest: --')
        self.baseline_summary.text = 'Baseline: HEALTHY / stored separately' if fp else 'Baseline: waiting'
        self.selection.text = f'Selected #{selected["inspection_sequence"]} / t={selected["timestamp_s"]:.2f}s' if selected else 'Selected: --'
        trend = rows[-8:]
        for i in range(8):
            record = trend[i] if i < len(trend) else None
            height = record['camera']['score'] * 44 if record else 0
            self.trend_spaces[i].height = ui.Pixel(44 - height)
            self.trend_bars[i].height = ui.Pixel(height)
            self.trend_labels[i].text = str(record['inspection_sequence']) if record else '--'
            self.trend_bars[i].tooltip = f'Camera {record["camera"]["score"]:.3f}' if record else ''
        if self.mode == 'history':
            if selected:
                self.show_mfl(selected['mfl']['channels'],
                              f'{selected["inspection_id"]} / SEQUENCE {selected["inspection_sequence"]} / t={selected["timestamp_s"]:.2f}s',
                              f'MFL HISTORY - {self.active_splice} / 24 CHANNELS')
            else:
                self.show_mfl([0.0] * 24, 'No stored inspection selected', f'MFL HISTORY - {self.active_splice} / EMPTY')
