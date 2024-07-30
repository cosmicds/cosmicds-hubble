import asyncio
from cosmicds.utils import empty_data_from_model_class, DEFAULT_VIEWER_HEIGHT
from cosmicds.viewers import CDSScatterView
from echo import delay_callback
from glue.core import Data
from glue_jupyter import JupyterApplication
from hubbleds.base_component_state import transition_next, transition_previous
import numpy as np
from pathlib import Path
import reacton.ipyvuetify as rv
import solara
from solara.toestand import Ref
from typing import Dict, List, Tuple

from cosmicds.components import ScaffoldAlert, StateEditor, ViewerLayout
from hubbleds.components import DataTable, HubbleExpUniverseSlideshow, LineDrawViewer, PlotlyLayerToggle, Stage4WaitingScreen
from hubbleds.state import LOCAL_STATE, GLOBAL_STATE, StudentMeasurement, get_multiple_choice, get_free_response, mc_callback, fr_callback
from hubbleds.viewers.hubble_scatter_viewer import HubbleScatterView
from .component_state import COMPONENT_STATE, Marker
from hubbleds.remote import LOCAL_API
from hubbleds.utils import AGE_CONSTANT, models_to_glue_data, PLOTLY_MARGINS

from cosmicds.logger import setup_logger

logger = setup_logger("STAGE 4")

GUIDELINE_ROOT = Path(__file__).parent / "guidelines"


