"""Native event-updated health view; original baseline/history views remain available."""
import omni.ui as ui
from phase5_hud import Phase5HUD, AMBER
from phase2_hud import label, CYAN, GREEN, MUTED

COLORS = {'HEALTHY':GREEN, 'STABLE':CYAN, 'DEGRADING':AMBER,
          'AT RISK':0xFF66AAFF, 'CRITICAL':0xFF7777FF}
PANEL = 0xFF241A12


class Phase7HUD(Phase5HUD):
    def __init__(self, window, store, history):
        self._health_ready = False
        self.health_results = {}
        self.health_trend = []
        super().__init__(window, store, history)
        self.subtitle.text = 'PHASE 7 - SENSOR FUSION / HEALTH'
        self.observation_note.text = 'Deterministic evidence fusion / no ML or prediction'
        self.health_frame = window.get_frame('BeltTwinHealth')
        self.health_trend_frame = window.get_frame('BeltTwinHealthTrend')
        self.health_bars, self.health_spaces, self.health_values, self.health_sequences, self.anomaly_values = [], [], [], [], []
        with self.health_trend_frame:
            with ui.Placer(offset_x=338, offset_y=14, draggable=False):
                with ui.ZStack(width=570, height=190):
                    ui.Rectangle(style={'background_color':PANEL,'border_radius':8})
                    with ui.Placer(offset_x=14, offset_y=8, draggable=False):
                        with ui.VStack(width=540, spacing=2):
                            label('S03 / HEALTH TREND', 23, 18, CYAN)
                            self.health_caption = label('HEALTH SCORE / fixed scale 0-100 | awaiting S03',17,11,MUTED)
                            with ui.HStack(height=104, spacing=10):
                                for i in range(6):
                                    with ui.VStack(width=80, spacing=0):
                                        self.health_values.append(label('-- / 100',18,13,CYAN))
                                        self.health_spaces.append(ui.Spacer(height=55))
                                        self.health_bars.append(ui.Rectangle(height=1,style={'background_color':GREEN}))
                                        self.health_sequences.append(label('Seq --',16,10,MUTED))
                                        self.anomaly_values.append(label('Anomaly --',14,9,MUTED))
                            label('HEALTHY >=90 | STABLE >=75 | DEGRADING >=50 | AT RISK >=25',18,10,AMBER)
                            label('CRITICAL <25 | Inspection sequence -> | Actual calculated health',15,10,MUTED)
        with self.health_frame:
            with ui.Placer(offset_x=338, offset_y=470, draggable=False):
                with ui.ZStack(width=570,height=204):
                    ui.Rectangle(style={'background_color':PANEL,'border_radius':8})
                    with ui.Placer(offset_x=14, offset_y=8, draggable=False):
                        with ui.VStack(width=540,spacing=2):
                            self.health_title=label('BASELINE -> SCAN -> ANOMALY -> HISTORY -> HEALTH',23,13,CYAN)
                            self.health_source=label('Awaiting health evidence',17,11,MUTED)
                            with ui.HStack(height=120,spacing=12):
                                with ui.VStack(width=290,spacing=0):
                                    label('SENSOR EVIDENCE / NORMALIZED DEVIATION',17,10,MUTED)
                                    self.evidence_rows={name:label('--',16,11) for name in ('mfl','camera','profile','tension','trend','confidence')}
                                with ui.VStack(width=238,spacing=1):
                                    self.health_score_label=label('HEALTH: -- / 100',28,20,CYAN)
                                    self.health_state_label=label('STATE: --',20,16,CYAN)
                                    self.health_anomaly_label=label('CURRENT ANOMALY: --',18,11)
                                    self.health_direction_label=label('TREND: --',18,12)
                                    self.health_stage_label=label('STAGE: --',17,11,MUTED)
                            self.fusion_explanation=label('70% current condition + 30% historical condition',17,10,MUTED)
                            self.health_overview=label('',17,10,CYAN)
        with window.get_frame('BeltTwinHealthButton'):
            with ui.Placer(offset_x=178,offset_y=585,draggable=False):
                ui.Button('Health / Live',width=138,height=30,clicked_fn=self.health_live)
        self._health_ready=True
        self.mode='health'
        self.refresh_view()

    def health_live(self):
        self.mode='health'; self.follow_live=True; self.active_splice=self.live_splice
        self.refresh_view()

    def show_trend(self):
        self.select_splice('S03')
        self.set_mode('health')

    def on_health(self, result):
        self.health_results[result['splice_id']]=result
        if result['splice_id']=='S03':
            self.health_trend.append(result)
            for i,point in enumerate(self.health_trend[-6:]):
                height=max(1,point['health_score']/100*56)
                self.health_bars[i].height=ui.Pixel(height)
                self.health_spaces[i].height=ui.Pixel(56-height)
                self.health_bars[i].style={'background_color':COLORS[point['health_state']]}
                self.health_values[i].text=f'{point["health_score"]:.1f} / 100'
                self.health_sequences[i].text=f'Seq {point["inspection_sequence"]} / L{point["synthetic_scenario"]["level"]}'
                self.anomaly_values[i].text=f'Anomaly {point["current_anomaly_score"]:.3f}'
                self.health_bars[i].tooltip=point['explanation']
            self.health_caption.text=f'HEALTH SCORE / 0-100 | {result["inspection_id"]} | {result["trend_direction"]}'
        self.refresh_view()

    def refresh_view(self, notice='BASELINE STORED / PRESERVED'):
        super().refresh_view(notice)
        if not self._health_ready:
            return
        self.health_frame.visible=self.mode=='health'
        self.health_trend_frame.visible=self.mode=='health'
        if self.mode!='health':
            return
        result=self.health_results.get(self.active_splice)
        self.health_overview.text=' | '.join(f'{s} {r["health_state"]}' for s,r in sorted(self.health_results.items()))
        if result is None:
            self.health_source.text=f'{self.active_splice} / awaiting completed inspection'
            self.health_score_label.text='HEALTH: -- / 100'
            self.health_state_label.text='STATE: --'
            for widget in self.evidence_rows.values(): widget.text='--'
            for widget in (self.health_anomaly_label,self.health_direction_label,self.health_stage_label): widget.text='--'
            return
        self.health_source.text=f'{self.active_splice} | Original {result["baseline_source"]} -> Current {result["inspection_id"]}'
        self.health_score_label.text=f'HEALTH: {result["health_score"]:.1f} / 100'
        self.health_score_label.style={'font_size':20,'color':COLORS[result['health_state']]}
        self.health_state_label.text=f'STATE: {result["health_state"]}'
        self.health_state_label.style={'font_size':16,'color':COLORS[result['health_state']]}
        self.health_anomaly_label.text=f'ANOMALY: {result["current_anomaly_score"]:.3f} / {result["current_anomaly_severity"]}'
        self.health_direction_label.text=f'TREND: {result["trend_direction"]}'
        self.health_stage_label.text='STAGE: '+result.get('synthetic_scenario',{}).get('stage','HEALTHY OBSERVATION')
        for name in ('mfl','camera','profile','tension'):
            self.evidence_rows[name].text=f'{name.upper():9s} {result[name+"_evidence"]["deviation"]:.3f}'
        self.evidence_rows['trend'].text=f'HISTORICAL TREND: {result["trend_score"]:.3f} / degradation'
        self.evidence_rows['confidence'].text=f'DATA CONFIDENCE: {result["data_confidence"]:.0%} / completeness'
        self.fusion_explanation.text=f'70% current + 30% history | {result["trend_observation_count"]} observations | MFL09-MFL13 tracked'
        self.fusion_explanation.tooltip=result['explanation']
