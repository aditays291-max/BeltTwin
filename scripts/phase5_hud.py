"""Phase 5 comparison view, retaining the Phase 4 baseline/history browser."""
import omni.ui as ui
from phase4_hud import Phase4HUD
from phase2_hud import label, CYAN, MUTED, GREEN, BACKGROUND
from splice_tracker import SPLICES

AMBER = 0xFF70CFFF


class Phase5HUD(Phase4HUD):
    def __init__(self, window, store, history):
        self._compare_ready = False
        self.comparisons = {}
        super().__init__(window, store, history)
        self.subtitle.text = 'PHASE 5 - COMPARE / ANOMALY'
        self.observation_note.text = 'Synthetic observations / fixed demonstration scenario'
        self.compare_frame = window.get_frame('BeltTwinCompare')
        with window.get_frame('BeltTwinCompareButton'):
            with ui.Placer(offset_x=18, offset_y=585, draggable=False):
                ui.Button('Compare / Live', width=150, height=30, clicked_fn=self.compare_live)
        with self.compare_frame:
            with ui.Placer(offset_x=338, offset_y=470, draggable=False):
                with ui.ZStack(width=570, height=204):
                    ui.Rectangle(style={'background_color': BACKGROUND, 'border_radius': 8})
                    with ui.Placer(offset_x=14, offset_y=10, draggable=False):
                        with ui.VStack(width=540, spacing=2):
                            self.compare_title = label('HEALTHY BASELINE -> CURRENT SCAN', 23, 16, CYAN)
                            self.compare_source = label('Awaiting completed comparison', 17, 11, MUTED)
                            with ui.HStack(height=118, spacing=14):
                                with ui.VStack(width=300, spacing=1):
                                    label('SENSOR          BASELINE          CURRENT', 17, 11, MUTED)
                                    self.value_rows = {name: label('--', 18, 12) for name in ('Camera', 'Profile', 'Tension', 'MFL')}
                                    self.history_context = label('', 18, 10, MUTED)
                                with ui.VStack(width=226, spacing=1):
                                    self.score_label = label('SCORE: --', 26, 21, CYAN)
                                    self.detection_label = label('AWAITING COMPARISON', 18, 12, CYAN)
                                    self.deviation_rows = {name: label('--', 16, 11) for name in ('mfl', 'camera', 'profile', 'tension')}
                            self.results_overview = label('', 19, 10, CYAN)
        self._compare_ready = True
        self.mode = 'compare'
        self.refresh_view()

    def compare_live(self):
        self.mode = 'compare'
        self.follow_live = True
        self.active_splice = self.live_splice
        self.refresh_view()

    def on_complete(self, record):
        super().on_complete(record)
        # The inherited Phase 2 panel labels its healthy demonstration NORMAL.
        # Here report raw observed values, without suggesting changed data is healthy.
        self.sensor_values['CAMERA'].text = f'{record["camera"]["score"]:.2f} / OBSERVED'
        self.sensor_values['MFL'].text = '24 channels / OBSERVED'
        self.sensor_values['PROFILE'].text = f'{record["profile"]["deviation"]:.3f} mm / OBSERVED'
        self.sensor_values['TENSION'].text = f'{record["tension"]["score"]:.2f} / OBSERVED'

    def on_comparison(self, record, baseline, result):
        self.comparisons[record['splice_id']] = (record, baseline, result)
        self.refresh_view()

    def update(self, distance, state):
        super().update(distance, state)
        if state == 'COMPLETE' and self.latest_record:
            comparison = self.comparisons.get(self.latest_record['splice_id'])
            if comparison:
                result = comparison[2]
                self.result.text = ('ANOMALY DETECTED / ' if result['severity'] != 'NORMAL' else 'ANOMALY SEVERITY: ') + result['severity']

    def refresh_view(self, notice='BASELINE STORED / PRESERVED'):
        super().refresh_view(notice)
        if not self._compare_ready:
            return
        self.compare_frame.visible = self.mode == 'compare'
        if self.mode != 'compare':
            for bar in self.bars:
                bar.style = {'background_color': CYAN}
            return
        self.compare_title.text = f'HEALTHY BASELINE -> CURRENT SCAN / {self.active_splice}'
        self.results_overview.text = ' | '.join(f'{s} {self.comparisons[s][2]["severity"] if s in self.comparisons else "--"}' for s in SPLICES)
        comparison = self.comparisons.get(self.active_splice)
        self.chart_title.text = f'MFL CHANNEL DEVIATION / {self.active_splice}'
        if comparison is None:
            self.compare_source.text = 'Awaiting completed comparison for this splice'
            self.score_label.text = 'SCORE: --'
            self.detection_label.text = 'AWAITING COMPARISON'
            for widget in list(self.value_rows.values()) + list(self.deviation_rows.values()):
                widget.text = '--'
            self.history_context.text = f'Stored history: {self.history.counts()[self.active_splice]} inspections'
            values = [0] * 24
            affected = []
            self.chart_record.text = 'No completed comparison selected'
            self.range_label.text = 'Normalized channel difference / scale 0-1'
        else:
            record, baseline, result = comparison
            self.compare_source.text = f'Baseline {result["baseline_source"]} (original) | Current {result["inspection_id"]}'
            self.score_label.text = f'{result["anomaly_score"]:.3f} / {result["severity"]}'
            self.score_label.style = {'font_size': 21, 'color': GREEN if result['severity'] == 'NORMAL' else AMBER}
            self.detection_label.text = 'ANOMALY DETECTED' if result['severity'] != 'NORMAL' else 'NORMAL / LOW DEVIATION'
            self.value_rows['Camera'].text = f'Camera          {baseline["camera"]["score"]:.3f}                 {record["camera"]["score"]:.3f}'
            self.value_rows['Profile'].text = f'Profile mm     {baseline["profile"]["deviation"]:.4f}               {record["profile"]["deviation"]:.4f}'
            self.value_rows['Tension'].text = f'Tension         {baseline["tension"]["score"]:.3f}                 {record["tension"]["score"]:.3f}'
            self.value_rows['MFL'].text = f'MFL              24 channels          {len(result["affected_channels"])} affected'
            self.history_context.text = f'History: {self.history.counts()[self.active_splice]} scans | baseline: original HEALTHY'
            for name, widget in self.deviation_rows.items():
                widget.text = f'{name.upper():8s}  {result[name+"_deviation"]:.3f} x {result["weights"][name]:.2f}'
            values = result['mfl_channel_deviations']
            affected = result['affected_channels']
            self.chart_record.text = f'{result["baseline_source"]} -> {result["inspection_id"]} | difference / fixed normalized scale 0-1'
            self.range_label.text = f'Max raw difference: {result["mfl_max_channel_deviation"]:.4f} at MFL{result["mfl_max_channel_index"]:02d} | highlighted: {len(affected)} channels'
        for i, value in enumerate(values):
            height = max(1, value * 56)
            self.bars[i].height = ui.Pixel(height)
            self.bar_spaces[i].height = ui.Pixel(56 - height)
            self.bars[i].style = {'background_color': AMBER if f'MFL{i+1:02d}' in affected else CYAN}
            self.bars[i].tooltip = f'MFL{i+1:02d} normalized deviation: {value:.4f}'
