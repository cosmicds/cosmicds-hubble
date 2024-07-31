import solara


from reacton import ipyvuetify as rv
from solara.toestand import Ref

from glue_jupyter.app import JupyterApplication
from glue.core import Data

from cosmicds.components import (
    ScaffoldAlert,
    StateEditor, 
    ViewerLayout
    )
from cosmicds.logger import setup_logger
from cosmicds.state import BaseState, BaseLocalState


from hubbleds.base_component_state import (
    transition_next,
    transition_previous, 
    transition_to
    )
from hubbleds.components import (
    AngsizeDosDontsSlideshow, 
    DataTable,
    DotplotViewer,
    )

from hubbleds.data_management import *
from hubbleds.remote import LOCAL_API
from hubbleds.state import (
    GLOBAL_STATE, 
    LOCAL_STATE,
    StudentMeasurement, 
    get_multiple_choice,
    mc_callback
    )
from hubbleds.utils import (
    DISTANCE_CONSTANT, 
    GALAXY_FOV,
    distance_from_angular_size,
    measurement_list_to_glue_data
    )

from hubbleds.widgets.distance_tool.distance_tool import DistanceTool
from ...viewers.hubble_dotplot import HubbleDotPlotView, HubbleDotPlotViewer
from .component_state import COMPONENT_STATE, Marker

from numpy import asarray
import astropy.units as u

from pathlib import Path
from typing import List, Tuple, cast

GUIDELINE_ROOT = Path(__file__).parent / "guidelines"

logger = setup_logger("STAGE3")



@solara.component
def DistanceToolComponent(galaxy, show_ruler, angular_size_callback, ruler_count_callback, use_guard, bad_measurement_callback):
    tool = DistanceTool.element()

    def set_selected_galaxy():
        widget = solara.get_widget(tool)
        if galaxy:
            widget.measuring = False
            widget.go_to_location(galaxy["ra"], galaxy["decl"], fov=GALAXY_FOV)
        widget.measuring_allowed = bool(galaxy)

    solara.use_effect(set_selected_galaxy, [galaxy])

    def turn_ruler_on():
        widget =  solara.get_widget(tool)
        widget.show_ruler = show_ruler

    solara.use_effect(turn_ruler_on, [show_ruler])
    
    def turn_on_guard():
        widget = cast(DistanceTool,solara.get_widget(tool))
        if use_guard:
            widget.activate_guard()
        else:
            widget.deactivate_guard()
    
    solara.use_effect(turn_on_guard, [use_guard])
    

    def _define_callbacks():
        widget = cast(DistanceTool,solara.get_widget(tool))

        def update_angular_size(change):
            if widget.measuring:
                angle = change["new"]
                if not widget.bad_measurement:
                    angular_size_callback(angle)
                else:
                    bad_measurement_callback()

        widget.observe(update_angular_size, ["angular_size"])

        def get_ruler_click_count(change):
            count = change["new"]
            ruler_count_callback(count)

        widget.observe(get_ruler_click_count, ["ruler_click_count"])

    solara.use_effect(_define_callbacks, [])
    
    

