from bqplot import Label
from bqplot.marks import Lines
from cosmicds.components.toolbar import Toolbar
from echo import add_callback, delay_callback, CallbackProperty
from glue.config import viewer_tool
from glue.viewers.common.utils import get_viewer_tools
from glue.viewers.scatter.state import ScatterViewerState
from glue_jupyter.bqplot.scatter import BqplotScatterView, \
    BqplotScatterLayerArtist
from traitlets import Bool

from cosmicds.viewers.cds_viewers import cds_viewer
from ..utils import H_ALPHA_REST_LAMBDA, MG_REST_LAMBDA

__all__ = ['SpectrumView', 'SpectrumViewLayerArtist', 'SpectrumViewerState']


class SpectrumViewerState(ScatterViewerState):
    _YMAX_FACTOR = 1.5

    resolution_x = CallbackProperty(0)
    resolution_y = CallbackProperty(0)

    @property
    def ymax_factor(self):
        return self._YMAX_FACTOR

    def reset_limits(self):
        with delay_callback(self, 'x_min', 'x_max', 'y_min', 'y_max'):
            xmin, xmax = self.x_min, self.x_max
            ymin, ymax = self.y_min, self.y_max
            super().reset_limits()
            self.y_max = self._YMAX_FACTOR * self.y_max
            self.resolution_x *= (self.x_max - self.x_min) / (xmax - xmin)
            self.resolution_y *= (self.y_max - self.y_min) / (ymax - ymin)


class SpectrumViewLayerArtist(BqplotScatterLayerArtist):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        old_scatter = self.scatter
        self.scatter = Lines(scales=self.scales, x=[0, 1], y=[0, 1],
                             marker=None, colors=['#507FB6'], stroke_width=1.8)
        self.view.figure.marks = list(
            filter(lambda x: x is not old_scatter, self.view.figure.marks)) + [
                                     self.scatter]


