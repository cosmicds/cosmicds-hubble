import solara
from solara.toestand import Ref
import reacton.ipyvuetify as rv
from numpy import where

# cosmicds
from cosmicds.components import (
    ScaffoldAlert,
    LayerToggle,
    StateEditor,
    ViewerLayout
)
from cosmicds.logger import setup_logger
from cosmicds.utils import show_legend, show_layer_traces_in_legend

# hubbleds
from hubbleds.remote import LOCAL_API
from hubbleds.base_component_state import (
    transition_previous,
    transition_next,
)
from hubbleds.state import (
    LOCAL_STATE, 
    GLOBAL_STATE, 
    mc_callback, 
    fr_callback, 
    get_free_response, 
    get_multiple_choice
)

from ...utils import HST_KEY_AGE, models_to_glue_data, AGE_CONSTANT

from .component_state import COMPONENT_STATE, Marker

# glue-jupyter
from glue_jupyter import JupyterApplication
from glue.core.data_factories import load_data

# misc.
from pathlib import Path

from glue_plotly.viewers import PlotlyBaseView
from ...viewers import HubbleFitView

from typing import Tuple, cast
from ...data_management import HUBBLE_1929_DATA_LABEL, HUBBLE_KEY_DATA_LABEL
import numpy as np

# from ...data_management import *

logger = setup_logger("STAGE")

# the guidelines in the current files parent directory
GUIDELINE_ROOT = Path(__file__).parent / "guidelines"


def basic_viewer_setup(viewer_class, glue_session, data_collection, name, x_att, y_att):
    viewer = viewer_class(glue_session)
    viewer.add_data(data_collection[name])
    viewer.state.x_att = x_att
    viewer.state.y_att = y_att
    return viewer

    
