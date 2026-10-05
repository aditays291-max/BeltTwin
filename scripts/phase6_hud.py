"""Event-updated S03 trend above the existing baseline/current comparison."""
import omni.ui as ui
from phase5_hud import Phase5HUD, AMBER
from phase2_hud import label, CYAN, GREEN, MUTED, BACKGROUND
from degradation_scenario import trend_point

COLORS = {'NORMAL': GREEN, 'WATCH': CYAN, 'WARNING': AMBER, 'CRITICAL': 0xFF7777FF}


class Phase6HUD(Phase5HUD):
    def __init__(self, window, store, history):
        self._trend_ready = False
        self.trend = []
        super().__init__(window, store, history)
        self.subtitle.text = 'PHASE 6 - PROGRESSIVE DEGRADATION'
        self.subtitle.style = {'font_size': 10, 'color': CYAN}
        self.observation_note.text = 'Synthetic progression / original baseline preserved'
        self.trend_frame = window.get_frame('BeltTwinProgression')
        self.progression_bars, self.progression_spaces, self.progression_scores, self.progression_sequences = [], [], [], []
        with self.trend_frame:
            with ui.Placer(offset_x=338, offset_y=14, draggable=False):
                with ui.ZStack(width=570, height=190):
                    ui.Rectangle(style={'background_color': 0xFF241A12, 'border_radius': 8})
                    with ui.Placer(offset_x=14, offset_y=8, draggable=False):
                        with ui.VStack(width=540, spacing=2):
                            label('S03 / DEGRADATION TREND', 23, 18, CYAN)
                            self.trend_caption = label('Anomaly score 0-1 | Awaiting S03', 17, 11, MUTED)
                            with ui.HStack(height=104, spacing=10):
                                for i in range(6):
                                    with ui.VStack(width=80, spacing=0):
                                        self.progression_scores.append(label('--', 18, 13, CYAN))
                                        self.progression_spaces.append(ui.Spacer(height=55))
                                        self.progression_bars.append(ui.Rectangle(height=1, style={'background_color': GREEN}))
                                        self.progression_sequences.append(label(f'L{i} / pending', 16, 10, MUTED))
                                        label(f'LEVEL {i}', 14, 9, MUTED)
                            label('NORMAL <.20  ->  WATCH <.40  ->  WARNING <.70  ->  CRITICAL', 18, 10, AMBER)
                            label('Inspection sequence -> | Actual detector results / fixed 0-1 scale', 15, 10, MUTED)
        with window.get_frame('BeltTwinTrendButtons'):
            with ui.Placer(offset_x=178, offset_y=585, draggable=False):
                with ui.VStack(width=138, spacing=4):
                    ui.Button('S03 trend', height=30, clicked_fn=self.show_trend)
                    ui.Button('24-channel deviation', height=26, clicked_fn=self.show_channels)
        self._trend_ready = True

    def show_trend(self):
        self.select_splice('S03')
        self.set_mode('compare')
        self.trend_frame.visible = True

    def show_channels(self):
        self.select_splice('S03')
        self.set_mode('compare')
        self.trend_frame.visible = False

    def on_comparison(self, record, baseline, result):
        if record['splice_id'] == 'S03':
            point = trend_point(result)
            self.trend.append(point)
            # Each bar is a real result, never an independently generated curve.
            for i, item in enumerate(self.trend[-6:]):
                height = max(1, item['anomaly_score'] * 56)
                color = COLORS[item['severity']]
                self.progression_bars[i].height = ui.Pixel(height)
                self.progression_spaces[i].height = ui.Pixel(56 - height)
                self.progression_bars[i].style = {'background_color': color}
                self.progression_scores[i].text = f'{item["anomaly_score"]:.3f}'
                self.progression_sequences[i].text = f'Seq {item["inspection_sequence"]} / L{item["degradation_level"]}'
                self.progression_bars[i].tooltip = f'{item["inspection_id"]}: {item["severity"]}'
            self.trend_caption.text = f'Target S03 | {point["stage"]} | {point["inspection_id"]} | {len(self.trend)} inspections'
        super().on_comparison(record, baseline, result)

    def refresh_view(self, notice='BASELINE STORED / PRESERVED'):
        super().refresh_view(notice)
        if not self._trend_ready:
            return
        comparison = self.comparisons.get(self.active_splice)
        if self.mode == 'compare' and comparison and self.active_splice == 'S03':
            scenario = comparison[2]['synthetic_scenario']
            self.compare_title.text = f'S03 / {scenario["stage"]} / HEALTHY BASELINE -> CURRENT'
            self.history_context.text = 'Original healthy fingerprint | changing region: MFL09-MFL13'
            self.score_label.style = {'font_size': 21, 'color': COLORS[comparison[2]['severity']]}

