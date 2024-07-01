from hubbleds.base_component_state import transition_next, transition_previous
import numpy as np
from pathlib import Path
import reacton.ipyvuetify as rv
import solara
from solara.toestand import Ref

from cosmicds.components import ScaffoldAlert
from hubbleds.components import HubbleExpUniverseSlideshow
from hubbleds.state import LOCAL_STATE, GLOBAL_STATE
from .component_state import COMPONENT_STATE, Marker
from hubbleds.remote import LOCAL_API
from hubbleds.utils import AGE_CONSTANT

from cosmicds.logger import setup_logger

logger = setup_logger("STAGE 4")

GUIDELINE_ROOT = Path(__file__).parent / "guidelines"


@solara.component
def Page():
    loaded_component_state = solara.use_reactive(False)

    async def _load_component_state():
        # Load stored component state from database, measurement data is
        # considered higher-level and is loaded when the story starts
        LOCAL_API.get_stage_state(GLOBAL_STATE, LOCAL_STATE, COMPONENT_STATE)

        # TODO: What else to we need to do here?
        logger.info("Finished loading component state for stage 4.")
        loaded_component_state.set(True)

    solara.lab.use_task(_load_component_state)

    async def _write_local_global_states():
        # Listen for changes in the states and write them to the database
        LOCAL_API.put_story_state(GLOBAL_STATE, LOCAL_STATE)

        logger.info("Wrote state to database.")

    solara.lab.use_task(_write_local_global_states, dependencies=[GLOBAL_STATE.value, LOCAL_STATE.value])

    async def _write_component_state():
        if not loaded_component_state.value:
            return

        # Listen for changes in the states and write them to the database
        LOCAL_API.put_stage_state(GLOBAL_STATE, LOCAL_STATE, COMPONENT_STATE)

        logger.info("Wrote component state to database.")

    solara.lab.use_task(_write_component_state, dependencies=[COMPONENT_STATE.value])

    class_plot_data = solara.use_reactive([])
    async def _load_class_data():
        class_measurements = LOCAL_API.get_class_measurements(GLOBAL_STATE, LOCAL_STATE)
        measurements = Ref(LOCAL_STATE.fields.class_measurements)
        student_ids = Ref(LOCAL_STATE.fields.stage_4_class_data_students)
        if class_measurements and not student_ids.value:
            ids = [id for id in np.unique([m.student_id for m in class_measurements])]
            student_ids.set(ids)
        measurements.set(class_measurements)

        class_data_points = [m for m in class_measurements if m.student_id in student_ids.value] 
        class_plot_data.set(class_data_points)

    solara.lab.use_task(_load_class_data)

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
                    # TODO: Update these once real values are hooked up
                    "hypgal_distance": 100,
                    "hypval_velocity": 8000,
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
                    # TODO: Update these once real values are hooked up
                    "hypgal_distance": 100,
                    "hypval_velocity": 8000,
                }
            )

        with rv.Col():
            pass

    with solara.ColumnsResponsive(12, large=[4,8]):
        with rv.Col():
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineTrendsDataMC1.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.tre_dat1),
                # event_mc_callback=lambda event: mc_callback(event=event, local_state=LOCAL_STATE, callback=set_mc_scoring)
                # state_view = { "mc_score": mc_serialize_score(mc_scoring.get("tre-dat-mc1")), "score_tag": "tre-dat-mc1" }
            )
            ScaffoldAlert(
                # TODO: This will need to be wired up once viewer is implemented
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
                # event_mc_callback=lambda event: mc_callback(event=event, local_state=LOCAL_STATE, callback=set_mc_scoring),
                # state_view={'mc_score': mc_serialize_score(mc_scoring.get('tre-dat-mc3')), 'score_tag': 'tre-dat-mc3'}
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineRelationshipsVelDistMC.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.rel_vel1),
                # event_mc_callback=lambda event: mc_callback(event = event, local_state = LOCAL_STATE, callback=set_mc_scoring),
                # state_view={'mc_score': mc_serialize_score(mc_scoring.get('galaxy-trend')), 'score_tag': 'galaxy-trend'} 
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineTrendLines1.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.tre_lin1),               
            )
            ScaffoldAlert(
                # TODO This will need to be wired up once linedraw tool is implemented
                GUIDELINE_ROOT / "GuidelineTrendLinesDraw2.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.tre_lin2),
            )
            ScaffoldAlert(
                # TODO This will need to be wired up once best fit line tool is implemented
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
                state_view={
                    "hubble_slideshow_finished": COMPONENT_STATE.value.hubble_slideshow_finished
                }, 
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
                # TODO - add free response functionality
                GUIDELINE_ROOT / "GuidelineShortcomingsEstReflect1.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.sho_est1),
                # event_fr_callback=lambda event: fr_callback(event=event, local_state=LOCAL_STATE),
                # state_view={
                #     'free_response_a': get_free_response(LOCAL_STATE.free_responses,'shortcoming-1'),
                #     'free_response_b': get_free_response(LOCAL_STATE.free_responses,'shortcoming-2'),
                #     'free_response_c': get_free_response(LOCAL_STATE.free_responses,'other-shortcomings'),
                # }
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineShortcomingsEst2.vue",
                # TODO: event_next_callback should go to next stage but I don't know how to set that up.
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.sho_est2),
            )

        with rv.Col():
            with rv.Col(cols=10, offset=1):
                if COMPONENT_STATE.value.current_step.value > Marker.rel_vel1.value:
                    slideshow_finished = Ref(COMPONENT_STATE.fields.hubble_slideshow_finished)
                    HubbleExpUniverseSlideshow(
                        event_on_slideshow_finished=lambda _: slideshow_finished.set(True),
                        dialog=COMPONENT_STATE.value.show_hubble_slideshow_dialog,
                        step=COMPONENT_STATE.value.hubble_slideshow_state.step,
                        max_step_completed=COMPONENT_STATE.value.hubble_slideshow_state.max_step_completed,
                    )
     
