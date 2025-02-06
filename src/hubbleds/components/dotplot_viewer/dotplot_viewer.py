from random import randint
from cosmicds.viewers.dotplot.viewer import DotplotScatterLayerArtist

import solara
from glue.core import Data, Subset
from reacton import ipyvuetify as rv

from hubbleds.viewers.hubble_dotplot import HubbleDotPlotView, HubbleDotPlotViewer
from cosmicds.viewers.dotplot.state import DotPlotViewerState

from glue.viewers.common.viewer import Viewer
from glue_plotly.viewers.common import PlotlyBaseView
from cosmicds.utils import vertical_line_mark, extend_tool
from hubbleds.utils import PLOTLY_MARGINS
from hubbleds.viewer_marker_colors import LIGHT_GENERIC_COLOR
from itertools import chain
from uuid import uuid4
from plotly.graph_objects import Scatter
import plotly.graph_objects as go
from numbers import Number
from typing import Callable, Iterable, List, cast, Union, Optional
from solara.toestand import Reactive
import numpy as np

from cosmicds.components import LayerToggle

from cosmicds.logger import setup_logger
logger = setup_logger("DOTPLOT")

from glue_jupyter import JupyterApplication

from hubbleds.tools import BinHighlighter

def valid_two_element_array(arr: Union[None, list]):
    return not (arr is None or len(arr) != 2 or np.isnan(arr).any())

def different_value(arr, value, index):
    if not valid_two_element_array(arr):
        return True
    return arr[index] != value

def this_or_default(arr, default, index):
    if not valid_two_element_array(arr):
        return default
    return arr[index]


_original_update_data = DotplotScatterLayerArtist._update_data

