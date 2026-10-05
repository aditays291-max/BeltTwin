"""Baseline status and details alongside the unchanged Phase 2 sensor panel."""
import omni.ui as ui
from phase2_hud import Phase2HUD, label, CYAN, GREEN, MUTED, BACKGROUND
from splice_tracker import SPLICES


class Phase3HUD(Phase2HUD):
    def __init__(self, window, store):
        super().__init__(window)
        self.store = store
        self.subtitle.text = 'DIGITAL FINGERPRINTS / PHASE 3'
        self.baseline_rows = {}
        with window.get_frame('BeltTwinFingerprints'):
            with ui.Placer(offset_x=338, offset_y=470, draggable=False):
                with ui.ZStack(width=570, height=204):
                    ui.Rectangle(style={'background_color': BACKGROUND, 'border_radius': 8})
                    with ui.Placer(offset_x=14, offset_y=10, draggable=False):
                        with ui.HStack(width=540, spacing=16):
                            with ui.VStack(width=246, spacing=2):
                                label('DIGITAL FINGERPRINTS', 24, 16, CYAN)
                                for splice in SPLICES:
                                    self.baseline_rows[splice] = label('', 20, 12, GREEN)
                                self.baseline_counter = label('', 24, 14, CYAN)
                                label('First healthy scan / preserved on disk', 18, 10, MUTED)
                            with ui.VStack(width=278, spacing=2):
                                self.detail_title = label('ACTIVE SPLICE: --', 24, 15, CYAN)
                                self.detail = label('Waiting for a completed inspection', 110, 12)
                                self.notice = label('WAITING FOR BASELINE', 22, 12, GREEN)
        self.refresh()
        for splice in SPLICES:
            if store.get(splice):
                self.show_fingerprint(store.get(splice), 'LOADED / BASELINE STORED')
                break

    def refresh(self):
        for splice, widget in self.baseline_rows.items():
            widget.text = f'{splice}    ' + ('STORED / HEALTHY' if self.store.get(splice) else 'WAITING FOR BASELINE')
        self.baseline_counter.text = f'TOTAL BASELINES: {len(self.store)} / 5'

    def on_inspection(self, record, count):
        super().on_inspection(record, count)
        fp = self.store.get(record['splice_id'])
        if fp:
            self.show_fingerprint(fp, 'EXISTS / BASELINE PRESERVED')
        else:
            self.detail_title.text = f'ACTIVE SPLICE: {record["splice_id"]}'
            self.detail.text = 'Waiting for completed healthy scan'
            self.notice.text = 'WAITING FOR BASELINE'

    def creating(self, record):
        self.baseline_rows[record['splice_id']].text = f'{record["splice_id"]}    CREATING...'
        self.notice.text = 'CREATING DIGITAL FINGERPRINT...'

    def show_fingerprint(self, fp, notice):
        self.refresh()
        self.detail_title.text = f'DIGITAL FINGERPRINT / {fp["splice_id"]}'
        self.detail.text = (f'Baseline: HEALTHY\nSource: {fp["created_from_inspection"]}\n'
                            f'Camera: {fp["camera"]["score"]:.3f} | MFL: 24 channels\n'
                            f'Profile: {fp["profile"]["deviation"]:.3f} mm\n'
                            f'Tension: {fp["tension"]["score"]:.3f}')
        self.notice.text = notice
        self.show_mfl(fp['mfl']['channels'], f'SOURCE: {fp["created_from_inspection"]} / STORED HEALTHY BASELINE',
                      f'HEALTHY MFL FINGERPRINT - {fp["splice_id"]}')
