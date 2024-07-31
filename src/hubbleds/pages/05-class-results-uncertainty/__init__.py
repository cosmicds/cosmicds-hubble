from contextlib import ExitStack
from echo import delay_callback, add_callback
from glue.core.message import NumericalDataChangedMessage
from glue.core.subset import RangeSubsetState
from glue_jupyter import JupyterApplication
from glue_jupyter.link import link
from glue_plotly.viewers import PlotlyBaseView
import numpy as np
import solara
from solara.toestand import Ref

from functools import partial
from pathlib import Path
import reacton.ipyvuetify as rv
from typing import Dict, Iterable, Optional, Tuple

from cosmicds.components import PercentageSelector, ScaffoldAlert, StateEditor, StatisticsSelector, ViewerLayout
from cosmicds.utils import empty_data_from_model_class, show_legend, show_layer_traces_in_legend
from cosmicds.viewers import CDSHistogramView
from hubbleds.base_component_state import transition_next, transition_previous
from hubbleds.components import UncertaintySlideshow, IdSlider
from hubbleds.tools import *  # noqa
from hubbleds.state import LOCAL_STATE, GLOBAL_STATE, StudentMeasurement, get_free_response, get_multiple_choice, mc_callback, fr_callback
from hubbleds.utils import make_summary_data, models_to_glue_data
from hubbleds.viewers.hubble_scatter_viewer import HubbleHistogramView, HubbleScatterView
from .component_state import COMPONENT_STATE, Marker
from hubbleds.remote import LOCAL_API

from cosmicds.logger import setup_logger

logger = setup_logger("STAGE 5")


GUIDELINE_ROOT = Path(__file__).parent / "guidelines"