# create the Page for the current stage
@solara.component
def Page():
    # === Setup State Loading and Writing ===
    loaded_component_state = solara.use_reactive(False)
    
    async def _load_component_state():
        LOCAL_API.get_stage_state(GLOBAL_STATE, LOCAL_STATE, COMPONENT_STATE)
        logger.info("Finished loading component state")
        loaded_component_state.set(True)
    
    solara.lab.use_task(_load_component_state)
    
    async def _write_component_state():
        if not loaded_component_state.value:
            return

        # Listen for changes in the states and write them to the database
        LOCAL_API.put_stage_state(GLOBAL_STATE, LOCAL_STATE, COMPONENT_STATE)

        logger.info("Wrote component state to database.")

    solara.lab.use_task(_write_component_state, dependencies=[COMPONENT_STATE.value])
    
    # === Setup Glue ===
    
    def _glue_setup() -> Tuple[JupyterApplication, HubbleFitView]:
        # NOTE: use_memo has to be part of the main page render. Including it
        #  in a conditional will result in an error.
        gjapp = JupyterApplication(
            GLOBAL_STATE.value.glue_data_collection, GLOBAL_STATE.value.glue_session
        )
        
        
        def add_link(from_dc_name, from_att, to_dc_name, to_att):
                from_dc = gjapp.data_collection[from_dc_name]
                to_dc = gjapp.data_collection[to_dc_name]
                gjapp.add_link(from_dc, from_att, to_dc, to_att)


        data_dir = Path(__file__).parent.parent.parent / "data"
        if HUBBLE_KEY_DATA_LABEL not in gjapp.data_collection:
            gjapp.data_collection.append(load_data(data_dir / f"{HUBBLE_KEY_DATA_LABEL}.csv"))
        if HUBBLE_1929_DATA_LABEL not in gjapp.data_collection:
            gjapp.data_collection.append(load_data(data_dir / f"{HUBBLE_1929_DATA_LABEL}.csv"))
        
        if len(LOCAL_STATE.value.class_measurements) == 0:
            class_measurements = LOCAL_API.get_class_measurements(GLOBAL_STATE, LOCAL_STATE)
            measurements = Ref(LOCAL_STATE.fields.class_measurements)
            student_ids = Ref(LOCAL_STATE.fields.stage_5_class_data_students)
            if class_measurements and not student_ids.value:
                ids = list(np.unique([m.student_id for m in class_measurements]))
                student_ids.set(ids)
            measurements.set(class_measurements)
        
        if 'Class Data' not in gjapp.data_collection:
            class_data = models_to_glue_data(LOCAL_STATE.value.class_measurements, label="Class Data")
            class_data = GLOBAL_STATE.value.add_or_update_data(class_data)

        add_link(HUBBLE_1929_DATA_LABEL, 'Distance (Mpc)', HUBBLE_KEY_DATA_LABEL, 'Distance (Mpc)')
        add_link(HUBBLE_1929_DATA_LABEL, 'Tweaked Velocity (km/s)', HUBBLE_KEY_DATA_LABEL, 'Velocity (km/s)')
        add_link(HUBBLE_1929_DATA_LABEL, 'Distance (Mpc)', 'Class Data', 'est_dist_value')
        add_link(HUBBLE_1929_DATA_LABEL, 'Tweaked Velocity (km/s)', 'Class Data', 'velocity_value')

        viewer = cast(HubbleFitView, gjapp.new_data_viewer(HubbleFitView, show=False))
        viewer.state.title = "Professional Data"
        viewer.figure.update_xaxes(showline=True, mirror=False)
        viewer.figure.update_yaxes(showline=True, mirror=False)
        viewer.ignore(lambda data: data.label == "student_slider_subset")
        
        return gjapp, viewer
    

    gjapp, viewer = solara.use_memo(_glue_setup)

    def _state_callback_setup():
        # We want to minimize duplicate state handling, but also keep the states
        #  independent. We'll set up observers for changes here so that they
        #  automatically keep the states in sync.
        # See Stage 1 for an example of how to do this manually.
        pass

    solara.use_memo(_state_callback_setup)    
    
    
    def show_class_data(viewer):
        data = gjapp.data_collection['Class Data']
        if data not in viewer.state.layers_data:
            print('adding class data')
            data.style.markersize = 10
            data.style.color = '#FF6D00'
            viewer.add_data(data)
            viewer.state.x_att = data.id['est_dist_value']
            viewer.state.y_att = data.id['velocity_value']
            viewer.state.reset_limits()
        else:
            viewer.layer_artist_for_data(data).visible = True

    def show_hubble1929_data(viewer):
        data = gjapp.data_collection[HUBBLE_1929_DATA_LABEL]
        if data not in viewer.state.layers_data:
            print('adding Hubble 1929')
            data.style.markersize = 10
            data.style.color = '#D500F9'
            viewer.add_data(data)
            viewer.state.x_att = data.id['Distance (Mpc)']
            viewer.state.y_att = data.id['Tweaked Velocity (km/s)']
            viewer.state.reset_limits()
        else:
            viewer.layer_artist_for_data(data).visible = True
                
    def show_hst_key_data(viewer):
        data = gjapp.data_collection[HUBBLE_KEY_DATA_LABEL]
        if data not in viewer.state.layers_data:
            print('adding HST key')
            data.style.markersize = 10
            data.style.color = '#AEEA00'
            viewer.add_data(data)
            viewer.state.x_att = data.id['Distance (Mpc)']
            viewer.state.y_att = data.id['Velocity (km/s)']  
            viewer.state.reset_limits()
        else:
            viewer.layer_artist_for_data(data).visible = True

    def hide_hubble1929_data(viewer):
        data = gjapp.data_collection[HUBBLE_1929_DATA_LABEL]
        if data in viewer.state.layers_data:
            viewer.layer_artist_for_data(data).visible = False

    def hide_hstkey_data(viewer):
        data = gjapp.data_collection[HUBBLE_KEY_DATA_LABEL]
        if data in viewer.state.layers_data:
            viewer.layer_artist_for_data(data).visible = False

    def add_data_by_marker(viewer, marker):
        if Marker.is_at_or_after(marker, Marker.pro_dat0):
            show_class_data(viewer)
        if Marker.is_between(marker, Marker.pro_dat1, Marker.pro_dat4):
            show_class_data(viewer)
            show_hubble1929_data(viewer)
            hide_hstkey_data(viewer)
        if Marker.is_between(marker, Marker.pro_dat5, Marker.pro_dat7):
            show_class_data(viewer)
            show_hst_key_data(viewer)
            hide_hubble1929_data(viewer)
        if Marker.is_at_or_after(marker, Marker.pro_dat8):
            show_class_data(viewer)
            show_hubble1929_data(viewer)
            show_hst_key_data(viewer)

    def display_fit_legend(marker):
        show_legend(viewer, show=Marker.is_at_or_after(marker, Marker.pro_dat8))

    current_step = Ref(COMPONENT_STATE.fields.current_step)
    current_step.subscribe(lambda step: add_data_by_marker(viewer, step))
    add_data_by_marker(viewer, current_step.value)

    show_layer_traces_in_legend(viewer)

    current_step.subscribe(display_fit_legend)
    display_fit_legend(COMPONENT_STATE.value.current_step)

    @staticmethod
    def linear_slope(x, y):
        # returns the slope, m,  of y(x) = m*x
        return sum(x * y) / sum(x * x)

    def _on_component_state_loaded(value: bool):
        if not value:
            return

        class_age = Ref(COMPONENT_STATE.fields.class_age)

        data = gjapp.data_collection['Class Data']
        vel = data['velocity_value']
        dist = data['est_dist_value']
        # only accept rows where both velocity and distance exist
        indices = where((vel != 0) & (vel is not None) & (dist != 0) & (dist is not None))
        if (indices[0].size > 0):
            slope = linear_slope(dist[indices], vel[indices])
            class_age.set(round(AGE_CONSTANT / slope, 8))     

    loaded_component_state.subscribe(_on_component_state_loaded) 

    if (GLOBAL_STATE.value.show_team_interface):
        StateEditor(Marker, COMPONENT_STATE, LOCAL_STATE, LOCAL_API)
    
    with solara.ColumnsResponsive(12, large=[4,8]):
        with rv.Col():
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineProfessionalData0.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.pro_dat0),
            )
            s = ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineProfessionalData1.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.pro_dat1),
                event_mc_callback = lambda event: mc_callback(event, LOCAL_STATE),
                state_view={'mc_score': get_multiple_choice(LOCAL_STATE, 'pro-dat1'), 'score_tag': 'pro-dat1'}
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineProfessionalData2.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.pro_dat2),
                event_mc_callback = lambda event: mc_callback(event, LOCAL_STATE),
                state_view={'mc_score': get_multiple_choice(LOCAL_STATE, 'pro-dat2'), 'score_tag': 'pro-dat2'}
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineProfessionalData3.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.pro_dat3),
                event_mc_callback = lambda event: mc_callback(event, LOCAL_STATE),
                state_view={'mc_score': get_multiple_choice(LOCAL_STATE, 'pro-dat3'), 'score_tag': 'pro-dat3'}
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineProfessionalData4.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.pro_dat4),
                event_mc_callback = lambda event: mc_callback(event, LOCAL_STATE),
                event_fr_callback = lambda event: fr_callback(event, LOCAL_STATE, lambda: LOCAL_API.put_story_state(GLOBAL_STATE, LOCAL_STATE)),
                state_view={
                    'mc_score': get_multiple_choice(LOCAL_STATE, 'pro-dat4'), 
                    'score_tag': 'pro-dat4',
                    'free_response': get_free_response(LOCAL_STATE, 'prodata-free-4'),
                    'mc_completed': LOCAL_STATE.value.question_completed("pro-dat4"),
                }
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineProfessionalData5.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.pro_dat5),
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineProfessionalData6.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.pro_dat6),
                event_mc_callback = lambda event: mc_callback(event, LOCAL_STATE),
                state_view={
                    'hst_age': HST_KEY_AGE, 
                    'class_age': COMPONENT_STATE.value.class_age,
                    'ages_within': COMPONENT_STATE.value.ages_within,
                    'allow_too_close_correct': COMPONENT_STATE.value.allow_too_close_correct,
                    'mc_score': get_multiple_choice(LOCAL_STATE, 'pro-dat6'), 
                    'score_tag': 'pro-dat6'
                }
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineProfessionalData7.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.pro_dat7),
                event_mc_callback = lambda event: mc_callback(event, LOCAL_STATE),
                event_fr_callback = lambda event: fr_callback(event, LOCAL_STATE, lambda: LOCAL_API.put_story_state(GLOBAL_STATE, LOCAL_STATE)),
                state_view={
                    'mc_score': get_multiple_choice(LOCAL_STATE, 'pro-dat7'), 
                    'score_tag': 'pro-dat7',
                    'free_response': get_free_response(LOCAL_STATE, 'prodata-free-7'),
                    'mc_completed': LOCAL_STATE.value.question_completed("pro-dat7"),
                }                
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineProfessionalData8.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.pro_dat8),
                event_fr_callback = lambda event: fr_callback(event, LOCAL_STATE, lambda: LOCAL_API.put_story_state(GLOBAL_STATE, LOCAL_STATE)),
                state_view={
                    'free_response_a': get_free_response(LOCAL_STATE,'prodata-reflect-8a'),
                    'free_response_b': get_free_response(LOCAL_STATE,'prodata-reflect-8b'),
                    'free_response_c': get_free_response(LOCAL_STATE,'prodata-reflect-8c'),
                }
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineProfessionalData9.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.pro_dat9),
                event_mc_callback = lambda event: mc_callback(event, LOCAL_STATE),
                state_view={'mc_score': get_multiple_choice(LOCAL_STATE, 'pro-dat9'), 'score_tag': 'pro-dat9'}
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineStoryFinish.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.sto_fin1),
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineStoryFinish2.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.sto_fin2),
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineStoryFinish3.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.sto_fin3),
            )
        
        with rv.Col(class_="no-padding"):
            with solara.Columns([3,9], classes=["no-padding"]):
                with rv.Col(class_="no-padding"):
                    # TODO: LayerToggle should refresh when the data changes
                    LayerToggle(viewer, names={
                        "Class Data": "Class Data",
                        HUBBLE_1929_DATA_LABEL: "Hubble 1929 Data",
                        HUBBLE_KEY_DATA_LABEL: "HST Key Project 2001 Data"
                    })
                with rv.Col(class_="no-padding"):
                    ViewerLayout(viewer)