class SpecView(BqplotScatterView):
    _data_artist_cls = SpectrumViewLayerArtist
    _subset_artist_cls = SpectrumViewLayerArtist

    inherit_tools = False
    tools = ['bqplot:home', 'hubble:wavezoom', 'hubble:restwave','cds:info']
    _state_cls = SpectrumViewerState
    show_line = Bool(True)
    LABEL = "Spectrum Viewer"

    observed_text = ' (observed)'
    rest_text = ' (rest)'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.figure_size_x = 0
        self.figure_size_y = 230
        self.element = None
        self._resolution_dirty = True

        self.user_line = Lines(
            x=[0, 0],
            y=[0, 0],
            scales={
                'x': self.scales['x'],
                'y': self.scales['y'],
            },
            colors=['#1b3e6a'],
        )

        self.user_line_label = Label(
            text=[""],
            x=[],
            y=[],
            x_offset=10,
            y_offset=10,
            scales={
                'x': self.scales['x'],
                'y': self.scales['y'],
            },
            colors=['#1b3e6a'],
        )

        self.label_background = Lines(
            x=[0, 0],
            y=[0, 0],
            stroke_width=25,
            scales={
                'x': self.scales['x'],
                'y': self.scales['y'],
            },
            colors=['white'],
            opacities=[0.8]
        )

        self.previous_line = Lines(
            x=[0, 0],
            y=[0, 0],
            scales={
                'x': self.scales['x'],
                'y': self.scales['y'],
            },
            colors=['#a7a5a5'],
            visible=False
        )

        self.previous_line_label = Label(
            text=[""],
            x=[],
            y=[],
            x_offset=10,
            y_offset=10,
            scales={
                'x': self.scales['x'],
                'y': self.scales['y'],
            },
            colors=['#747272'],
            visible=False
        )

        self.previous_label_background = Lines(
            x=[0, 0],
            y=[0, 0],
            stroke_width=25,
            scales={
                'x': self.scales['x'],
                'y': self.scales['y'],
            },
            colors=['white'],
            opacities=[0.8]
        )

        self.element_tick = Lines(
            x=[],
            y=[0, 0],
            x_offset=-10,
            opacities=[0.7],
            colors=['red'],
            stroke_width=10,
            scales={
                'x': self.scales['x'],
                'y': self.scales['y'],
            })

        self.element_label = Label(
            text=["H-α"],
            x=[],
            y=[],
            x_offset=-5,
            opacities=[0.7],
            colors=['red'],
            scales={
                'x': self.scales['x'],
                'y': self.scales['y'],
            })

        self.figure.marks += [self.previous_label_background,
                              self.previous_line, self.previous_line_label,
                              self.label_background, self.user_line,
                              self.user_line_label,
                              self.element_tick, self.element_label]

        self.scale_y.observe(self._update_locations, names=['min', 'max'])

        add_callback(self.state, 'y_min', self._on_ymin_change, echo_old=True)
        add_callback(self.state, 'y_max', self._on_ymax_change, echo_old=True)
        add_callback(self.state, 'resolution_x', self._update_x_locations)
        add_callback(self.state, 'resolution_y', self._update_y_locations)
        self.toolbar.observe(self._active_tool_change, names=['active_tool'])

    @staticmethod
    def _label_text(value):
        return f"{value:.0f} Å"

    def _x_background_coordinates(self, x):
        return [x + 10 * self.state.resolution_x,
                x + 65 * self.state.resolution_x]

    def _y_background_coordinates(self, y):
        return [y - 10 * self.state.resolution_y,
                y - 10 * self.state.resolution_y]

    def _active_tool_change(self, change):
        is_tool = change.new is not None
        line_visible = not is_tool or change.new.tool_id != 'hubble:wavezoom'
        for mark in [self.user_line, self.user_line_label,
                     self.label_background]:
            mark.visible = line_visible

    def _on_ymin_change(self, old, new):
        if old is not None:
            ymax = self.state.y_max
            self.state.resolution_y *= (ymax - new + 20) / (ymax - old + 20)
        self._update_y_locations()

    def _on_ymax_change(self, old, new):
        if old is not None:
            ymin = self.state.y_min
            self.state.resolution_y *= (new - ymin + 20) / (old - ymin + 20)
        self._update_y_locations()

    def _update_y_locations(self, resolution=None):
        scale = self.scales['y']
        ymin, ymax = scale.min, scale.max

        if ymin is None or ymax is None:
            return

        line_bounds = [ymin, ymax / self.state.ymax_factor]
        tick_bounds = [ymax * 0.74, ymax * 0.87]
        bottom_label_position = ymax * 0.91
        self.user_line.y = line_bounds
        self.previous_line.y = line_bounds
        self.user_line_label.y = [self.user_line.y[1]]
        self.label_background.y = self._y_background_coordinates(
            self.user_line_label.y[0])
        self.previous_line_label.y = [self.previous_line.y[1]]
        self.previous_label_background.y = self._y_background_coordinates(
            self.previous_line_label.y[0])
        self.element_tick.y = tick_bounds
        self.element_label.y = [bottom_label_position]

    def _update_x_locations(self, resolution=None):
        self.user_line_label.x = [self.user_line.x[0]]
        self.label_background.x = self._x_background_coordinates(
            self.user_line_label.x[0])
        self.previous_line_label.x = [self.previous_line.x[0]]
        self.previous_label_background.x = self._x_background_coordinates(
            self.previous_line_label.x[0])

    def _update_locations(self, event=None):
        self._update_x_locations()
        self._update_y_locations()

    def _on_mouse_moved(self, event):

        if not self.user_line.visible \
                or self.state.x_min is None:
            return

        new_x = event['domain']['x']

        if self._resolution_dirty:
            pixel_x = event['pixel']['x']
            y = event['domain']['y']
            pixel_y = event['pixel']['y']
            self.state.resolution_x = (new_x - self.state.x_min) / pixel_x
            if self.state.resolution_x != 0:
                self.figure_size_x = (self.state.x_max - self.state.x_min) / self.state.resolution_x
            self.state.resolution_y = (self.state.y_max - y) / (
                        pixel_y - 10)  # The y-axis has 10px "extra" on the top and bottom
            if self.state.resolution_y != 0:
                self.figure_size_y = (self.state.y_max - self.state.y_min) / self.state.resolution_y
            self._resolution_dirty = False

        self.user_line_label.text = [self._label_text(new_x)]
        self.user_line.x = [new_x, new_x]
        self.user_line_label.x = [new_x, new_x]
        self.label_background.x = self._x_background_coordinates(self.user_line_label.x[0])
        self.label_background.y = self._y_background_coordinates(self.user_line_label.y[0])

    def _on_click(self, event):
        new_x = event['domain']['x']
        self.previous_line.x = [new_x, new_x]
        self.previous_line_label.text = [self._label_text(new_x)]
        self.previous_line_label.x = [new_x, new_x]
        self.previous_label_background.x = self._x_background_coordinates(
            new_x)
        self.previous_label_background.y = self._y_background_coordinates(
            self.previous_line_label.y[0])
        self.previous_line.visible = True
        self.previous_line_label.visible = True
        self.previous_label_background.visible = True

    def update(self, name, element, z, previous=None):
        self.spectrum_name = name
        self.element = element
        self.z = z
        rest = MG_REST_LAMBDA if element == 'Mg-I' else H_ALPHA_REST_LAMBDA
        self.shifted = rest * (1 + z)
        items_visible = bool(
            z > 0)  # The bqplot Mark complained without the explicit bool() call
        self.element_label.visible = items_visible
        self.element_tick.visible = items_visible
        self.user_line.visible = items_visible
        self.user_line_label.visible = items_visible
        self.label_background.visible = items_visible
        has_previous = previous is not None
        self.previous_line.visible = has_previous
        self.previous_line_label.visible = has_previous
        self.previous_label_background.visible = has_previous
        if has_previous:
            self.previous_line.x = [previous, previous]
            self.previous_line_label.x = [previous, previous]
            self.previous_line_label.text = [self._label_text(previous)]
            self.previous_label_background.x = self._x_background_coordinates(
                previous)
        self.element_label.x = [self.shifted, self.shifted]
        self.element_label.text = [element]
        self.element_tick.x = [self.shifted, self.shifted]
        self._update_locations()
        self._resolution_dirty = True

    def add_data(self, data):
        super().add_data(data)
        self.state.x_att = data.id['lambda']
        self.state.y_att = data.id['flux']
        self.layers[0].state.attribute = data.id['flux']
        for layer in self.layers:
            if layer.state.layer.label != data.label:
                layer.state.visible = False

        bring_to_front = [
            self.previous_label_background, self.previous_line,
            self.previous_line_label,
            self.label_background, self.user_line, self.user_line_label
        ]
        marks = [x for x in self.figure.marks if x not in bring_to_front]
        self.figure.marks = marks + bring_to_front

    def initialize_toolbar(self):
        self.toolbar = Toolbar(self)

        tool_ids, subtool_ids = get_viewer_tools(self.__class__)

        if subtool_ids:
            raise ValueError(
                'subtools are not yet supported in Jupyter viewers')

        for tool_id in tool_ids:
            mode_cls = viewer_tool.members[tool_id]
            mode = mode_cls(self)
            self.toolbar.add_tool(mode)

        zoom_tool = self.toolbar.tools["hubble:wavezoom"]

        zoom_tool.on_zoom = self.on_xzoom

    def on_xzoom(self, old_state, new_state):
        self.state.resolution_x *= (new_state.x_max - new_state.x_min) / (
                    old_state.x_max - old_state.x_min)

    @property
    def line_visible(self):
        return self.user_line.visible


SpectrumView = cds_viewer(SpecView, "SpectrumView")