@solara.component
def DotplotViewer(
    gjapp: JupyterApplication, 
    data=None, 
    component_id=None, 
    title = None, 
    height=300, 
    on_click_callback = None, 
    line_marker_at: Optional[Reactive | int | float] = None, 
    line_marker_color = LIGHT_GENERIC_COLOR, 
    vertical_line_visible: Union[Reactive[bool], bool] = True,
    unit: Optional[str] = None,
    x_label: Optional[str] = None,
    y_label: Optional[str] = None,
    zorder: Optional[list[int]] = None,
    nbin: int = 75,
    x_bounds: Optional[Reactive[list[float]]] = None,
    reset_bounds: Reactive[list] = Reactive([]),
    hide_layers: Reactive[List[Data | Subset]] | list[Data | Subset] = [],
    highlight_bins: Reactive[bool] | bool = False
    ):
    
    """
    DotplotViewer component
    
    Basic Usage:
    ```python
    data = Data(label = "Test Data", x=[randint(1, 10) for _ in range(30)])
    DotplotViewer(data = data, component_id: str = 'x')
    ```
    
    Parameters:
    - `gjapp`: The GlueJupyter application instance
    - `data`: The data to be displayed in the viewer. Can be a single Data object or a list of Data objects.
    - `component_id`: The component id of the data to be displayed. Only used if `data` is a list of Data objects.
       the components should already linked. component_id is the id for the first (only) Data object in the list.
    - `title`: The title of the viewer
    - `height`: The height of the viewer (default: 400)
    - `on_click_callback`: A callback function that is called when a point is clicked. The function should accept the
    - `line_marker_at`: The value at which the vertical line marker should be placed (passed value is displayed)
    - `line_marker_color`: The color of the vertical line marker (default: 'red')
    - `vertical_line_visible`: Whether the vertical line marker should be visible (default: True)
    - `unit`: The unit for the x-axis values, used in the label for the vertical line (default: None)
    - `x_label`: x_label (Optional[str]): The label for the x-axis of the dot plot. If None, the label will be the name of the x attribute.
    - `y_label`: y_label (Optional[str]): The label for the y-axis of the dot plot. If None, the label will be the name of the y attribute.
    
    """
    
    logger.info(f"creating DotplotViewer: {title}")
    
    line_marker_at = solara.use_reactive(line_marker_at)
    vertical_line_visible = solara.use_reactive(vertical_line_visible)
    x_bounds = solara.use_reactive(x_bounds) # type: ignore
    reset_bounds = solara.use_reactive(reset_bounds)
    hide_layers = solara.use_reactive(hide_layers)
    # bin_highlighter: Reactive[Optional[BinHighlighter]] = solara.use_reactive(None)
    highlight_bins = solara.use_reactive(highlight_bins)
    
    with rv.Card() as main:
        with rv.Toolbar(dense=True, class_="toolbar"):
            with rv.ToolbarTitle(class_="toolbar toolbar-title"):
                title_container = rv.Html(tag="div")

            rv.Spacer()
            toolbar_container = rv.Html(tag="div")

        viewer_container = rv.Html(tag="div", style_=f"width: 100%; height: {height}px", class_="mb-4")
        
        def _line_ids_for_viewer(viewer: PlotlyBaseView):
            line_ids = []
            traces = list(chain(l.traces() for l in viewer.layers))
            for trace in viewer.figure.data:
                if trace not in traces and isinstance(trace, Scatter) and getattr(trace, "meta", None):
                    line_ids.append(trace.meta)

            return line_ids
        
        def _remove_lines(viewers: List[PlotlyBaseView], line_ids: List[List[str]]):
            if not line_ids:
                return
            for (viewer, viewer_line_ids) in zip(viewers, line_ids):
                shapes = viewer.figure.layout.shapes
                shapes = tuple(s for s in shapes if s.name not in viewer_line_ids)
                viewer.figure.layout.shapes = shapes

        
        def _add_vertical_line(viewer: PlotlyBaseView, value: Number, color: str, label: str = None, line_ids: list[str] = []):
            line_id = str(uuid4())
            line_ids.append(line_id)
            viewer.figure.add_vline(x=value, line_color=color, line_width=2, name=line_id)

        
        def _add_data(viewer: PlotlyBaseView, data: Union[Data, tuple]):
            if isinstance(data, Data):
                viewer.add_data(data)
            else:
                viewer.add_data(data[0], layer_type=data[1])

        def _add_viewer():
            logger.info(f"Dotplot _add_viewer()")
            if data is None:
                viewer_data = Data(label = "Test Data", x=[randint(1, 10) for _ in range(30)])
                gjapp.data_collection.append(viewer_data)
            else: 
                if isinstance(data, Data):
                    viewer_data = data
                else:
                    viewer_data = data[0]
            
            dotplot_view: HubbleDotPlotViewer = gjapp.new_data_viewer(
                HubbleDotPlotView, show=False) # type: ignore

            _add_data(dotplot_view, viewer_data)
            if isinstance(viewer_data, tuple):
                viewer_data = viewer_data[0]
            
            if component_id is not None:
                dotplot_view.state.x_att = viewer_data.id[component_id]
            
            if isinstance(data, list):
                if len(data) > 1:
                    for viewer_data in data[1:]:
                        _add_data(dotplot_view, viewer_data)

            dotplot_view.state.hist_n_bin = nbin
            if x_bounds.value is not None:
                if len(x_bounds.value) == 2:
                    dotplot_view.state.x_min = x_bounds.value[0]
                    dotplot_view.state.x_max = x_bounds.value[1]
            
            
            
            
            for layer in dotplot_view.layers:
                for trace in layer.traces():
                    trace.update(hoverinfo="skip", hovertemplate=None)

            def no_hover_update(self: DotplotScatterLayerArtist):
                with dotplot_view.figure.batch_update():
                    _original_update_data(self)
                    for trace in self.traces():
                        trace.update(hoverinfo="skip", hovertemplate=None)
            DotplotScatterLayerArtist._update_data = no_hover_update
                
            def get_layer(layer_name):
                layer_artist = dotplot_view.layer_artist_for_data(layer_name) # type: ignore
                if layer_artist is None:
                    logger.warning(f"Layer not found: {layer_name}")
                return layer_artist
            
            def hide_ignored_layers(*args):
                logger.info("Hiding ignored layers")
                layers = dotplot_view.layers
                hidden_layers = [get_layer(l) for l in hide_layers.value] # type: ignore
                # visible_layers = [l for l in layers if l not in hidden_layers]
                for layer in hidden_layers:
                    if layer is not None:
                        # logger.info(f"\n\t({title}) Hiding layer: {layer.layer.label}")
                        layer.visible = False
                for layer in layers:
                    if (layer is not None) and not layer in hidden_layers:
                        # logger.info(f"\n\t({title}) Showing layer: {layer.layer.label}")
                        layer.visible = True
                layer_status = ''.join([f"\n\t{l.layer.label}: {'visible' if l.visible else 'not visible'}" for l in dotplot_view.layers])
            
            hide_ignored_layers()
            hide_layers.subscribe(hide_ignored_layers)

            # override the default selection layer
            def new_update_selection(self=dotplot_view):
                state = cast(DotPlotViewerState, self.state)
                x0 = state.x_min
                dx = (state.x_max - state.x_min) * .005
                y0 = state.y_min
                dy = (state.y_max - state.y_min) * 2
                self.selection_layer.update(x0=x0 - dx, dx=dx, y0=y0, dy=dy)

            dotplot_view._update_selection_layer_bounds = new_update_selection

            if x_label is not None:    
                dotplot_view.state.x_axislabel = x_label

            if y_label is not None:    
                dotplot_view.state.y_axislabel = y_label

            
            line_ids = [] #[_line_ids_for_viewer(dotplot_view)]
            
            def _update_lines(value = None):
                # remove any pre existing lines

                _remove_lines([dotplot_view], line_ids)
                
                line_ids.clear()
                
                if vertical_line_visible.value and value is not None:
                    _add_vertical_line(dotplot_view, value, line_marker_color, label = "Line Marker", line_ids = line_ids)
                
                # line_ids.append(_line_ids_for_viewer(dotplot_view))
            
            
            
            if title is not None:
                dotplot_view.state.title = title
    
            title_widget = solara.get_widget(title_container)
            title_widget.children = (dotplot_view.state.title or "DOTPLOT VIEWER",)

            toolbar_widget = solara.get_widget(toolbar_container)
            toolbar_widget.children = (dotplot_view.toolbar,)

            viewer_widget = solara.get_widget(viewer_container)
            viewer_widget.children = (dotplot_view.figure_widget,)

            # The auto sizing in the plotly widget only works if the height
            #  and width are undefined. First, unset the height and width,
            #  then enable auto sizing.
            dotplot_view.figure_widget.update_layout(height=None, width=None)
            dotplot_view.figure_widget.update_layout(autosize=True, height=height)
            dotplot_view.figure_widget.update_layout(
                margin=PLOTLY_MARGINS,
                showlegend=False,
                hovermode="x",
                spikedistance=-1,
                xaxis=dict(
                    spikecolor="black",
                    spikethickness=1,
                    spikedash="solid",
                    spikemode="across",
                    spikesnap="cursor",
                    showspikes=True,
                    tickformat=",.0f",
                    titlefont_size=16,
                ),
                yaxis=dict(
                    tickmode="auto",
                    titlefont_size=16,
                ),
            )
            
            def on_click(trace, points, selector):
                if len(points.xs) > 0:
                    value = points.xs[0]
                    _update_lines(value = value)
                    if on_click_callback is not None:
                        on_click_callback(points)
                else:
                   logger.info(f"({title}) No points selected")

                
                
            dotplot_view.figure.update_layout(clickmode="event", hovermode="closest", showlegend=False)
            dotplot_view.selection_layer.on_click(on_click)
            unit_str = f" {unit}" if unit else ""
            dotplot_view.selection_layer.update(hovertemplate=f"%{{x:,.0f}}{unit_str}<extra></extra>")
            def reset_selection():
                dotplot_view.set_selection_active(True)
                # special treatment for go.Heatmap from https://stackoverflow.com/questions/58630928/how-to-hide-the-colorbar-and-legend-in-plotly-express-bar-graph#comment131880779_68555667
                dotplot_view.selection_layer.update(visible=True, z = [list(range(201))], opacity=0, coloraxis='coloraxis')
                dotplot_view.figure.update_coloraxes(showscale=False)
            

            def apply_zorder():
                logger.info(f"({title}) Applying zorder")
                if zorder:
                    logger.info(f"({title}) zorder: {zorder}")
                    logger.info(f"({title}) layers: {dotplot_view.layers}")
                    for i, layer in enumerate(dotplot_view.layers):
                        try:
                            layer.state.zorder = zorder[i]
                        except IndexError:
                            layer.state.zorder = max(zorder) + 1
            
            # prevent_callback = False
            
            def _on_reset_bounds(*args):
                if None not in reset_bounds.value and len(reset_bounds.value) == 2:
                    new_range = reset_bounds.value
                    dotplot_view.state.x_min = new_range[0]
                    dotplot_view.state.x_max = new_range[1]
                else:
                    new_range = [dotplot_view.state.x_min, dotplot_view.state.x_max]
                
                # new_range = [dotplot_view.state.x_min, dotplot_view.state.x_max]
                if (
                    not valid_two_element_array(x_bounds.value) or
                    not np.isclose(x_bounds.value, new_range).all()
                    ):
                    if valid_two_element_array(new_range):
                        logger.info(f'({title}) reset x_bounds ({new_range[0]:0.2f}, {new_range[1]:0.2f})')
                        x_bounds.set(new_range)
                    else:
                        logger.info(f'Skipped setting x_bounds: {new_range}')
                else:
                    logger.info(f'({title}) Bounds already set')
            
            def _on_bounds_changed(*args):
                logger.info("Bounds changed")
                new_range = [dotplot_view.state.x_min, dotplot_view.state.x_max]
                if (
                    not valid_two_element_array(x_bounds.value) or
                    not np.isclose(x_bounds.value, new_range).all()
                    ):
                    logger.info(f'({title}) set x_bounds ({new_range[0]:0.2f}, {new_range[1]:0.2f})')
                    x_bounds.set(new_range)
                else:
                    logger.info(f'({title}) Bounds already set')
                
                
            def bin_on_hover(trace, points, state):
                if on_click_callback is not None:
                    on_click_callback(points)
            bin_highlighter = BinHighlighter(dotplot_view,
                                             line_color='rgba(120, 120, 255, 1)',
                                             fill_color='rgba(0,0,0,.5)',
                                             show_all_bins=False,
                                             show_bins_with_data_only=True,
                                            #  on_hover_callback=bin_on_hover,
                                             use_selection_layer=True,
                                             setup_selection_layer=False,
                                             )
            def turn_off_bin_highlighter():
                if bin_highlighter is not None:
                    bin_highlighter.turn_off_bin_highlight()
            def turn_on_bin_highlighter():
                if not highlight_bins.value:
                    return
                if bin_highlighter is not None:
                    bin_highlighter.turn_off_bin_highlight()
                    bin_highlighter.setup_bin_highlight()
            def toggle_bin_highlighter(show = True):
                if show:
                    turn_on_bin_highlighter()
                else:
                    turn_off_bin_highlighter()

                    
            def extend_the_tools():  
                extend_tool(dotplot_view, 'plotly:home', activate_cb=turn_off_bin_highlighter, activate_before_tool=True)
                extend_tool(dotplot_view, 'plotly:home', activate_cb=_on_reset_bounds, activate_before_tool=False)
                extend_tool(dotplot_view, 'plotly:home', activate_cb=apply_zorder)
                extend_tool(dotplot_view, 'plotly:home', activate_cb=turn_on_bin_highlighter, activate_before_tool=False)
                extend_tool(dotplot_view, 'plotly:home', activate_cb=turn_on_bin_highlighter, activate_before_tool=False)
                
                extend_tool(dotplot_view, 'hubble:wavezoom', activate_cb=turn_off_bin_highlighter, activate_before_tool=True)
                extend_tool(dotplot_view, 'hubble:wavezoom', deactivate_cb=_on_bounds_changed, activate_before_tool=False)
                extend_tool(dotplot_view, 'hubble:wavezoom', deactivate_cb=apply_zorder)
                extend_tool(dotplot_view, 'hubble:wavezoom', deactivate_cb=turn_on_bin_highlighter, deactivate_before_tool=False)
                
            
            extend_the_tools()
            tool = dotplot_view.toolbar.tools['plotly:home']
            if tool:
                tool.activate()

            zoom_tool = dotplot_view.toolbar.tools['hubble:wavezoom']
            def on_zoom(bounds_old, bounds_new):
                dotplot_view.state._update_bins()
            zoom_tool.on_zoom = on_zoom
            
            
            if line_marker_at.value is not None:
                _update_lines(value = line_marker_at.value)
                
            line_marker_at.subscribe(lambda new_val: _update_lines(value = new_val))
            vertical_line_visible.subscribe(lambda new_val: _update_lines())
            def update_x_bounds(new_val):
                if new_val is not None and len(new_val) == 2:
                    dotplot_view.state.x_min = new_val[0]
                    dotplot_view.state.x_max = new_val[1]
                reset_selection()
            x_bounds.subscribe(update_x_bounds)
            
            tool = dotplot_view.toolbar.tools['plotly:home']
            if tool:
                tool.activate()
            
            reset_selection()
            if highlight_bins.value:
                bin_highlighter.setup_bin_highlight()
            apply_zorder()
            
            highlight_bins.subscribe(toggle_bin_highlighter)
            
            viewer_data_log = ''.join([f"\n\t{l.layer.label}: {'visible' if l.visible else 'not visible'}" for l in dotplot_view.layers])            
            
            def cleanup():
                for cnt in (title_widget, toolbar_widget, viewer_widget):
                    cnt.children = ()

                for wgt in (dotplot_view.toolbar, dotplot_view.figure_widget):
                    # wgt.layout.close()
                    wgt.close()

            return cleanup

        solara.use_effect(_add_viewer, dependencies=[])

    return main