@solara.component
def Page():
    solara.Title("HubbleDS")
    loaded_component_state = solara.use_reactive(False)
    router = solara.use_router()

    async def _load_component_state():
        # Load stored component state from database, measurement data is
        # considered higher-level and is loaded when the story starts
        LOCAL_API.get_stage_state(GLOBAL_STATE, LOCAL_STATE, COMPONENT_STATE)

        # TODO: What else to we need to do here?
        logger.info("Finished loading component state for stage 4.")
        loaded_component_state.set(True)

    solara.lab.use_task(_load_component_state)

    async def _write_component_state():
        if not loaded_component_state.value:
            return

        # Listen for changes in the states and write them to the database
        LOCAL_API.put_stage_state(GLOBAL_STATE, LOCAL_STATE, COMPONENT_STATE)

        logger.info("Wrote component state to database.")

    solara.lab.use_task(_write_component_state, dependencies=[COMPONENT_STATE.value])

    def load_class_data():
        logger.info("Loading class data")
        class_measurements = LOCAL_API.get_class_measurements(GLOBAL_STATE, LOCAL_STATE)
        logger.info(len(class_measurements))
        measurements = Ref(LOCAL_STATE.fields.class_measurements)
        student_ids = Ref(LOCAL_STATE.fields.stage_4_class_data_students)
        if class_measurements and not student_ids.value:
            ids = [int(id) for id in np.unique([m.student_id for m in class_measurements])]
            student_ids.set(ids)
        measurements.set(class_measurements)
    
        class_data_points = [m for m in class_measurements if m.student_id in student_ids.value]
        Ref(LOCAL_STATE.fields.enough_students_ready).set(len(class_data_points) >= min(50, 5 * GLOBAL_STATE.value.classroom.size))
            
        return class_data_points

    async def keep_checking_class_data():
        enough_students_ready = Ref(LOCAL_STATE.fields.enough_students_ready)
        while not enough_students_ready.value:
            load_class_data()
            await asyncio.sleep(10)

    solara.lab.use_task(keep_checking_class_data, dependencies=[])

    if COMPONENT_STATE.value.current_step == Marker.wwt_wait:
        Stage4WaitingScreen(
            can_advance=LOCAL_STATE.value.enough_students_ready,
            on_advance_click=lambda: transition_next(COMPONENT_STATE),
        )
        return


    class_plot_data = solara.use_reactive([])

    student_plot_data = solara.use_reactive(LOCAL_STATE.value.measurements)
    async def _load_student_data():
        if not LOCAL_STATE.value.measurements_loaded:
            logger.info("Loading measurements")
            measurements = LOCAL_API.get_measurements(GLOBAL_STATE, LOCAL_STATE)
            student_plot_data.set(measurements)
    solara.lab.use_task(_load_student_data)

    def glue_setup() -> Tuple[JupyterApplication, Dict[str, CDSScatterView]]:
        gjapp = JupyterApplication(
            GLOBAL_STATE.value.glue_data_collection, GLOBAL_STATE.value.glue_session
        )

        race_viewer = gjapp.new_data_viewer(HubbleScatterView, show=False)
        race_data = Data(**{
            "label": "Hubble Race Data",
            "Distance (km)": [12, 24, 30],
            "Velocity (km/hr)": [4, 8, 10],
        })
        race_data = GLOBAL_STATE.value.add_or_update_data(race_data)
        race_data.style.color = "#f00"
        race_data.style.alpha = 1
        race_data.style.markersize = 10
        race_viewer.add_data(race_data)
        race_viewer.state.x_att = race_data.id["Distance (km)"]
        race_viewer.state.y_att = race_data.id["Velocity (km/hr)"]
        race_viewer.state.x_max = 1.1 * race_viewer.state.x_max
        race_viewer.state.y_max = 1.1 * race_viewer.state.y_max
        race_viewer.state.x_min = 0
        race_viewer.state.y_min = 0
        race_viewer.state.title = "Race Data"

        layer_viewer = gjapp.new_data_viewer(HubbleScatterView, show=False)

        viewers = {
            "race": race_viewer,
            "layer": layer_viewer,
        }

        return gjapp, viewers

    gjapp, viewers = solara.use_memo(glue_setup, dependencies=[])

    if not (load_class_data.finished or load_class_data.pending):
        load_class_data()

    def _on_class_data_loaded(class_data_points: List[StudentMeasurement]):
        logger.info("Setting up class glue data")
        if not class_data_points:
            return

        class_data = models_to_glue_data(class_data_points, label="Stage 4 Class Data")
        if not class_data.components:
            class_data = empty_data_from_model_class(StudentMeasurement, label="Stage 4 Class Data")
        class_data = GLOBAL_STATE.value.add_or_update_data(class_data)
        class_data.style.color = "#3A86FF"
        class_data.style.alpha = 1
        class_data.style.markersize = 10

        layer_viewer = viewers["layer"]
        layer_viewer.add_data(class_data)
        layer_viewer.state.x_att = class_data.id['est_dist_value']
        layer_viewer.state.y_att = class_data.id['velocity_value']
        with delay_callback(layer_viewer.state, 'x_max', 'y_max'):
            layer_viewer.state.reset_limits()
            layer_viewer.state.x_max = 1.06 * layer_viewer.state.x_max
            layer_viewer.state.y_max = 1.06 * layer_viewer.state.y_max   
        layer_viewer.state.x_axislabel = "Distance (Mpc)"
        layer_viewer.state.y_axislabel = "Velocity (km/s)"
        layer_viewer.state.title = "Our Data"

        class_plot_data.set(class_data_points)

    if load_class_data.finished:
        _on_class_data_loaded(load_class_data.value)

    StateEditor(Marker, COMPONENT_STATE, LOCAL_STATE, LOCAL_API, show_all=True)

    with solara.ColumnsResponsive(12, large=[4,8]):
        with rv.Col():
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineExploreData.vue",
                event_next_callback = lambda _: transition_next(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.exp_dat1),
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineAgeUniverseEstimate3.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.age_uni3),
                state_view={
                    "age_const": AGE_CONSTANT,
                    "hypgal_distance": COMPONENT_STATE.value.best_fit_gal_dist,
                    "hypgal_velocity": COMPONENT_STATE.value.best_fit_gal_vel,
                }
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineAgeUniverseEstimate4.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.age_uni4),
                state_view={
                    "age_const": AGE_CONSTANT,
                    "hypgal_distance": COMPONENT_STATE.value.best_fit_gal_dist,
                    "hypgal_velocity": COMPONENT_STATE.value.best_fit_gal_vel,
                }
            )

        with rv.Col():
            DataTable(
                title="My Galaxies",
                items=[x.model_dump() for x in LOCAL_STATE.value.measurements],
                headers=[
                    {
                        "text": "Galaxy Name",
                        "align": "start",
                        "sortable": False,
                        "value": "galaxy.name"
                    },
                    { "text": "Velocity (km/s)", "value": "velocity_value" },
                    { "text": "Distance (Mpc)", "value": "est_dist_value" },
                ]
            )

    with solara.ColumnsResponsive(12, large=[4,8]):
        with rv.Col():
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineTrendsDataMC1.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.tre_dat1),
                event_mc_callback=lambda event: mc_callback(event=event, local_state=LOCAL_STATE),
                state_view={
                    "mc_score": get_multiple_choice(LOCAL_STATE, "tre-dat-mc1"),
                    "score_tag": "tre-dat-mc1"
                }
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineTrendsData2.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.tre_dat2),
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineTrendsDataMC3.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.tre_dat3),
                event_mc_callback=lambda event: mc_callback(event=event, local_state=LOCAL_STATE),
                state_view={
                    'mc_score': get_multiple_choice(LOCAL_STATE, 'tre-dat-mc3'),
                    'score_tag': 'tre-dat-mc3'
                }
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineRelationshipVelDistMC.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.rel_vel1),
                event_mc_callback=lambda event: mc_callback(event = event, local_state = LOCAL_STATE),
                state_view={
                    'mc_score': get_multiple_choice(LOCAL_STATE, 'galaxy-trend'),
                    'score_tag': 'galaxy-trend'
                }
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineTrendLines1.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.tre_lin1),               
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineTrendLinesDraw2.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.tre_lin2),
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineBestFitLine.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.bes_fit1),
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineHubblesExpandingUniverse1.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.hub_exp1),
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineAgeUniverse.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.age_uni1),
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineHypotheticalGalaxy.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.hyp_gal1),
                state_view={
                    "hypgal_distance": COMPONENT_STATE.value.best_fit_gal_dist,
                    "hypgal_velocity": COMPONENT_STATE.value.best_fit_gal_vel,
                }
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineAgeRaceEquation.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.age_rac1),
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineAgeUniverseEquation2.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.age_uni2),
                state_view={
                    "age_const": AGE_CONSTANT
                },             
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineYourAgeEstimate.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.you_age1),
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineShortcomingsEstReflect1.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.sho_est1),
                event_fr_callback = lambda event: fr_callback(event, LOCAL_STATE, lambda: LOCAL_API.put_story_state(GLOBAL_STATE, LOCAL_STATE)),
                state_view={
                    'free_response_a': get_free_response(LOCAL_STATE, 'shortcoming-1'),
                    'free_response_b': get_free_response(LOCAL_STATE, 'shortcoming-2'),
                    'free_response_c': get_free_response(LOCAL_STATE, 'other-shortcomings'),
                }
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineShortcomingsEst2.vue",
                event_next_callback=lambda _: router.push("05-class-results-uncertainty"),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.sho_est2),
            )

        # Which data layers to display in plotly viewer
        layers_enabled = solara.use_reactive((False, True))

        # Are the buttons available to press?
        draw_enabled = solara.use_reactive(False)
        fit_enabled = solara.use_reactive(False)
        draw_active = solara.use_reactive(False)

        # Are the plotly traces actively displayed?
        display_best_fit_gal = solara.use_reactive(False)
        clear_class_layer = solara.use_reactive(0)
        clear_drawn_line = solara.use_reactive(0)
        clear_fit_line = solara.use_reactive(0)

        def _on_marker_update(marker):
            if Marker.is_between(marker, Marker.tre_dat2, Marker.hub_exp1):
                layers_enabled.set((True, True))
            else:
                layers_enabled.set((False, True))

            if Marker.is_at_or_after(marker, Marker.tre_lin2):
                draw_enabled.set(True)
            else:
                draw_enabled.set(False)

            if Marker.is_at_or_after(marker, Marker.bes_fit1):
                fit_enabled.set(True)
            else:
                fit_enabled.set(False)

            if Marker.is_at_or_after(marker, Marker.hyp_gal1):
                display_best_fit_gal.set(True)
            else:
                display_best_fit_gal.set(False)

            if Marker.is_on(marker, Marker.tre_lin1):
                # What we really want is for the viewer to check if this layer is visible when it gets to this marker, and if so, clear it.
                clear_class_layer.set(clear_class_layer.value + 1)

            #This has the same issues as above.
            if Marker.is_on(marker, Marker.age_uni1):
                clear_drawn_line.set(clear_drawn_line.value + 1)
                draw_active.set(False)
            
            
        Ref(COMPONENT_STATE.fields.current_step).subscribe(_on_marker_update)

        with rv.Col(class_="no-padding"):
            if COMPONENT_STATE.value.current_step_between(Marker.tre_dat1, Marker.sho_est2):
                with solara.Columns([3,9], classes=["no-padding"]):
                    colors = ("#3A86FF", "#FB5607")
                    sizes = (8, 12)
                    with rv.Col(class_="no-padding"):
                        PlotlyLayerToggle(chart_id="line-draw-viewer",
                        # (Plotly calls layers traces, but we'll use layers for consistency with glue).
                        # For the line draw viewer:
                        # Layer 0 = line that the student draws
                        # Layer 1, 2 = fit lines for data layers.
                        # Layer 3, 4 = data layers.
                        # Layer 5 = endpoint for drawn line.
                        # Add Layer 6 = best fit galaxy marker.
                                          layer_indices=(3, 4),

                        # These are the indices (within the specified tuple, which has 2 data layers) of the layers that we want to have initially checked/displayed. 
                        # If only 1 layer is selected, you still need the comma, otherwise this will be interpreted as an int instead of a tuple. This means "check & display layer 1, which is the student data layer."

                                          initial_selected=(1,),
                                          enabled=layers_enabled.value,
                                          colors=colors,
                                          labels=("Class Data", "My Data"))
                    with rv.Col(class_="no-padding"):
                        if student_plot_data.value and class_plot_data.value:
                            # Note the ordering here - we want the student data on top
                            layers = (class_plot_data.value, student_plot_data.value)
                            layers_visible = (False, True)

                            plot_data=[
                                {
                                    "x": [t.est_dist_value for t in data],
                                    "y": [t.velocity_value for t in data],
                                    "mode": "markers",
                                    "marker": { "color": color, "size": size },
                                    "visible": visibility,    
                                    "hoverinfo": "none"
                                } for data, color, size, visibility in zip(layers, colors, sizes, layers_visible)
                            ]

                            draw_click_count = Ref(COMPONENT_STATE.fields.draw_click_count)
                            best_fit_click_count = Ref(COMPONENT_STATE.fields.best_fit_click_count)
                            best_fit_slope = Ref(LOCAL_STATE.fields.best_fit_slope)
                            best_fit_gal_vel = Ref(COMPONENT_STATE.fields.best_fit_gal_vel)
                            best_fit_gal_dist = Ref(COMPONENT_STATE.fields.best_fit_gal_dist)

                            def draw_click_cb():
                                draw_click_count.set(draw_click_count.value + 1)    

                            def best_fit_click_cb():
                                best_fit_click_count.set(best_fit_click_count.value + 1)

                            def line_fit_cb(args: Dict):
                                # student line is the 2nd of the 2 layers, so index=1
                                best_fit_slope.set(args["slopes"][1]) 
                                range = args["range"]
                                best_fit_gal_dist.set(round(range/2))
                                best_fit_gal_vel.set(round(best_fit_slope.value * best_fit_gal_dist.value))

                            LineDrawViewer(chart_id="line-draw-viewer",
                                           title="Our Data",
                                           plot_data=plot_data,
                                           on_draw_clicked=draw_click_cb,
                                           on_best_fit_clicked = best_fit_click_cb,
                                           on_line_fit=line_fit_cb,
                                           x_axis_label="Distance (Mpc)",
                                           y_axis_label="Velocity (km/s)",
                                           viewer_height=DEFAULT_VIEWER_HEIGHT,
                                           plot_margins=PLOTLY_MARGINS,
                                           draw_enabled=draw_enabled.value,
                                           fit_enabled=fit_enabled.value,
                                           display_best_fit_gal = display_best_fit_gal.value,
                                           draw_active=draw_active,
                                           # Use student data for best fit galaxy
                                           best_fit_gal_layer_index=1,
                                           clear_class_layer=clear_class_layer.value,
                                           clear_drawn_line=clear_drawn_line.value,
                                           clear_fit_line=clear_fit_line.value,)

            with rv.Col(cols=10, offset=1):
                if COMPONENT_STATE.value.current_step_at_or_after(
                Marker.hub_exp1):
                    dialog = Ref(COMPONENT_STATE.fields.show_hubble_slideshow_dialog)
                    step = Ref(COMPONENT_STATE.fields.hubble_slideshow_state.step)
                    max_step_completed = Ref(COMPONENT_STATE.fields.hubble_slideshow_state.max_step_completed)
                    slideshow_finished = Ref(COMPONENT_STATE.fields.hubble_slideshow_finished)

                    HubbleExpUniverseSlideshow(
                        race_viewer=ViewerLayout(viewer=viewers["race"]),
                        layer_viewer=ViewerLayout(viewers["layer"]),

                        dialog=COMPONENT_STATE.value.show_hubble_slideshow_dialog,
                        step=COMPONENT_STATE.value.hubble_slideshow_state.step,
                        max_step_completed=COMPONENT_STATE.value.hubble_slideshow_state.max_step_completed,
                        state_view={
                            "mc_score": get_multiple_choice(LOCAL_STATE, "race-age"),
                            "score_tag": "race-age"
                        },
                        
                        event_set_dialog=dialog.set,
                        event_set_step=step.set,
                        event_set_max_step_completed=max_step_completed.set,
                        event_mc_callback=lambda event: mc_callback(event, LOCAL_STATE),
                        event_on_slideshow_finished=lambda _: slideshow_finished.set(True),
                    )
