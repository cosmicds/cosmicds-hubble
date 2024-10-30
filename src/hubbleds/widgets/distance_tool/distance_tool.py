from datetime import datetime

import astropy.units as u
import ipyvue as v
from astropy.coordinates import Angle, SkyCoord
from cosmicds.utils import RepeatedTimer, load_template
from ipywidgets import DOMWidget, widget_serialization
from ipywwt import WWTWidget
from traitlets import Instance, Bool, Float, Int, Unicode, observe, Dict

from ...utils import GALAXY_FOV, angle_to_json, \
    angle_from_json


class DistanceTool(v.VueTemplate):
    template = load_template("distance_tool.vue", __file__, traitlet=True).tag(
        sync=True)
    widget = Instance(DOMWidget, allow_none=True).tag(sync=True,
                                                      **widget_serialization)
    measuring = Bool().tag(sync=True)
    measuredDistance = Float().tag(sync=True)
    angular_size = Instance(Angle).tag(sync=True, to_json=angle_to_json,
                                       from_json=angle_from_json)
    angular_height = Instance(Angle).tag(sync=True, to_json=angle_to_json,
                                         from_json=angle_from_json)
    height = Int().tag(sync=True)
    width = Int().tag(sync=True)
    view_changing = Bool(False).tag(sync=True)
    measuring_allowed = Bool(False).tag(sync=True)
    show_ruler = Bool(False).tag(sync=True)
    fov_text = Unicode().tag(sync=True)
    flagged = Bool(False).tag(sync=True)
    ruler_click_count = Int().tag(sync=True)
    measurement_count = Int().tag(sync=True)
    galaxy_selected = Bool(False).tag(sync=True)
    _ra = Angle(0 * u.deg)
    _dec = Angle(0 * u.deg)
    wwtStyle = Dict().tag(sync=True)
    reset_style = Bool(False).tag(sync=True)
    brightness = Float(1).tag(sync=True)
    contrast = Float(0).tag(sync=True)
    
    # Guard
    guard = Bool(False).tag(sync=True)
    galaxy_max_size = Angle("60 arcmin") # 2 x Pinwheel galaxy (d = 7 Mpc, r = 1.7 Rmw)
    galaxy_min_size = Angle("6 arcsec") # 3 x sdss resolution
    bad_measurement = Bool(False).tag(sync=True)

    UPDATE_TIME = 1  # seconds
    START_COORDINATES = SkyCoord(180 * u.deg, 25 * u.deg, frame='icrs')

    def __init__(self, *args, **kwargs):
        self.widget = WWTWidget()
        self._setup_widget()
        self.measuring = kwargs.get('measuring', False)
        self.guard = kwargs.get('guard', False)
        self.angular_size = Angle(0, u.deg)
        self.angular_height = Angle(60, u.deg)
        self.widget._set_message_type_callback('wwt_view_state',
                                               self._update_wwt_state)
        self.last_update = datetime.now()
        self._rt = RepeatedTimer(self.UPDATE_TIME, self._update_wwt_state)
        self._rt.start()
        self.update_text()
        self.resetting = False
        super().__init__(*args, **kwargs)

    def __del__(self):
        self._rt.stop()
        super().__del__()

    def _setup_widget(self):
        # Temp update to set background to SDSS. Once we remove galaxies without SDSS WWT tiles from the catalog, make background DSS again, and set wwt.foreground_opacity = 0, per Peter Williams.
        self.widget.background = 'SDSS: Sloan Digital Sky Survey (Optical)'
        self.widget.foreground = 'SDSS: Sloan Digital Sky Survey (Optical)'
        self.widget.center_on_coordinates(self.START_COORDINATES, fov= 42 * u.arcmin, #start in close enough to see galaxies
                                          instant=True)

    def reset_canvas(self):
        self.resetting = True
        self.send({"method": "reset", "args": []})

    def update_text(self):
        self.send({"method": "update_text", "args": []})

    def _height_from_pixel_str(self, s):
        return int(s[:-2])  # Remove the 'px' from the end

    # We aren't always guaranteed to get an update from the WWT viewer
    # so every second, if the view is marked as changing, 
    # we check when the last update that we got is
    # If it's more than a second old, mark the view as not changing
    def _check_view_changing(self):
        if self.view_changing:
            delta = datetime.now() - self.last_update
            if delta.total_seconds() >= self.UPDATE_TIME:
                self.view_changing = False

    def vue_toggle_measuring(self, _args=None):
        self.measuring = not self.measuring
        self.ruler_click_count += 1

    @observe('measuredDistance')
    def _on_measured_distance_changed(self, change):
        if self.resetting:
            self.resetting = False
            return
        fov = self.widget.get_fov()
        widget_height = self._height_from_pixel_str(self.widget.layout.height)
        ang_size = Angle(((change["new"] / widget_height) * fov))
        valid = self.validate_angular_size(ang_size, True)
        # print(ang_size, change["new"], valid)
        # if valid:
        #     print('valid measurement')
        self.angular_size = ang_size
        self.measurement_count += 1

    @observe('measuring')
    def _on_measuring_changed(self, measuring):
        if not measuring["new"]:
            self.reset_canvas()

    @observe("angular_height")
    def _on_fov_change(self, change):
        d, m, s = change["new"].dms
        m = m + s / 60
        d = d + m / 60
        s = int(s)
        if d > 9.95:  # to avoid edge case where you can get 10 between 10 and 11 and 10.0 from 9.95-10
            self.fov_text = f"{d:.0f}°"
        elif d > 0.99:  # to avoid edge case where you can get 60.0 arcmin from 59.5-59.9 arcmin
            self.fov_text = f"{d:.1f}°"
        elif m > 9.95:
            self.fov_text = f"{m:.0f}'"
        elif m > 0.99:
            self.fov_text = f"{m:.1f}'"
        else:
            self.fov_text = f"{s}\""

    def _update_wwt_state(self, wwt=None, _updated=None):
        fov = Angle(self.widget.get_fov())
        center = self.widget.get_center()
        ra = Angle(center.ra)
        dec = Angle(center.dec)
        changing = not u.allclose([fov, ra, dec],
                                  [self.angular_height, self._ra, self._dec])
        self.angular_height = fov
        self._ra = ra
        self._dec = dec
        self.view_changing = changing
        self.last_update = datetime.now()

    def go_to_location(self, ra, dec, fov=GALAXY_FOV):
        coordinates = SkyCoord(ra * u.deg, dec * u.deg, frame='icrs')
        self.widget.center_on_coordinates(coordinates, fov=fov, instant=True)
    
    def reset_brightness_contrast(self):
        self.wwtStyle = {}
        self.brightness = 100
        self.contrast = 100
        # toggle reset style to trigger watch in vue
        self.reset_style = True
        self.reset_style = False
    
    def activate_guard(self):
        self.guard = True
        
    def deactivate_guard(self):
        self.guard = False
        self.bad_measurement = False
        
    def set_guard(self, max = None, min = None):
        self.activate_guard()
        self.galaxy_max_size = Angle(max) if max is not None else self.galaxy_max_size
        self.galaxy_min_size = Angle(min) if min is not None else self.galaxy_min_size
    
    def validate_angular_size(self, angular_size, check = True):
        if not self.guard:
            return True
        if not check:
            return self.bad_measurement
        max_wwt_size = Angle("60 deg")
        c1 = (angular_size < max_wwt_size) 
        c2 = (angular_size >= self.galaxy_min_size) 
        c3 = (angular_size <= self.galaxy_max_size)
        self.bad_measurement = not (c1 and c2 and c3)
        return c1 and c2 and c3
    
    def vue_set_brightness(self, brightness, *_args):
        print(f"Brightness: {brightness}")
        self.brightness = brightness
    
    def vue_set_contrast(self, contrast, *_args):
        print(f"Contrast: {contrast}")
        self.contrast = contrast