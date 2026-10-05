import omni.ui as ui
from splice_tracker import SPLICES

class Phase1HUD:
    def __init__(self, window):
        self.active = False
        with window.get_frame('BeltTwinStatus'):
            with ui.Placer(offset_x=18, offset_y=18, draggable=False):
                with ui.ZStack(width=388, height=563):
                    ui.Rectangle(width=388, height=563,
                                 style={'background_color': 0xE6111B29, 'border_color': 0xFF3A5068,
                                        'border_width': 1, 'border_radius': 8})
                    with ui.Frame(width=360, height=535, style={'padding': 14}):
                        with ui.VStack(spacing=2, content_clipping=True):
                            ui.Label('BELTTWIN', height=34, style={'font_size': 27, 'color': 0xFFFFFFFF})
                            ui.Label('CONVEYOR HEALTH MONITORING', height=23,
                                     style={'font_size': 13, 'color': 0xFF71D7F4})
                            ui.Spacer(height=6)
                            ui.Label('SYSTEM STATUS: ONLINE', height=25,
                                     style={'font_size': 15, 'color': 0xFF66E2A3})
                            ui.Label('CONVEYOR', height=19, style={'font_size': 12, 'color': 0xFF92A9BF})
                            ui.Label('Length                 18 m', height=22, style={'font_size': 15, 'color': 0xFFFFFFFF})
                            ui.Label('Belt speed             1.20 m/s', height=22, style={'font_size': 15, 'color': 0xFFFFFFFF})
                            self.encoder_readout = ui.Label('Encoder position       0.00 m  |  0 ticks', height=23,
                                                        style={'font_size': 14, 'color': 0xFFFFFFFF})
                            ui.Label('SPLICES', height=22, style={'font_size': 12, 'color': 0xFF92A9BF})
                            self.splice_rows = {}
                            for name in SPLICES:
                                with ui.HStack(height=21, spacing=8):
                                    ui.Rectangle(width=8, height=8,
                                                 style={'background_color': [0xFFFF9638, 0xFF18BFEF, 0xFF25DCA2,
                                                                            0xFF9A70F0, 0xFFE7CA3E][int(name[-1]) - 1]})
                                    ui.Label(name, width=58, style={'font_size': 14, 'color': 0xFFFFFFFF})
                                    self.splice_rows[name] = ui.Label('TRACKING' if name == 'S03' else 'NORMAL',
                                                                style={'font_size': 13, 'color': 0xFFBDCCD9})
                            ui.Label('INSPECTION STATION', height=22,
                                     style={'font_size': 12, 'color': 0xFF92A9BF})
                            self.station_status = ui.Label('Status: STANDBY', height=22,
                                                      style={'font_size': 14, 'color': 0xFF66E2A3})
                            ui.Rectangle(height=1, style={'background_color': 0x80506478})
                            self.event_title = ui.Label('AWAITING INSPECTION', height=25,
                                                   style={'font_size': 15, 'color': 0xFF71D7F4})
                            self.event_card = ui.Label('Awaiting next splice', height=86,
                                                  style={'font_size': 16, 'color': 0xFFFFFFFF})
    

    def on_inspection(self, event, count):
        self.active = True
        self.event_title.text = 'INSPECTION EVENT'
        self.event_card.text = (f'SPLICE: {event["splice"]}\nPOSITION: {event["position_m"]:.1f} m\n'
                                f'ENCODER: {event["encoder_ticks"]} ticks\nSTATUS: DETECTED')
        self.event_title.style = {'font_size': 17, 'color': 0xFF75F3AF}
        for name, row in self.splice_rows.items():
            row.text = 'TRACKING' if name == event['splice'] else 'NORMAL'
        self.splice_rows[event['splice']].style = {'font_size': 13, 'color': 0xFFFFDE70}
        self.station_status.text = 'Status: SCANNING'
        self.station_status.style = {'font_size': 14, 'color': 0xFF75F3AF}

    def update(self, distance, state):
        self.encoder_readout.text = f'Encoder position       {distance:.2f} m  |  {round(distance * 100)} ticks'
        if state == 'READY' and self.active:
            self.active = False
            for name, row in self.splice_rows.items():
                row.text = 'TRACKING' if name == 'S03' else 'NORMAL'
                row.style = {'font_size': 13, 'color': 0xFFBDCCD9}
            self.station_status.text = 'Status: STANDBY'
            self.station_status.style = {'font_size': 14, 'color': 0xFF66E2A3}
            self.event_title.text = 'AWAITING NEXT SPLICE'
            self.event_title.style = {'font_size': 15, 'color': 0xFF71D7F4}
            self.event_card.text = 'Splice identification follows encoder position.'
