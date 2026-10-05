"""Small native Kit UI panels; bars update only when an inspection completes."""
import omni.ui as ui
from splice_tracker import SPLICES

WHITE = 0xFFF3F4F6
MUTED = 0xFFBFAE9C
CYAN = 0xFFF3D16B
GREEN = 0xFFADE573
BACKGROUND = 0xF0241A12


def label(text, height=19, size=13, color=WHITE, **kwargs):
    return ui.Label(text, height=height, style={'font_size': size, 'color': color}, **kwargs)


class Phase2HUD:
    def __init__(self, window):
        self.latest_record = None
        self.total = 0
        self._state = None
        self.rows = {}
        self.sensor_values = {}
        self.bar_spaces, self.bars = [], []
        with window.get_frame('BeltTwinStatus'):
            with ui.ZStack():
                with ui.Placer(offset_x=14, offset_y=14, draggable=False):
                    with ui.ZStack(width=306, height=554):
                        ui.Rectangle(style={'background_color': BACKGROUND, 'border_radius': 8})
                        with ui.Placer(offset_x=14, offset_y=10, draggable=False):
                            with ui.VStack(width=278, spacing=2):
                                label('BELTTWIN', 29, 25)
                                self.subtitle = label('MULTI-SENSOR INSPECTION / PHASE 2', 17, 11, CYAN)
                                label('SYSTEM ONLINE  |  SYNTHETIC DEMO', 20, 12, GREEN)
                                label('18 m conveyor  |  1.20 m/s', 19, 13)
                                self.encoder = label('Encoder travel: 0.00 m / 0 ticks', 20, 12)
                                self.counter = label('TOTAL INSPECTIONS: 0', 22, 15, CYAN)
                                self.splice_labels = {}
                                with ui.HStack(height=22, spacing=3):
                                    for name in SPLICES:
                                        self.splice_labels[name] = label(name, 22, 13, MUTED, width=50)
                                label('INSPECTION STATION', 22, 12, MUTED)
                                for name in ('CAMERA', 'MFL 24-CH', 'LASER', 'TENSION', 'ENCODER'):
                                    with ui.HStack(height=19):
                                        label(name, 19, 12, WHITE, width=125)
                                        self.rows[name] = label('ACTIVE' if name == 'ENCODER' else 'READY',
                                                                19, 12, GREEN)
                                ui.Spacer(height=5)
                                ui.Rectangle(height=1, style={'background_color': 0xFF645340})
                                self.title = label('AWAITING INSPECTION', 24, 14, CYAN)
                                self.identity = label('All observations share one inspection ID.', 20, 11, MUTED)
                                self.position = label('Position: --', 18, 12)
                                self.ticks = label('Station encoder: --', 18, 12)
                                for sensor in ('CAMERA', 'MFL', 'PROFILE', 'TENSION'):
                                    with ui.HStack(height=21):
                                        label(sensor, 21, 12, MUTED, width=76)
                                        self.sensor_values[sensor] = label('--', 21, 12)
                                self.result = label('AWAITING NEXT SPLICE', 23, 13, GREEN)
                                self.observation_note = label('Healthy values are simulated observations.', 18, 10, MUTED)
                with ui.Placer(offset_x=338, offset_y=14, draggable=False):
                    with ui.ZStack(width=570, height=190):
                        ui.Rectangle(style={'background_color': BACKGROUND, 'border_radius': 8})
                        with ui.Placer(offset_x=14, offset_y=10, draggable=False):
                            with ui.VStack(width=540, spacing=3):
                                self.chart_title = label('MFL 24-CHANNEL SIGNAL', 23, 17, CYAN)
                                self.chart_record = label('Awaiting first inspection', 18, 12, MUTED)
                                with ui.HStack(height=77, spacing=4):
                                    for index in range(24):
                                        with ui.VStack(width=18, height=77, spacing=0):
                                            self.bar_spaces.append(ui.Spacer(height=55))
                                            self.bars.append(ui.Rectangle(height=1,
                                                                          style={'background_color': CYAN}))
                                            label(f'{index + 1:02d}', 19, 10, MUTED)
                                self.range_label = label('Fixed scale: 0.00 to 0.05 | baseline ~0.025', 18, 11, MUTED)
                                label('Normalized synthetic signal / no electromagnetic simulation', 18, 10, MUTED)

    def on_inspection(self, record, count):
        self.latest_record = record
        self.total = count
        self.counter.text = f'TOTAL INSPECTIONS: {count}'
        self.identity.text = f'{record["inspection_id"]}  /  SPLICE {record["splice_id"]}'
        self.position.text = f'POSITION: {record["position_m"]:.1f} m'
        self.ticks.text = f'STATION ENCODER: {record["encoder_ticks"]} ticks'
        for value in self.sensor_values.values():
            value.text = 'SCANNING'
        for name, widget in self.splice_labels.items():
            widget.style = {'font_size': 13, 'color': GREEN if name == record['splice_id'] else MUTED}

    def on_complete(self, record):
        if record is not self.latest_record:
            return
        self.sensor_values['CAMERA'].text = f'{record["camera"]["score"]:.2f}  /  NORMAL'
        self.sensor_values['MFL'].text = f'{len(record["mfl"]["channels"])} channels  /  NORMAL'
        self.sensor_values['PROFILE'].text = f'{record["profile"]["deviation"]:.3f} mm  /  NORMAL'
        self.sensor_values['TENSION'].text = f'{record["tension"]["score"]:.2f}  /  NORMAL'
        self.show_mfl(record['mfl']['channels'],
                      f'LAST SCAN: {record["inspection_id"]} / {record["splice_id"]} / 24 of 24 channels')

    def show_mfl(self, values, caption, title='MFL 24-CHANNEL SIGNAL'):
        self.chart_title.text = title
        for index, value in enumerate(values):
            height = max(1, min(56, value / 0.05 * 56))
            self.bars[index].height = ui.Pixel(height)
            self.bar_spaces[index].height = ui.Pixel(56 - height)
            self.bars[index].tooltip = f'MFL{index + 1:02d}: {value:.4f}'
        self.chart_record.text = caption
        self.range_label.text = f'0.00-0.05 fixed scale | min {min(values):.4f} / max {max(values):.4f}'

    def update(self, distance, state):
        self.encoder.text = f'Encoder travel: {distance:.2f} m / {round(distance * 100)} ticks'
        if state == self._state:
            return
        self._state = state
        for name, widget in self.rows.items():
            widget.text = ('ACTIVE' if name == 'ENCODER' else 'READY') if state == 'READY' else (
                'TRACKING' if name == 'ENCODER' and state == 'SCANNING' else state)
        if state == 'SCANNING':
            self.title.text = 'BELTTWIN INSPECTION'
            self.result.text = 'ACQUIRING OBSERVATIONS'
        elif state == 'COMPLETE':
            self.result.text = 'INSPECTION COMPLETE'
        else:
            self.title.text = 'AWAITING NEXT SPLICE' if self.total else 'AWAITING INSPECTION'
            self.identity.text = 'Encoder identifies the next passing splice.'
            self.position.text = 'POSITION: --'
            self.ticks.text = 'STATION ENCODER: --'
            self.result.text = 'READY TO SCAN'
            for value in self.sensor_values.values():
                value.text = '--'
            for widget in self.splice_labels.values():
                widget.style = {'font_size': 13, 'color': MUTED}
