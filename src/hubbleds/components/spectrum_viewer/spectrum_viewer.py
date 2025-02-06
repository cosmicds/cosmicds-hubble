from typing import Callable, Optional

import plotly.graph_objects as go
import reacton.ipyvuetify as rv
import solara
from hubbleds.state import GalaxyData
from pandas import DataFrame
from hubbleds.components.spectrum_viewer.plotly_figure import FigurePlotly
from cosmicds.logger import setup_logger
from hubbleds.viewer_marker_colors import GENERIC_COLOR, H_ALPHA_COLOR, MY_DATA_COLOR, LIGHT_GENERIC_COLOR
from hubbleds.utils import PLOTLY_MARGINS

from glue_plotly.common import DEFAULT_FONT

logger = setup_logger("SPECTRUM")


@solara.component
def SpectrumViewer(
    galaxy_data: GalaxyData | None,
    obs_wave: float | None = None,
    spectrum_click_enabled: bool = False,
    on_obs_wave_measured: Callable = None,
    on_rest_wave_tool_clicked: Callable = lambda: None,
    on_zoom_tool_clicked: Callable = lambda: None,
    on_zoom_tool_toggled: Callable = lambda: None,
    on_zoom: Callable = lambda: None,
    on_reset_tool_clicked: Callable = lambda: None,
    spectrum_bounds: Optional[solara.Reactive[list[float]]] = None,
    add_marker_here: float | None = None,
    on_spectrum_bounds_changed: Callable = lambda x: None,
    max_spectrum_bounds: Optional[solara.Reactive[list[float]]] = None,
    spectrum_color: str = GENERIC_COLOR,
):

    vertical_line_visible = solara.use_reactive(False)
    toggle_group_state = solara.use_reactive([])

    
    def _on_change_marker_here():
       print('add_marker_here', add_marker_here)
    solara.use_effect(_on_change_marker_here, [add_marker_here])

    x_bounds = solara.use_reactive([])
    y_bounds = solara.use_reactive([])
    if spectrum_bounds is not None:
        spectrum_bounds.subscribe(x_bounds.set)
    
    use_dark_effective = solara.use_trait_observe(solara.lab.theme, "dark_effective")

    async def _load_spectrum():
        if galaxy_data is None:
            return False

        return galaxy_data.spectrum_as_data_frame

    spec_data_task = solara.lab.use_task(  #noqa: SH101
        _load_spectrum,
        dependencies=[galaxy_data],
    )

    def _rest_wave_tool_toggled():
        on_rest_wave_tool_clicked()

    def _on_relayout(event):
        if event is None:
            return

        try:
            x_bounds.set(
                [
                    event["relayout_data"]["xaxis.range[0]"],
                    event["relayout_data"]["xaxis.range[1]"],
                ]
            )
            # y_bounds.set(
            #     [
            #         event["relayout_data"]["yaxis.range[0]"],
            #         event["relayout_data"]["yaxis.range[1]"],
            #     ]
            # )
            toggle_group_state.set([x for x in toggle_group_state.value if x != 0])
        except:
            x_bounds.set([])
            y_bounds.set([])

        if "relayout_data" in event:
            if "xaxis.range[0]" in event["relayout_data"] and "xaxis.range[1]" in event["relayout_data"]:
                if spectrum_bounds is not None:
                    spectrum_bounds.set([
                        event["relayout_data"]["xaxis.range[0]"],
                        event["relayout_data"]["xaxis.range[1]"],
                    ])
                on_zoom()

    def _on_reset_button_clicked(*args, **kwargs):
        x_bounds.set([])
        y_bounds.set([])
        try:
            if spec_data_task.value is not None and spectrum_bounds is not None:
                spectrum_bounds.set([
                    spec_data_task.value["wave"].min(),
                    spec_data_task.value["wave"].max(),
                ])
        except Exception as e:
            print(e)

        on_reset_tool_clicked()
    
    solara.use_effect(_on_reset_button_clicked, dependencies=[galaxy_data])

    def _spectrum_clicked(**kwargs):
        if spectrum_click_enabled:
            vertical_line_visible.set(True)
            on_obs_wave_measured(kwargs["points"]["xs"][0])

    def _zoom_button_clicked():
        on_zoom_tool_clicked()
        on_zoom_tool_toggled()  

    with rv.Card():
        with rv.Toolbar(class_="toolbar", dense=True):
            with rv.ToolbarTitle():
                solara.Text("SPECTRUM VIEWER")

            rv.Spacer()

            solara.IconButton(
                flat=True,
                tile=True,
                icon_name="mdi-cached",
                on_click=_on_reset_button_clicked,
            )

            with rv.BtnToggle(
                v_model=toggle_group_state.value,
                on_v_model=toggle_group_state.set,
                flat=True,
                tile=True,
                group=True,
                multiple=True,
            ):

                solara.IconButton(
                    icon_name="mdi-select-search",
                    on_click=_zoom_button_clicked,
                )

                solara.IconButton(
                    icon_name="mdi-lambda",
                    on_click=_rest_wave_tool_toggled,
                )

        if spec_data_task.value is None:
            with rv.Sheet(
                style_="height: 360px", class_="d-flex justify-center align-center"
            ):
                rv.ProgressCircular(size=100, indeterminate=True, color="primary")

            return
        elif not isinstance(spec_data_task.value, DataFrame):
            with rv.Sheet(
                style_="height: 360px", class_="d-flex justify-center align-center"
            ):
                solara.Text("Select a galaxy to view its spectrum")

            return

        fig = go.Figure()
        fig.add_trace(go.Scatter(
                        x= spec_data_task.value["wave"], 
                        y= spec_data_task.value["flux"],
                        line=dict(
                            color=spectrum_color,
                            width=2,
                        ),
                        mode='lines',
                        hovertemplate="%{x:.0f} Å<extra></extra>",
                    ))
         
        fig.update_layout(
            plot_bgcolor="white",
            font_family=DEFAULT_FONT,
            title_font_family=DEFAULT_FONT,
            margin=PLOTLY_MARGINS,
            yaxis=dict(
                linecolor="black",
                fixedrange=True,
                title="Brightness",
                showgrid=False,
                showline=True,
                linewidth=1,
                mirror=True,
                title_font_family=DEFAULT_FONT, 
                titlefont_size=16, 
                tickfont_size=12,
                ticks="outside",
                ticklen=5,
                tickwidth=1,
                tickcolor="black",
                ),
            xaxis=dict(
                linecolor="black",
                title="Wavelength (Angstroms)",
                showgrid=False,
                showline=True,
                linewidth=1,
                mirror=True,
                title_font_family=DEFAULT_FONT, 
                titlefont_size=16, 
                tickfont_size=12,
                hoverformat=".0f",
                ticks="outside",
                ticklen=5,
                tickwidth=1,
                tickcolor="black",
                ticksuffix=" Å",
                ),
            showlegend=False,
            hoverlabel=dict(
                font_size=16,
                bgcolor="white",
            ),
        )

        # This is the line that appears when user first makes observed wavelength measurement
        fig.add_vline(
            x=obs_wave,
            line_width=2,
            line_color= MY_DATA_COLOR,
            visible=vertical_line_visible.value and obs_wave > 0.0 and spectrum_click_enabled,
        )

        # Orange "Your Measurement" Marker Line & Label
        fig.add_shape(
            type='line',
            x0=obs_wave,
            x1=obs_wave,
            y0=0.0,
            y1=0.2,
            xref="x",
            yref="paper",
            line_color= MY_DATA_COLOR,
            line_width=2,
            fillcolor= MY_DATA_COLOR,
            label={
                "text": f"Your measurement",
                "font": {
                    "color": MY_DATA_COLOR,
                    "family": "Arial, sans-serif",
                    "size": 14, 
                    "weight":"bold"
                },
                "textposition": "bottom right",
                "xanchor": "left",
                "yanchor": "top",
                "textangle": 0,
            },
            visible=vertical_line_visible.value and obs_wave > 0.0  and not spectrum_click_enabled,
        )
        
        # Light gray measurement line
        # if (marker_position is not None) and (not spectrum_click_enabled):
        #     fig.add_vline(
        #         x = marker_position.value,
        #         line_width = 2,
        #         line_color = LIGHT_GENERIC_COLOR,
        #         visible = True,
        #     )
        

        # Red Observed H-alpha Marker Line
        fig.add_shape(
            editable=False,
            x0=galaxy_data.redshift_rest_wave_value - 1.5,
            x1=galaxy_data.redshift_rest_wave_value + 1.5,
            y0=0.82,
            y1=0.99,
            yref="paper",
            # xref="x",
            line_color=H_ALPHA_COLOR,
            fillcolor=H_ALPHA_COLOR,
            ysizemode="scaled",
        )

        # Red Observed H-alpha Marker Label
        fig.add_annotation(
            x=galaxy_data.redshift_rest_wave_value + 7,
            y= 0.99,
            yref="paper",
            text=f"{galaxy_data.element} (observed)",
            showarrow=False,
            font=dict(
                family="Arial, sans-serif",
                size=14,
                color=H_ALPHA_COLOR,
                weight="bold"
            ),
            xanchor="left",
            yanchor="top",
        )

        # Black Rest H-alpha Marker Line            
        fig.add_shape(
            editable=False,
            type="line",
            x0=galaxy_data.rest_wave_value,
            x1=galaxy_data.rest_wave_value,
            xref="x",
            y0=0.0,
            y1=1.0,
            line_color="black",
            ysizemode="scaled",
            yref="paper",
            line=dict(
                dash="dot",
                width=4
            ),
            visible=1 in toggle_group_state.value,
        )

        # Black Rest H-alpha Marker Label
        fig.add_annotation(
            x=galaxy_data.rest_wave_value - 7,
            y= 0.99,
            yref="paper",
            text=f"{galaxy_data.element} (rest)",
            showarrow=False,
            font=dict(
                family="Arial, sans-serif",
                size=14,
                color="black",
                weight="bold"
            ),
            xanchor="right",
            yanchor="top",
            visible=1 in toggle_group_state.value,
        )

        fig.update_layout(
            xaxis_zeroline=False,
            yaxis_zeroline=False,
            xaxis=dict(
                showspikes=spectrum_click_enabled,
                # showline=spectrum_click_enabled,
                spikecolor="black",
                spikethickness=1,
                spikedash="solid",
                spikemode="across",
                spikesnap="cursor",
            ),
            spikedistance=-1,
            hovermode="x",
        )

        if x_bounds.value:  # and y_bounds.value:
            fig.update_xaxes(range=x_bounds.value)
            # fig.update_yaxes(range=y_bounds.value)
        # else:
        fig.update_yaxes(
            range=[
                spec_data_task.value["flux"].min() * 0.95,
                spec_data_task.value["flux"].max() * 1.25,
            ]
        )

        fig.update_layout(dragmode="zoom" if 0 in toggle_group_state.value else False)
        
        
        dependencies = [
            obs_wave,
            spectrum_click_enabled,
            vertical_line_visible.value,
            toggle_group_state.value,
            x_bounds.value,
            y_bounds.value,
            
        ]
        
        # if marker_position is not None:
        #     dependencies.append(marker_position.value)
        
        FigurePlotly(
            fig,
            on_click=lambda kwargs: _spectrum_clicked(**kwargs),
            on_relayout=_on_relayout,
            dependencies=[
                obs_wave,
                spectrum_click_enabled,
                vertical_line_visible.value,
                toggle_group_state.value,
                x_bounds.value,
                y_bounds.value,
            ],
            config={
                "displayModeBar": False,
                "showTips": False 
            },
        )