@solara.component
def Page():
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

        logger.info("Wrote stage 5 component state to database.")

    solara.lab.use_task(_write_component_state, dependencies=[COMPONENT_STATE.value])
    
    student_default_color = "#3A86FF"
    student_highlight_color = "#FF5A00"

    class_default_color = "#FF006E"
    class_highlight_color = "#3A86FF"

    def _update_bins(viewers: Iterable[CDSHistogramView], _msg: Optional[NumericalDataChangedMessage]=None):
        props = ('hist_n_bin', 'hist_x_min', 'hist_x_max')
        with ExitStack() as stack:
            for viewer in viewers:
                stack.enter_context(delay_callback(viewer.state, *props))

            values = []
            for viewer in viewers:
                if viewer.layers: 
                    # For now, we assume that the first layer contains the data that we're interested in
                    values.append(viewer.layers[0].layer[viewer.state.x_att])

            if not values:
                return

            try:
                xmin = round(min(min(vals) for vals in values), 0) - 2.5
                xmax = round(max(max(vals) for vals in values), 0) + 2.5
            except:
                return
            for viewer in viewers:
                viewer.state.hist_n_bin = int(xmax - xmin)
                viewer.state.hist_x_min = xmin
                viewer.state.hist_x_max = xmax

    data_ready = solara.use_reactive(False)
    def glue_setup() -> Tuple[JupyterApplication, Dict[str, PlotlyBaseView]]:
        # NOTE: use_memo has to be part of the main page render. Including it
        #  in a conditional will result in an error.
        gjapp = JupyterApplication(
            GLOBAL_STATE.value.glue_data_collection, GLOBAL_STATE.value.glue_session
        )

        layer_viewer = gjapp.new_data_viewer(HubbleScatterView, show=False)
        student_slider_viewer = gjapp.new_data_viewer(HubbleScatterView, show=False)
        class_slider_viewer = gjapp.new_data_viewer(HubbleScatterView, show=False)
        student_hist_viewer = gjapp.new_data_viewer(HubbleHistogramView, show=False)
        all_student_hist_viewer = gjapp.new_data_viewer(HubbleHistogramView, show=False)
        class_hist_viewer = gjapp.new_data_viewer(HubbleHistogramView, show=False)
        viewers = {
            "layer": layer_viewer,
            "student_slider": student_slider_viewer,
            "class_slider": class_slider_viewer,
            "student_hist": student_hist_viewer,
            "all_student_hist": all_student_hist_viewer,
            "class_hist": class_hist_viewer
        }

        hist_viewers = (all_student_hist_viewer, class_hist_viewer)
        for att in ('x_min', 'x_max'):
            link((all_student_hist_viewer.state, att), (class_hist_viewer.state, att))

        if not LOCAL_STATE.value.measurements_loaded:
            LOCAL_API.get_measurements(GLOBAL_STATE, LOCAL_STATE)

        class_measurements = LOCAL_API.get_class_measurements(GLOBAL_STATE, LOCAL_STATE)
        measurements = Ref(LOCAL_STATE.fields.class_measurements)
        student_ids = Ref(LOCAL_STATE.fields.stage_5_class_data_students)
        if class_measurements and not student_ids.value:
            ids = list(np.unique([m.student_id for m in class_measurements]))
            student_ids.set(ids)
        measurements.set(class_measurements)

        all_measurements, student_summaries, class_summaries = LOCAL_API.get_all_data(LOCAL_STATE)
        all_meas = Ref(LOCAL_STATE.fields.all_measurements)
        all_stu_summaries = Ref(LOCAL_STATE.fields.student_summaries)
        all_cls_summaries = Ref(LOCAL_STATE.fields.class_summaries)
        all_meas.set(all_measurements)
        all_stu_summaries.set(student_summaries)
        all_cls_summaries.set(class_summaries)

        student_data = models_to_glue_data(LOCAL_STATE.value.measurements, label="My Data")
        if not student_data.components:
            student_data = empty_data_from_model_class(StudentMeasurement, label="My Data")
        student_data = GLOBAL_STATE.value.add_or_update_data(student_data)

        class_ids = LOCAL_STATE.value.stage_5_class_data_students
        class_data_points = [m for m in LOCAL_STATE.value.class_measurements if m.student_id in class_ids]
        class_data = models_to_glue_data(class_data_points, label="Class Data")
        class_data = GLOBAL_STATE.value.add_or_update_data(class_data)

        for component in ("est_dist_value", "velocity_value"):
            gjapp.add_link(student_data, component, class_data, component)
        layer_viewer.add_data(student_data)
        student_layer = layer_viewer.layers[0]
        student_layer.state.color = student_highlight_color
        student_layer.state.size = 12
        student_layer.state.zorder = 5

        layer_viewer.ignore(lambda data: data.label == "student_slider_subset")
        layer_viewer.add_data(class_data)
        class_layer = layer_viewer.layers[1]
        class_layer.state.zorder = 1
        class_layer.state.color = "#3A86FF"
        class_layer.state.size = 8
        class_layer.state.visible = False


        layer_viewer.state.x_att = class_data.id['est_dist_value']
        layer_viewer.state.y_att = class_data.id['velocity_value']
        layer_viewer.state.x_axislabel = "Distance (Mpc)"
        layer_viewer.state.y_axislabel = "Velocity (km/s)"
        layer_viewer.state.title = "Our Data"
        show_layer_traces_in_legend(layer_viewer)
        show_legend(layer_viewer, show=True)

        if len(class_data.subsets) == 0:
            student_slider_subset = class_data.new_subset(label="student_slider_subset", alpha=1, markersize=10)
        else:
            student_slider_subset = class_data.subsets[0]
        student_slider_viewer.add_data(class_data)
        student_slider_viewer.state.x_att = class_data.id['est_dist_value']
        student_slider_viewer.state.y_att = class_data.id['velocity_value']
        student_slider_viewer.state.x_axislabel = "Distance (Mpc)"
        student_slider_viewer.state.y_axislabel = "Velocity (km/s)"
        student_slider_viewer.state.title = "My Class Data"
        student_slider_viewer.add_subset(student_slider_subset)
        student_slider_viewer.layers[0].state.visible = False
        student_slider_viewer.toolbar.tools["hubble:linefit"].activate()
        show_layer_traces_in_legend(student_slider_viewer)
        show_legend(student_slider_viewer, show=True)

        class_summary_data = make_summary_data(class_data,
                                               input_id_field="student_id",
                                               output_id_field="id",
                                               label="Class Summaries")
        class_summary_data = GLOBAL_STATE.value.add_or_update_data(class_summary_data)

        student_hist_viewer.add_data(class_summary_data)
        student_hist_viewer.state.x_att = class_summary_data.id['age_value']
        student_hist_viewer.state.x_axislabel = "Age (Gyr)"
        student_hist_viewer.state.title = "My class ages (5 galaxies each)"
        student_hist_viewer.layers[0].state.color = "#8338EC"

        all_data = models_to_glue_data(all_measurements, label="All Measurements")
        all_data = GLOBAL_STATE.value.add_or_update_data(all_data)

        student_summ_data = models_to_glue_data(student_summaries, label="All Student Summaries")
        student_summ_data = GLOBAL_STATE.value.add_or_update_data(student_summ_data)

        all_class_summ_data = models_to_glue_data(class_summaries, label="All Class Summaries")
        all_class_summ_data = GLOBAL_STATE.value.add_or_update_data(all_class_summ_data)

        if len(all_data.subsets) == 0:
            class_slider_subset = all_data.new_subset(label="class_slider_subset", alpha=1, markersize=10)
        else:
            class_slider_subset = all_data.subsets[0]

        class_slider_viewer.add_data(all_data)
        class_slider_viewer.state.x_att = all_data.id['est_dist_value']
        class_slider_viewer.state.y_att = all_data.id['velocity_value']
        class_slider_viewer.state.x_axislabel = "Distance (Mpc)"
        class_slider_viewer.state.y_axislabel = "Velocity (km/s)"
        class_slider_viewer.state.title = "All Classes Data"
        class_slider_viewer.layers[0].state.visible = False
        class_slider_viewer.add_subset(class_slider_subset)
        class_slider_viewer.toolbar.tools["hubble:linefit"].activate()
        show_layer_traces_in_legend(class_slider_viewer)
        show_legend(class_slider_viewer, show=True)        

        all_student_hist_viewer.add_data(student_summ_data)
        all_student_hist_viewer.state.x_att = student_summ_data.id['age_value']
        all_student_hist_viewer.state.x_axislabel = "Age (Gyr)"
        all_student_hist_viewer.state.title = "All student ages (5 galaxies each)"
        all_student_hist_viewer.layers[0].state.color = "#FFBE0B"

        class_hist_viewer.add_data(all_class_summ_data)
        class_hist_viewer.state.x_att = all_class_summ_data.id['age_value']
        class_hist_viewer.state.x_axislabel = "Age (Gyr)"
        class_hist_viewer.state.title = "All class ages (~100 galaxies each)"
        class_hist_viewer.layers[0].state.color = "#619EFF"

        # This looks weird, and it kinda is!
        # The idea here is that the all students viewer will always have a wider range than the all classes viewer
        # So we force the home tool of the class viewer to limit-resetting based on the students viewer
        class_hist_viewer.toolbar.tools["plotly:home"].activate = all_student_hist_viewer.toolbar.tools["plotly:home"].activate

        gjapp.data_collection.hub.subscribe(gjapp.data_collection, NumericalDataChangedMessage,
                                            handler=partial(_update_bins, hist_viewers),
                                            filter=lambda msg: msg.data.label == "Student Summaries")

        gjapp.data_collection.hub.subscribe(gjapp.data_collection, NumericalDataChangedMessage,
                                            handler=partial(_update_bins, [student_hist_viewer]),
                                            filter=lambda msg: msg.data.label in ("All Student Summaries", "All Class Summaries"))

        data_ready.set(True)

        return gjapp, viewers

    gjapp, viewers = solara.use_memo(glue_setup, dependencies=[])

    if not data_ready.value:
        rv.ProgressCircular(
            width=3,
            color="primary",
            indeterminate=True,
            size=100,
        )
        return

    _update_bins((viewers["all_student_hist"], viewers["class_hist"]))
    _update_bins((viewers["student_hist"],))

    logger.info("DATA IS READY")

    def show_class_data(marker):
        if "Class Data" in GLOBAL_STATE.value.glue_data_collection:
            class_data = GLOBAL_STATE.value.glue_data_collection["Class Data"]
            layer = viewers["layer"].layer_artist_for_data(class_data)
            layer.state.visible = Marker.is_at_or_after(marker, Marker.cla_dat1)

    def show_student_data(marker):
        if "My Data" in GLOBAL_STATE.value.glue_data_collection:
            student_data = GLOBAL_STATE.value.glue_data_collection["My Data"]
            layer = viewers["layer"].layer_artist_for_data(student_data)
            layer.state.visible = Marker.is_at_or_before(marker, Marker.fin_cla1)

    current_step = Ref(COMPONENT_STATE.fields.current_step)
    
    current_step.subscribe(show_class_data)
    show_class_data(COMPONENT_STATE.value.current_step)

    current_step.subscribe(show_student_data)
    show_student_data(COMPONENT_STATE.value.current_step)   

    class_best_fit_clicked = Ref(COMPONENT_STATE.fields.class_best_fit_clicked)

    def _on_best_fit_line_shown(active):
        if not class_best_fit_clicked.value:
            class_best_fit_clicked.set(active)

    line_fit_tool = viewers["layer"].toolbar.tools['hubble:linefit']
    add_callback(line_fit_tool, 'active',  _on_best_fit_line_shown)

    if (GLOBAL_STATE.value.show_team_interface):
        StateEditor(Marker, COMPONENT_STATE, LOCAL_STATE, LOCAL_API)

    def _on_component_state_loaded(value: bool):
        if not value:
            return

        student_low_age = Ref(COMPONENT_STATE.fields.student_low_age)
        student_high_age = Ref(COMPONENT_STATE.fields.student_high_age)

        class_low_age = Ref(COMPONENT_STATE.fields.class_low_age)
        class_high_age = Ref(COMPONENT_STATE.fields.class_high_age)

        class_data_size = Ref(COMPONENT_STATE.fields.class_data_size)

        class_summary_data = GLOBAL_STATE.value.glue_data_collection["Class Summaries"]
        student_low_age.set(round(min(class_summary_data["age_value"])))
        student_high_age.set(round(max(class_summary_data["age_value"])))
        class_data_size.set(len(class_summary_data["age_value"]))

        all_class_summ_data = GLOBAL_STATE.value.glue_data_collection["All Class Summaries"]
        class_low_age.set(round(min(all_class_summ_data["age_value"])))
        class_high_age.set(round(max(all_class_summ_data["age_value"])))

    loaded_component_state.subscribe(_on_component_state_loaded)

    #--------------------- Row 1: OUR DATA HUBBLE VIEWER -----------------------
    if (
            COMPONENT_STATE.value.current_step_between(Marker.ran_var1, Marker.fin_cla1) \
                    or \
            COMPONENT_STATE.value.current_step_between(Marker.cla_dat1, Marker.you_age1c)
    ):
        with solara.ColumnsResponsive(12, large=[5,7]):
            with rv.Col():
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineRandomVariability.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    allow_back=False,
                    show=COMPONENT_STATE.value.is_current_step(Marker.ran_var1),
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineFinishedClassmates.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.fin_cla1),
                    state_view={
                        "class_data_size": COMPONENT_STATE.value.class_data_size
                    }
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineClassData.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.cla_dat1),
                    state_view={
                        "class_data_size": COMPONENT_STATE.value.class_data_size
                    }                    
                )

                # Skipping this guideline for now since we don't have linedraw functionality in glue viewer.
                # ScaffoldAlert(
                #     GUIDELINE_ROOT / "GuidelineTrendLinesDraw2c.vue",
                #     event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                #     event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                #     can_advance=COMPONENT_STATE.value.can_transition(next=True),
                #     show=COMPONENT_STATE.value.is_current_step(Marker.tre_lin2c),
                # )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineBestFitLinec.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.bes_fit1c),
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineYourAgeEstimatec.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.you_age1c),
                    state_view={
                        "low_guess": get_free_response(LOCAL_STATE, "likely-low-age").get("response"),
                        "high_guess": get_free_response(LOCAL_STATE, "likely-high-age").get("response"),
                        "best_guess": get_free_response(LOCAL_STATE, "best-guess-age").get("response"),
                    }                    
                )

            with rv.Col():
                ViewerLayout(viewer=viewers["layer"])

    # --------------------- Row 2: SLIDER VERSION: OUR DATA HUBBLE VIEWER -----------------------
    if COMPONENT_STATE.value.current_step_between(Marker.cla_res1, Marker.con_int3):
        with solara.ColumnsResponsive(12, large=[5,7]):
            with rv.Col():
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineClassmatesResults.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.cla_res1),
                    state_view={
                        "class_data_size": COMPONENT_STATE.value.class_data_size
                    }
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineRelationshipAgeSlopeMC.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.rel_age1),
                    event_mc_callback=lambda event: mc_callback(event, LOCAL_STATE),
                    state_view={
                        "mc_score": get_multiple_choice(LOCAL_STATE, "age-slope-trend"),
                        "score_tag": "age-slope-trend"
                    }
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineClassAgeRange.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.cla_age1),
                    state_view={
                        "student_low_age": COMPONENT_STATE.value.student_low_age,
                        "student_high_age": COMPONENT_STATE.value.student_high_age,
                    }
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineClassAgeRange2.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.cla_age2),
                    state_view={
                        "student_low_age": COMPONENT_STATE.value.student_low_age,
                        "student_high_age": COMPONENT_STATE.value.student_high_age,
                    }
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineClassAgeRange3.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.cla_age3),
                    state_view={
                        "student_low_age": COMPONENT_STATE.value.student_low_age,
                        "student_high_age": COMPONENT_STATE.value.student_high_age,
                    }
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineClassAgeRange4.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _:transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.cla_age4),
                    state_view={
                        "student_low_age": COMPONENT_STATE.value.student_low_age,
                        "student_high_age": COMPONENT_STATE.value.student_high_age,
                    }
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineLearnUncertainty1.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.lea_unc1),
                    state_view={
                        "uncertainty_slideshow_finished": COMPONENT_STATE.value.uncertainty_slideshow_finished,
                    },
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineMostLikelyValue1.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.mos_lik1),
                )

            def update_student_slider_subset(id, highlighted):
                class_data = gjapp.data_collection["Class Data"]
                student_slider_subset = class_data.subsets[0]
                student_slider_subset.subset_state = RangeSubsetState(id, id, class_data.id['student_id'])
                color = student_highlight_color if highlighted else student_default_color
                student_slider_subset.style.color = color
                student_slider_subset.style.markersize = 12

            with rv.Col(class_="no-padding"):
                ViewerLayout(viewer=viewers["student_slider"])
                class_summary_data = gjapp.data_collection["Class Summaries"]
                IdSlider(
                    gjapp=gjapp,
                    data=class_summary_data,
                    on_id=update_student_slider_subset,
                    highlight_ids=[GLOBAL_STATE.value.student.id],
                    id_component=class_summary_data.id['id'],
                    value_component=class_summary_data.id['age_value'],
                    default_color=student_default_color,
                    highlight_color=student_highlight_color
                )

        if COMPONENT_STATE.value.current_step_between(Marker.lea_unc1, Marker.you_age1c):
            with solara.ColumnsResponsive(12, large=[5,7]):
                with rv.Col():
                    pass
                with rv.Col():
                    with rv.Col(cols=10, offset=1):
                        UncertaintySlideshow(
                            event_on_slideshow_finished=lambda _: Ref(COMPONENT_STATE.fields.uncertainty_slideshow_finished).set(True),
                            step=COMPONENT_STATE.value.uncertainty_state.step,
                            age_calc_short1=get_free_response(LOCAL_STATE, "shortcoming-1").get("response"),
                            age_calc_short2=get_free_response(LOCAL_STATE, "shortcoming-2").get("response"),
                            age_calc_short_other=get_free_response(LOCAL_STATE, "other-shortcomings").get("response"),    
                            event_fr_callback = lambda event: fr_callback(event, LOCAL_STATE, lambda: LOCAL_API.put_story_state(GLOBAL_STATE, LOCAL_STATE)),
                            free_responses=[get_free_response(LOCAL_STATE,'shortcoming-4'), get_free_response(LOCAL_STATE,'systematic-uncertainty')]   
                        )
            
    #--------------------- Row 3: ALL DATA HUBBLE VIEWER - during class sequence -----------------------

    if COMPONENT_STATE.value.current_step_at_or_after(Marker.cla_res1c):
        with solara.ColumnsResponsive(12, large=[5,7]):
            with rv.Col():
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineClassmatesResultsc.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.cla_res1c),
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineClassAgeRangec.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.cla_age1c),
                    state_view={
                        "class_low_age": COMPONENT_STATE.value.class_low_age,
                        "class_high_age": COMPONENT_STATE.value.class_high_age,
                    }
                )

            def update_class_slider_subset(id, highlighted):
                all_data = gjapp.data_collection["All Measurements"]
                class_slider_subset = all_data.subsets[0]
                class_slider_subset.subset_state = RangeSubsetState(id, id, all_data.id['class_id'])
                color = class_highlight_color if highlighted else class_default_color
                class_slider_subset.style.color = color

            with rv.Col():
                ViewerLayout(viewer=viewers["class_slider"])
                all_summary_data = gjapp.data_collection["All Class Summaries"]
                IdSlider(
                    gjapp=gjapp,
                    data=all_summary_data,
                    on_id=update_class_slider_subset,
                    highlight_ids=[GLOBAL_STATE.value.classroom.class_info.get("id", 0)],
                    id_component=all_summary_data.id['class_id'],
                    value_component=all_summary_data.id['age_value'],
                    default_color=class_default_color,
                    highlight_color=class_highlight_color
                )

                with rv.Col(cols=10, offset=1):
                    UncertaintySlideshow(
                        event_on_slideshow_finished=lambda _: Ref(COMPONENT_STATE.fields.uncertainty_slideshow_finished).set(True),
                        step=COMPONENT_STATE.value.uncertainty_state.step,
                        age_calc_short1=get_free_response(LOCAL_STATE, "shortcoming-1").get("response"),
                        age_calc_short2=get_free_response(LOCAL_STATE, "shortcoming-2").get("response"),
                        age_calc_short_other=get_free_response(LOCAL_STATE, "other-shortcomings").get("response"),  
                        event_fr_callback = lambda event: fr_callback(event, LOCAL_STATE, lambda: LOCAL_API.put_story_state(GLOBAL_STATE, LOCAL_STATE)),
                        free_responses=[get_free_response(LOCAL_STATE, 'shortcoming-4'), get_free_response(LOCAL_STATE, 'systematic-uncertainty')]
                )

    #--------------------- Row 4: OUR CLASS HISTOGRAM VIEWER -----------------------
    if COMPONENT_STATE.value.current_step_between(Marker.age_dis1, Marker.con_int3):
        with solara.ColumnsResponsive(12, large=[5,7]):
            with rv.Col():
                with rv.Row():
                    class_summary_data = gjapp.data_collection["Class Summaries"]
                    with rv.Col():
                        if COMPONENT_STATE.value.current_step_between(Marker.mos_lik2, Marker.con_int3):
                            StatisticsSelector(
                                viewers=[viewers["student_hist"]],
                                glue_data=[class_summary_data],
                                units=["counts"],
                                transform=round,
                            )

                    with rv.Col():
                        if COMPONENT_STATE.value.current_step_between(Marker.con_int2, Marker.con_int3):
                            PercentageSelector(
                                viewers=[viewers["student_hist"]],
                                glue_data=[class_summary_data],
                            )

                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineClassAgeDistribution.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.age_dis1),
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineMostLikelyValue2.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.mos_lik2),
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineMostLikelyValue3.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.mos_lik3),
                )

                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineConfidenceInterval.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.con_int1),
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineConfidenceInterval2.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.con_int2),
                )

            with rv.Col():
                ViewerLayout(viewer=viewers["student_hist"])

    ScaffoldAlert(
        GUIDELINE_ROOT / "GuidelineMostLikelyValueReflect4.vue",
        event_next_callback=lambda _: transition_next(COMPONENT_STATE),
        event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
        can_advance=COMPONENT_STATE.value.can_transition(next=True),
        show=COMPONENT_STATE.value.is_current_step(Marker.mos_lik4),
        event_fr_callback = lambda event: fr_callback(event, LOCAL_STATE, lambda: LOCAL_API.put_story_state(GLOBAL_STATE, LOCAL_STATE)),
        state_view={
            'free_response_a': get_free_response(LOCAL_STATE,'best-guess-age'),
            # 'best_guess_answered': LOCAL_STATE.value.question_completed("best-guess-age"),
            'free_response_b': get_free_response(LOCAL_STATE,'my-reasoning')
        }
    )

    ScaffoldAlert(
        GUIDELINE_ROOT / "GuidelineConfidenceIntervalReflect3.vue",
        event_next_callback=lambda _: transition_next(COMPONENT_STATE),
        event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
        can_advance=COMPONENT_STATE.value.can_transition(next=True),
        show=COMPONENT_STATE.value.is_current_step(Marker.con_int3),
        event_fr_callback = lambda event: fr_callback(event, LOCAL_STATE, lambda: LOCAL_API.put_story_state(GLOBAL_STATE, LOCAL_STATE)),
        state_view={
            'free_response_a': get_free_response(LOCAL_STATE,'likely-low-age'),
            'free_response_b': get_free_response(LOCAL_STATE,'likely-high-age'),
            # 'high_low_answered': LOCAL_STATE.value.question_completed("likely-low-age") and LOCAL_STATE.value.question_completed("likely-high-age"),
            'free_response_c': get_free_response(LOCAL_STATE,'my-reasoning-2'),
        }
    )

    #--------------------- Row 5: ALL DATA HISTOGRAM VIEWER -----------------------

    if COMPONENT_STATE.value.current_step_between(Marker.age_dis1c):
        with solara.ColumnsResponsive(12, large=[5,7]):
            with rv.Col():
                with rv.Row():
                    all_student_summary_data = gjapp.data_collection["All Student Summaries"]
                    all_class_summary_data = gjapp.data_collection["All Class Summaries"]
                    hist_viewers = [viewers["all_student_hist"], viewers["class_hist"]]
                    hist_data = [all_student_summary_data, all_class_summary_data]
                    units = ["counts" for _ in range(len(hist_viewers))]
                    with rv.Col():
                        StatisticsSelector(
                            viewers=hist_viewers,
                            glue_data=hist_data,
                            units=units,
                            transform=round,
                        )

                    with rv.Col():
                        PercentageSelector(
                            viewers=hist_viewers,
                            glue_data=hist_data,
                        )

                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineClassAgeDistributionc.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.age_dis1c),
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineTwoHistograms1.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.two_his1),
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineTwoHistogramsMC2.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.two_his2),
                    event_mc_callback=lambda event: mc_callback(event, LOCAL_STATE),
                    state_view = {
                        "mc_score": get_multiple_choice(LOCAL_STATE, "histogram-range"),
                        "score_tag": "histogram-range"
                    }
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineTwoHistogramsMC3.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.two_his3),
                    event_mc_callback=lambda event: mc_callback(event, LOCAL_STATE),
                    state_view = {
                        "mc_score": get_multiple_choice(LOCAL_STATE, "histogram-percent-range"),
                        "score_tag": "histogram-percent-range"
                    }
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineTwoHistogramsMC4.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.two_his4),
                    event_mc_callback=lambda event: mc_callback(event, LOCAL_STATE),
                    state_view = {
                        "mc_score": get_multiple_choice(LOCAL_STATE, "histogram-distribution"),
                        "score_tag": "histogram-distribution"
                    }
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineTwoHistogramsReflect5.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.two_his5),
                    event_fr_callback = lambda event: fr_callback(event, LOCAL_STATE, lambda: LOCAL_API.put_story_state(GLOBAL_STATE, LOCAL_STATE)),
                    state_view={
                        'free_response': get_free_response(LOCAL_STATE,'unc-range-change-reasoning'),
                    }
                )
                ScaffoldAlert(
                    # TODO: event_next_callback should go to next stage but I don't know how to set that up.
                    GUIDELINE_ROOT / "GuidelineMoreDataDistribution.vue",
                    event_next_callback=lambda _: router.push("06-prodata"),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.mor_dat1),
                )

            with rv.Col():
                if COMPONENT_STATE.value.current_step_between(Marker.two_his1):
                    ViewerLayout(viewers["all_student_hist"])

                ViewerLayout(viewers["class_hist"]) 

        ScaffoldAlert(
            GUIDELINE_ROOT / "GuidelineConfidenceIntervalReflect2c.vue",
            event_next_callback=lambda _: transition_next(COMPONENT_STATE),
            event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
            can_advance=COMPONENT_STATE.value.can_transition(next=True),
            show=COMPONENT_STATE.value.is_current_step(Marker.con_int2c),
            event_fr_callback = lambda event: fr_callback(event, LOCAL_STATE, lambda: LOCAL_API.put_story_state(GLOBAL_STATE, LOCAL_STATE)),
            state_view={
                "low_guess": get_free_response(LOCAL_STATE, "likely-low-age").get("response"),
                "high_guess": get_free_response(LOCAL_STATE, "likely-high-age").get("response"),
                "best_guess": get_free_response(LOCAL_STATE, "best-guess-age").get("response"),
                'free_response_a': get_free_response(LOCAL_STATE, 'new-most-likely-age'),
                'free_response_b': get_free_response(LOCAL_STATE, 'new-likely-low-age'),
                'free_response_c': get_free_response(LOCAL_STATE, 'new-likely-high-age'),
                'free_response_d': get_free_response(LOCAL_STATE, 'my-updated-reasoning'),
            }
        )