@solara.component
def Page():
    
    # === Setup State Loading and Writing ===
    loaded_component_state = solara.use_reactive(False)
    router = solara.use_router()
    
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
    
    
    def _glue_setup() -> JupyterApplication:
        gjapp = gjapp = JupyterApplication(
            GLOBAL_STATE.value.glue_data_collection, GLOBAL_STATE.value.glue_session
        )
        
        # Get the example seed data
        if EXAMPLE_GALAXY_SEED_DATA not in gjapp.data_collection:
            example_seed_data = LOCAL_API.get_example_seed_measurement(LOCAL_STATE)
            data = Data(label=EXAMPLE_GALAXY_SEED_DATA, **{k: asarray([r[k] for r in example_seed_data]) for k in example_seed_data[0].keys()})
            gjapp.data_collection.append(data)
        
        return gjapp
    
    
    gjapp = solara.use_memo(_glue_setup)
    
    
    
    def _state_callback_setup():
        # We want to minimize duplicate state handling, but also keep the states
        #  independent. We'll set up observers for changes here so that they
        #  automatically keep the states in sync.
        # See Stage 1 for an example of how to do this manually.
        
        def _on_example_galaxy_selected(*args):
            if COMPONENT_STATE.value.is_current_step(Marker.cho_row1):
                transition_to(COMPONENT_STATE, Marker.ang_siz2)
        selected_example_galaxy = Ref(COMPONENT_STATE.fields.selected_example_galaxy)
        selected_example_galaxy.subscribe(_on_example_galaxy_selected)

        def _on_ruler_clicked_first_time(*args):
            if COMPONENT_STATE.value.is_current_step(Marker.ang_siz3) and COMPONENT_STATE.value.ruler_click_count == 1:
                transition_to(COMPONENT_STATE, Marker.ang_siz4)
        
        ruler_click_count = Ref(COMPONENT_STATE.fields.ruler_click_count)
        ruler_click_count.subscribe(_on_ruler_clicked_first_time)

        def _on_measurement_added(*args):
            if COMPONENT_STATE.value.is_current_step(Marker.ang_siz4) and COMPONENT_STATE.value.n_meas == 1:
                transition_to(COMPONENT_STATE, Marker.ang_siz5)
        
        n_meas = Ref(COMPONENT_STATE.fields.n_meas)
        n_meas.subscribe(_on_measurement_added)
        

        
    solara.use_memo(_state_callback_setup)

    if (GLOBAL_STATE.value.show_team_interface):
        StateEditor(Marker, cast(solara.Reactive[BaseState],COMPONENT_STATE), LOCAL_STATE, LOCAL_API)
    

    def put_measurements(samples):
        if samples:
            LOCAL_API.put_sample_measurements(GLOBAL_STATE, LOCAL_STATE)
        else:
            LOCAL_API.put_measurements(GLOBAL_STATE, LOCAL_STATE)
            
    def _update_angular_size(update_example: bool, galaxy, angular_size, count):
        # if bool(galaxy) and angular_size is not None:
        arcsec_value = int(angular_size.to(u.arcsec).value)
        if update_example:
            index = LOCAL_STATE.value.get_example_measurement_index(galaxy["id"])
            if index is not None:
                measurement = Ref(LOCAL_STATE.fields.example_measurements[index])
                measurement.set(
                    measurement.value.model_copy(
                        update={
                            "ang_size_value": arcsec_value
                            }
                        )
                )
            else:
                raise ValueError(f"Could not find measurement for galaxy {galaxy['id']}")
        else:
            index = LOCAL_STATE.value.get_measurement_index(galaxy["id"])
            if index is not None:
                measurement = Ref(LOCAL_STATE.fields.measurements[index])
                measurement.set(
                    measurement.value.model_copy(
                        update={
                            "ang_size_value": arcsec_value
                            }
                        )
                )
                count.set(count.value + 1)
            else:
                raise ValueError(f"Could not find measurement for galaxy {galaxy['id']}")
   
        
        
            
    def _update_distance_measurement(update_example: bool, galaxy, theta):
        # if bool(galaxy) and theta is not None:
        distance = distance_from_angular_size(theta)
        if update_example:
            print(galaxy)
            index = LOCAL_STATE.value.get_example_measurement_index(galaxy["id"])
            logger.info(f"Updating example galaxy {galaxy['id']} with distance {distance} with index {index}")
            if index is not None:
                measurement = Ref(LOCAL_STATE.fields.example_measurements[index])
                measurement.set(
                    measurement.value.model_copy(
                        update={
                            "est_dist_value": distance
                            }
                        )
                )
            else:
                raise ValueError(f"Could not find measurement for galaxy {galaxy['id']}")
        else:
            index = LOCAL_STATE.value.get_measurement_index(galaxy["id"])
            if index is not None:
                measurement = Ref(LOCAL_STATE.fields.measurements[index])
                measurement.set(
                    measurement.value.model_copy(
                        update={
                            "est_dist_value": distance
                            }
                        )
                )
            else:
                raise ValueError(f"Could not find measurement for galaxy {galaxy['id']}")
    
    

    with solara.ColumnsResponsive(12, large=[4,8]):
        with rv.Col():
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineAngsizeMeas1.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.ang_siz1),
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineAngsizeMeas2.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.ang_siz2),
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineAngsizeMeas2b.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.ang_siz2b),
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineAngsizeMeas3.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.ang_siz3),
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineAngsizeMeas4.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.ang_siz4),
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineAngsizeMeas5a.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.ang_siz5a),
                state_view={
                    "dosdonts_tutorial_opened": COMPONENT_STATE.value.dosdonts_tutorial_opened
                },
            )
            # This was skipped in voila version
            # ScaffoldAlert(
            #     GUIDELINE_ROOT / "GuidelineAngsizeMeas6.vue",
            #     event_next_callback=lambda _: transition_next(COMPONENT_STATE),
            #     event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
            #     can_advance=COMPONENT_STATE.value.can_transition(next=True),
            #     show=COMPONENT_STATE.value.is_current_step(Marker.ang_siz6),
            # )

            # NOTE: We are skipping the 2nd measurement for now
            # So we want to skip forward to rep_rem1.
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineDotplotSeq5.vue",
                # event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                event_next_callback=lambda _: transition_to(COMPONENT_STATE, Marker.rep_rem1), #
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq5),
            )
            # Not doing the 2nd measurement
            # ScaffoldAlert(
            #     # TODO This will need to be wired up once measuring tool is implemented
            #     GUIDELINE_ROOT / "GuidelineDotplotSeq5b.vue",
            #     event_next_callback=lambda _: transition_next(COMPONENT_STATE),
            #     event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
            #     can_advance=COMPONENT_STATE.value.can_transition(next=True),
            #     show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq5b),
            # )

        with rv.Col():
            def show_ruler_range(marker):
                COMPONENT_STATE.value.show_ruler = Marker.is_between(marker, Marker.ang_siz3, Marker.est_dis4) or \
                Marker.is_between(marker, Marker.rep_rem1, Marker.last())
            
            current_step = Ref(COMPONENT_STATE.fields.current_step)
            current_step.subscribe(show_ruler_range)

            @solara.lab.computed
            def on_example_galaxy_marker():
                return COMPONENT_STATE.value.current_step < Marker.rep_rem1

            @solara.lab.computed
            def current_galaxy():
                galaxy = COMPONENT_STATE.value.selected_galaxy
                example_galaxy = COMPONENT_STATE.value.selected_example_galaxy
                logger.info(f"Current galaxy: {example_galaxy if on_example_galaxy_marker.value else galaxy}")
                return example_galaxy if on_example_galaxy_marker.value else galaxy

            @solara.lab.computed
            def current_data():
                return LOCAL_STATE.value.example_measurements if on_example_galaxy_marker.value else LOCAL_STATE.value.measurements

            def _ang_size_cb(angle):
                """
                Callback for when the angular size is measured. This function
                updates the angular size of the galaxy in the data model and
                puts the measurements in the database.
                """
                data = current_data.value
                count = Ref(COMPONENT_STATE.fields.example_angular_sizes_total) if on_example_galaxy_marker.value else Ref(COMPONENT_STATE.fields.angular_sizes_total)
                _update_angular_size(on_example_galaxy_marker.value, current_galaxy.value, angle, count)
                put_measurements(samples=on_example_galaxy_marker.value)
                if on_example_galaxy_marker.value:
                    value = int(angle.to(u.arcsec).value)
                    meas_theta = Ref(COMPONENT_STATE.fields.meas_theta)
                    meas_theta.set(value)
                    n_meas = Ref(COMPONENT_STATE.fields.n_meas)
                    n_meas.set(COMPONENT_STATE.value.n_meas + 1)
                if COMPONENT_STATE.value.bad_measurement:
                    bad_measurement = Ref(COMPONENT_STATE.fields.bad_measurement)
                    bad_measurement.set(False)
            
            def _bad_measurement_cb():
                bad_measurement = Ref(COMPONENT_STATE.fields.bad_measurement)
                bad_measurement.set(True)
                
            
            def _distance_cb(theta):
                """
                Callback for when the distance is estimated. This function
                updates the distance of the galaxy in the data model and
                puts the measurements in the database.
                """
                _update_distance_measurement(on_example_galaxy_marker.value, current_galaxy.value, theta)
                print('_distance_cb. example:', on_example_galaxy_marker.value)
                put_measurements(samples=on_example_galaxy_marker.value)

            def _get_ruler_clicks_cb(count):
                ruler_click_count = Ref(COMPONENT_STATE.fields.ruler_click_count)
                ruler_click_count.set(count)

            DistanceToolComponent(
                galaxy=current_galaxy.value,
                show_ruler=COMPONENT_STATE.value.show_ruler,
                angular_size_callback=_ang_size_cb,
                ruler_count_callback=_get_ruler_clicks_cb,
                bad_measurement_callback=_bad_measurement_cb,
                use_guard=True
            )
            
            if COMPONENT_STATE.value.bad_measurement:
                solara.Error("This measurement seems to be too large/small. Make sure you are appropriately zoomed in on the galaxy and are measuring the full size.")

            with rv.Col(cols=6, offset=3):
                if COMPONENT_STATE.value.current_step_at_or_after(Marker.ang_siz5a):
                    dosdonts_tutorial_opened = Ref(COMPONENT_STATE.fields.dosdonts_tutorial_opened)
                    AngsizeDosDontsSlideshow(
                        event_on_dialog_opened=lambda *args: dosdonts_tutorial_opened.set(
                            True
                        )
                    )

    with solara.ColumnsResponsive(12, large=[4,8]):
        with rv.Col():
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineChooseRow1.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.cho_row1),
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineAngsizeMeas5.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.ang_siz5),
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineEstimateDistance1.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.est_dis1),
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineEstimateDistance2.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.est_dis2),
                state_view={
                    "distance_const": DISTANCE_CONSTANT
                },
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineEstimateDistance3.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.est_dis3),
                event_set_distance=_distance_cb,
                state_view={
                    "distance_const": DISTANCE_CONSTANT,
                    "meas_theta": COMPONENT_STATE.value.meas_theta,
                },
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineEstimateDistance4.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.est_dis4),
                state_view={
                    "distance_const": DISTANCE_CONSTANT,
                    "meas_theta": COMPONENT_STATE.value.meas_theta,
                },
            )
            # Not doing the 2nd measurement
            # ScaffoldAlert(
            #     # TODO This will need to be wired up once table is implemented
            #     GUIDELINE_ROOT / "GuidelineDotplotSeq5a.vue",
            #     event_next_callback=lambda _: transition_next(COMPONENT_STATE),
            #     event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
            #     can_advance=COMPONENT_STATE.value.can_transition(next=True),
            #     show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq5a),
            # )
            # Not doing the 2nd measurement
            # ScaffoldAlert(
            #     GUIDELINE_ROOT / "GuidelineDotplotSeq5c.vue",
            #     event_next_callback=lambda _: transition_next(COMPONENT_STATE),
            #     event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
            #     can_advance=COMPONENT_STATE.value.can_transition(next=True),
            #     show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq5c),
            # )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineRepeatRemainingGalaxies.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_to(COMPONENT_STATE, Marker.dot_seq5),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.rep_rem1),
                scroll_on_mount=False,
                state_view={
                    "angular_sizes_total": COMPONENT_STATE.value.angular_sizes_total,

                    # TODO: will need to fix this once we have an angular size measurement guard.
                    "bad_angsize": False
                }
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineFillRemainingGalaxies.vue",
                event_next_callback=lambda _: router.push("04-explore-data"),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.fil_rem1),
                state_view={
                    "distances_total": COMPONENT_STATE.value.distances_total
                }
            )

        with rv.Col():
            with rv.Card(class_="pa-0 ma-0", elevation=0):

                distances_total = Ref(COMPONENT_STATE.fields.distances_total)  

                def fill_galaxy_distances(): 
                    dataset = LOCAL_STATE.value.measurements
                    count = 0
                    has_ang_size = all(measurement.ang_size_value is not None for measurement in dataset)
                    if not has_ang_size:
                        print("\n ======= Not all galaxies have angular sizes ======= \n")
                    for measurement in dataset:
                        if measurement.galaxy is not None and measurement.ang_size_value is not None:
                            count += 1
                            _update_distance_measurement(False, measurement.galaxy.model_dump(), measurement.ang_size_value)
                        elif measurement.ang_size_value is None:
                            logger.info(f"Galaxy {measurement.galaxy_id} has no angular size")
                    print(f"Filled {count} distances")
                    put_measurements(samples=False)
                    distances_total.set(count)

                if (COMPONENT_STATE.value.current_step_at_or_after(Marker.fil_rem1) and GLOBAL_STATE.value.show_team_interface):
                    solara.Button("Fill Galaxy Distances", on_click=lambda: fill_galaxy_distances())


                common_headers = [
                    {
                        "text": "Galaxy Name",
                        "align": "start",
                        "sortable": False,
                        "value": "galaxy_id"
                    },
                    { "text": "&theta; (arcsec)", "value": "ang_size_value" },
                    { "text": "Distance (Mpc)", "value": "est_dist_value" },
                ]

            if COMPONENT_STATE.value.current_step_at_or_before(Marker.dot_seq5):
                def update_example_galaxy(galaxy):
                    flag = galaxy.get("value", True)
                    value = galaxy["item"]["galaxy"] if flag else None
                    selected_example_galaxy = Ref(COMPONENT_STATE.fields.selected_example_galaxy)
                    selected_example_galaxy.set(value)
                    if COMPONENT_STATE.value.is_current_step(Marker.cho_row1):
                        transition_to(COMPONENT_STATE, Marker.ang_siz2)

                @solara.lab.computed
                def example_table_kwargs():
                    ang_size_tot = COMPONENT_STATE.value.example_angular_sizes_total
                    tab = [e.model_dump(exclude={'galaxy': {'spectrum'}}) for e in LOCAL_STATE.value.example_measurements]
                    
                    return {
                        "title": "Example Galaxy",
                        "headers": common_headers, # + [{ "text": "Measurement Number", "value": "measurement_number" }], # we will be skipping the 2nd measurement for now
                        "items": tab,
                        "highlighted": False,  # TODO: Set the markers for this,
                        "event_on_row_selected": update_example_galaxy,
                        "show_select": True,
                    }

                DataTable(**example_table_kwargs.value)

            else:
                def update_galaxy(galaxy):
                    flag = galaxy.get("value", True)
                    value = galaxy["item"]["galaxy"] if flag else None
                    selected_galaxy = Ref(COMPONENT_STATE.fields.selected_galaxy)
                    selected_galaxy.set(value)

                @solara.lab.computed
                def table_kwargs():
                    ang_size_tot = COMPONENT_STATE.value.angular_sizes_total
                    table_data = [s.model_dump(exclude={'galaxy': {'spectrum'}, 'measurement_number':True}) for s in LOCAL_STATE.value.measurements]
                    return {
                        "title": "My Galaxies",
                        "headers": common_headers, # + [{ "text": "Measurement Number", "value": "measurement_number" }],
                        "items": table_data,
                        "highlighted": False,  # TODO: Set the markers for this,
                        "event_on_row_selected": update_galaxy,
                        "show_select": True,
                        "button_icon": "mdi-tape-measure",
                        "show_button": COMPONENT_STATE.value.current_step_at_or_after(Marker.fil_rem1),
                        "event_on_button_pressed": lambda _: fill_galaxy_distances()
                    }

                DataTable(**table_kwargs.value)

    with solara.ColumnsResponsive(12, large=[4,8]):
        with rv.Col():
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineDotplotSeq1.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq1),
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineDotplotSeq2.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq2),
                event_mc_callback=lambda event: mc_callback(event = event, local_state = LOCAL_STATE),
                state_view={'mc_score': get_multiple_choice(LOCAL_STATE, 'ang_meas_consensus'), 'score_tag': 'ang_meas_consensus'}
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineDotplotSeq3.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq3),
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineDotplotSeq4.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq4),
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineDotplotSeq4a.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq4a),
                event_mc_callback=lambda event: mc_callback(event = event, local_state = LOCAL_STATE),
                state_view={'mc_score': get_multiple_choice(LOCAL_STATE, 'ang_meas_dist_relation'), 'score_tag': 'ang_meas_dist_relation'}
            )
            # Not doing the 2nd measurement #dot_seq6 is comparison of 1st and 2nd measurement
            # ScaffoldAlert(
            #     GUIDELINE_ROOT / "GuidelineDotplotSeq6.vue",
            #     event_next_callback=lambda _: transition_next(COMPONENT_STATE),
            #     event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
            #     can_advance=COMPONENT_STATE.value.can_transition(next=True),
            #     show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq6),
            #     event_mc_callback=lambda event: mc_callback(event = event, local_state = LOCAL_STATE, callback=set_mc_scoring),
            #     state_view={'mc_score': get_multiple_choice(LOCAL_STATE, 'ang_meas_consensus_2'), 'score_tag': 'ang_meas_consensus_2'}
            # )
            # Not doing the 2nd measurement #dot_seq7 is transition to doing all galaxies. This is not dot_seq5
            # ScaffoldAlert(
            #     GUIDELINE_ROOT / "GuidelineDotplotSeq7.vue",
            #     event_next_callback=lambda _: transition_next(COMPONENT_STATE),
            #     event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
            #     can_advance=COMPONENT_STATE.value.can_transition(next=True),
            #     show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq7),
            # )

        with rv.Col():
            
            with rv.Card(class_="pa-0 ma-0", elevation=0):
                
                
                def add_link(from_dc_name, from_att, to_dc_name, to_att):
                    if isinstance(from_dc_name, Data):
                        from_dc = from_dc_name
                    else:
                        from_dc = gjapp.data_collection[from_dc_name]
                    
                    if isinstance(to_dc_name, Data):
                        to_dc = to_dc_name
                    else:
                        to_dc = gjapp.data_collection[to_dc_name]
                    gjapp.add_link(from_dc, from_att, to_dc, to_att)


                def add_example_measurements_to_glue():
                    if len(LOCAL_STATE.value.example_measurements) > 0:
                        example_measurements_glue = measurement_list_to_glue_data(LOCAL_STATE.value.example_measurements, label=EXAMPLE_GALAXY_MEASUREMENTS)
                        example_measurements_glue.style.color = "red"
                        if EXAMPLE_GALAXY_MEASUREMENTS in gjapp.data_collection:
                            existing = gjapp.data_collection[EXAMPLE_GALAXY_MEASUREMENTS]
                            existing.update_values_from_data(example_measurements_glue)
                            example_measurements_glue = existing
                        else:
                            gjapp.data_collection.append(example_measurements_glue)
                            example_measurements_glue = gjapp.data_collection[EXAMPLE_GALAXY_MEASUREMENTS]

                        egsd = gjapp.data_collection[EXAMPLE_GALAXY_SEED_DATA]
                        add_link(egsd, DB_ANGSIZE_FIELD, example_measurements_glue,"ang_size_value")
                        add_link(egsd, DB_DISTANCE_FIELD, example_measurements_glue,"est_dist_value")
                

                
                
                def set_angular_size_line(trace, points, selector):
                    logger.info("Called set_angular_size_line")
                    angular_size_line = Ref(COMPONENT_STATE.fields.angular_size_line)
                    if len(points.xs) > 0:
                        logger.info(f"Setting angular size line with {points.xs}")
                        distance = points.xs[0]
                        angular_size = DISTANCE_CONSTANT / distance
                        angular_size_line.set(angular_size)
                
                def set_distance_line(trace, points, selector):
                    logger.info("Called set_distance_line")
                    distance_line = Ref(COMPONENT_STATE.fields.distance_line)
                    if len(points.xs) > 0:
                        logger.info(f"Setting distance line with {points.xs}")
                        angular_size = points.xs[0]
                        distance = DISTANCE_CONSTANT / angular_size
                        distance_line.set(distance)
                
                
                
                show_dotplot_lines = Ref(COMPONENT_STATE.fields.show_dotplot_lines)
                if COMPONENT_STATE.value.current_step_at_or_after(Marker.dot_seq4a):
                    show_dotplot_lines.set(True)
                else:
                    show_dotplot_lines.set(False)
                
                if COMPONENT_STATE.value.current_step_between(Marker.dot_seq1, Marker.dot_seq5):
                    add_example_measurements_to_glue()
                    if EXAMPLE_GALAXY_MEASUREMENTS in gjapp.data_collection:
                        DotplotViewer(gjapp, 
                                        data = [
                                            gjapp.data_collection[EXAMPLE_GALAXY_SEED_DATA], 
                                            gjapp.data_collection[EXAMPLE_GALAXY_MEASUREMENTS]
                                            ],
                                            component_id="est_dist_value",
                                            vertical_line_visible=show_dotplot_lines,
                                            line_marker_at=Ref(COMPONENT_STATE.fields.distance_line),
                                            on_click_callback=set_angular_size_line,
                                            unit="Mpc",
                                            x_label="Distance (Mpc)",
                                            y_label="Number",
                                            )
                        if COMPONENT_STATE.value.current_step_at_or_after(Marker.dot_seq4a):
                            DotplotViewer(gjapp, 
                                            data = [
                                                gjapp.data_collection[EXAMPLE_GALAXY_SEED_DATA], 
                                                gjapp.data_collection[EXAMPLE_GALAXY_MEASUREMENTS]
                                                ],
                                                component_id="ang_size_value",
                                                vertical_line_visible=show_dotplot_lines,
                                                line_marker_at=Ref(COMPONENT_STATE.fields.angular_size_line),
                                                on_click_callback=set_distance_line,
                                                unit="arcsec",
                                                x_label="Angular Size (arcsec)",
                                                y_label="Number",
                                                )
                    else:
                        # raise ValueError("Example galaxy measurements not found in glue data collection")
                        pass
