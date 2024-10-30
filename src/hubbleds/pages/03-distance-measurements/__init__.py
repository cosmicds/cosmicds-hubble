import solara


from reacton import ipyvuetify as rv
import solara.lab
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
    models_to_glue_data,
    _add_or_update_data, _add_link,
    subset_by_label
    )

from hubbleds.widgets.distance_tool.distance_tool import DistanceTool
from ...viewers.hubble_dotplot import HubbleDotPlotView, HubbleDotPlotViewer
from .component_state import COMPONENT_STATE, Marker

from numpy import asarray
import astropy.units as u

from pathlib import Path
from typing import List, Tuple, cast
from hubbleds.utils import sync_reactives

from hubbleds.example_measurement_helpers import (
    create_example_subsets,
    link_example_seed_and_measurements,
    _update_second_example_measurement,
    link_seed_data
)


GUIDELINE_ROOT = Path(__file__).parent / "guidelines"

logger = setup_logger("STAGE3")

def update_second_example_measurement():
    example_measurements = Ref(LOCAL_STATE.fields.example_measurements)
    if len(example_measurements.value) < 2:
        logger.info('No second example measurement to update')
        return
    
    changed, updated = _update_second_example_measurement(example_measurements.value)
    logger.info('Updating second example measurement')
    
    if changed != '':
        logger.info(f'\t\t setting example_measurements: {changed}')
        example_measurements.set([example_measurements.value[0], updated])
    else:
        logger.info('\t\t no changes for second measurement')

@solara.component
def DistanceToolComponent(galaxy, show_ruler, angular_size_callback, ruler_count_callback, use_guard, bad_measurement_callback, brightness_callback, reset_canvas):
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
    
    def _reset_canvas():
        logger.info('resetting canvas')
        widget = cast(DistanceTool,solara.get_widget(tool))
        widget.reset_canvas()
    
    
    solara.use_effect(_reset_canvas, [reset_canvas])

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
        
        def update_brightness(change):
            brightness_callback(change["new"])
            
        widget.observe(update_brightness, ["brightness"])

    solara.use_effect(_define_callbacks, [])
    
    

@solara.component
def Page():
    solara.Title("HubbleDS")
    
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
        res = LOCAL_API.put_stage_state(GLOBAL_STATE, LOCAL_STATE, COMPONENT_STATE)
        if res:
            logger.info("Wrote component state for stage 3 to database.")
        else:
            logger.info("Did not write component state for stage 3 to database.")

    solara.lab.use_task(_write_component_state, dependencies=[COMPONENT_STATE.value])
    
    
    def _glue_setup() -> JupyterApplication:
        gjapp = gjapp = JupyterApplication(
            GLOBAL_STATE.value.glue_data_collection, GLOBAL_STATE.value.glue_session
        )
        
        # Get the example seed data
        if EXAMPLE_GALAXY_SEED_DATA not in gjapp.data_collection:
            example_seed_data = LOCAL_API.get_example_seed_measurement(LOCAL_STATE, which = 'both')
            data = Data(label=EXAMPLE_GALAXY_SEED_DATA, **{k: asarray([r[k] for r in example_seed_data]) for k in example_seed_data[0].keys()})
            gjapp.data_collection.append(data)
            
            # create 'first measurement' and 'second measurement' datasets
            # create_measurement_subsets(gjapp, data)
            first = Data(label = EXAMPLE_GALAXY_SEED_DATA + '_first', 
                         **{k: asarray([r[k] for r in example_seed_data if r['measurement_number'] == 'first'])
                            for k in example_seed_data[0].keys()}
                            )
            first.style.color = "#C94456"
            gjapp.data_collection.append(first)
            second = Data(label = EXAMPLE_GALAXY_SEED_DATA + '_second', 
                         **{k: asarray([r[k] for r in example_seed_data if r['measurement_number'] == 'second'])
                            for k in example_seed_data[0].keys()}
                            )
            second.style.color = "#4449C9"
            gjapp.data_collection.append(second)
            
            link_seed_data(gjapp)
        
        return gjapp
    
    
    gjapp = solara.use_memo(_glue_setup)
    
    def add_or_update_data(data):
        return _add_or_update_data(gjapp, data)
    
    def add_link(from_dc_name, from_att, to_dc_name, to_att):
        _add_link(gjapp, from_dc_name, from_att, to_dc_name, to_att)
    
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
    
    def _initialize_state():
        if (not loaded_component_state.value) or (not LOCAL_STATE.value.measurements_loaded):
            return

        logger.info('Initializing state')
        
        if COMPONENT_STATE.value.current_step >= Marker.cho_row1:
            logger.info('Setting selected example galaxy')
            selected_example_galaxy = Ref(COMPONENT_STATE.fields.selected_example_galaxy)
            if len(LOCAL_STATE.value.example_measurements) > 0:
                logger.info('Setting selected example galaxy')
                if COMPONENT_STATE.value.current_step_at_or_after(Marker.ang_siz2):
                    num = 1 if COMPONENT_STATE.value.current_step_at_or_after(Marker.dot_seq5) else 0
                    selected_example_galaxy.set(LOCAL_STATE.value.example_measurements[num].galaxy.model_dump(exclude={'spectrum'}))
                    logger.info(f'Selected example galaxy on init: {selected_example_galaxy.value}')
        
        angular_sizes_total = 0
        for measurement in LOCAL_STATE.value.measurements:
            if measurement.ang_size_value is not None:
                angular_sizes_total += 1
        if COMPONENT_STATE.value.angular_sizes_total != angular_sizes_total:
            Ref(COMPONENT_STATE.fields.angular_sizes_total).set(angular_sizes_total)
        
        example_angular_sizes_total = 0
        for measurement in LOCAL_STATE.value.example_measurements:
            if measurement.ang_size_value is not None:
                example_angular_sizes_total += 1
        if COMPONENT_STATE.value.example_angular_sizes_total != example_angular_sizes_total:
            Ref(COMPONENT_STATE.fields.example_angular_sizes_total).set(example_angular_sizes_total)
    
    solara.use_memo(_initialize_state, dependencies=[loaded_component_state, Ref(LOCAL_STATE.fields.measurements_loaded)])
    # loaded_component_state.subscribe(_initialize_state)
    
    def _fill_data_points():
        dummy_measurements = LOCAL_API.get_dummy_data()
        for measurement in dummy_measurements:
            measurement.student_id = GLOBAL_STATE.value.student.id
        Ref(LOCAL_STATE.fields.measurements).set(dummy_measurements)
        Ref(COMPONENT_STATE.fields.angular_sizes_total).set(5)
        router.push("04-explore-data")

    def _fill_thetas():
        dummy_measurements = LOCAL_API.get_dummy_data()
        measurements = []
        for measurement in dummy_measurements:
            measurements.append(StudentMeasurement(student_id=GLOBAL_STATE.value.student.id,
                                                   obs_wave_value=measurement.obs_wave_value,
                                                   velocity_value=measurement.velocity_value,
                                                   ang_size_value=measurement.ang_size_value,
                                                   galaxy=measurement.galaxy))
        Ref(LOCAL_STATE.fields.measurements).set(measurements)
        Ref(COMPONENT_STATE.fields.angular_sizes_total).set(5)
    
    def add_example_measurements_to_glue():
        logger.info('in add_example_measurements_to_glue')
        if len(LOCAL_STATE.value.example_measurements) > 0:
            logger.info(f'has {len(LOCAL_STATE.value.example_measurements)} example measurements')
            example_measurements_glue = models_to_glue_data(LOCAL_STATE.value.example_measurements, label=EXAMPLE_GALAXY_MEASUREMENTS)
            example_measurements_glue.style.color = "red"
            create_example_subsets(gjapp, example_measurements_glue)
            
            use_this = add_or_update_data(example_measurements_glue)
            use_this.style.color = "red"

            link_example_seed_and_measurements(gjapp)
        else:
            logger.info('no example measurements yet')
        
    def _glue_data_setup():
        add_example_measurements_to_glue()
        update_second_example_measurement()
    
    solara.use_effect(_glue_data_setup, dependencies=[Ref(LOCAL_STATE.fields.measurements_loaded)])

    with solara.Row():
        with solara.Column():
            StateEditor(Marker, COMPONENT_STATE, LOCAL_STATE, LOCAL_API, show_all=True)
        # with solara.Column():
        #     solara.Button(label="Shortcut: Fill in distance data & Go to Stage 4", on_click=_fill_data_points)
    # StateEditor(Marker, cast(solara.Reactive[BaseState],COMPONENT_STATE), LOCAL_STATE, LOCAL_API, show_all=False)
    

    def put_measurements(samples):
        if samples:
            LOCAL_API.put_sample_measurements(GLOBAL_STATE, LOCAL_STATE)
        else:
            LOCAL_API.put_measurements(GLOBAL_STATE, LOCAL_STATE)
            
    def _update_angular_size(update_example: bool, galaxy, angular_size, count, meas_num = 'first'):
        # if bool(galaxy) and angular_size is not None:
        arcsec_value = int(angular_size.to(u.arcsec).value)
        if update_example:
            index = LOCAL_STATE.value.get_example_measurement_index(galaxy["id"], measurement_number=meas_num)
            if index is not None:
                measurements = LOCAL_STATE.value.example_measurements
                measurement = Ref(LOCAL_STATE.fields.example_measurements[index])
                measurement.set(
                    measurement.value.model_copy(
                        update={
                            "ang_size_value": arcsec_value
                            }
                        )
                )
                measurements[index] = measurement.value
                Ref(LOCAL_STATE.fields.example_measurements).set(measurements)
            else:
                raise ValueError(f"Could not find measurement for galaxy {galaxy['id']}")
        else:
            index = LOCAL_STATE.value.get_measurement_index(galaxy["id"])
            if index is not None:
                measurements = LOCAL_STATE.value.measurements
                measurement = Ref(LOCAL_STATE.fields.measurements[index])
                measurement.set(
                    measurement.value.model_copy(
                        update={
                            "ang_size_value": arcsec_value
                            }
                        )
                )
                measurements[index] = measurement.value
                Ref(LOCAL_STATE.fields.measurements).set(measurements)
                count.set(count.value + 1)
            else:
                raise ValueError(f"Could not find measurement for galaxy {galaxy['id']}")
   
        
    @solara.lab.computed
    def use_second_measurement():
        return COMPONENT_STATE.value.current_step_at_or_after(Marker.dot_seq5)
        
            
    def _update_distance_measurement(update_example: bool, galaxy, theta, measurement_number = 'first'):
        # if bool(galaxy) and theta is not None:
        distance = distance_from_angular_size(theta)
        if update_example:
            index = LOCAL_STATE.value.get_example_measurement_index(galaxy["id"], measurement_number=measurement_number)
            if index is not None:
                measurements = LOCAL_STATE.value.example_measurements
                measurement = Ref(LOCAL_STATE.fields.example_measurements[index])
                measurement.set(
                    measurement.value.model_copy(
                        update={
                            "est_dist_value": distance
                            }
                        )
                )
                measurements[index] = measurement.value
                Ref(LOCAL_STATE.fields.example_measurements).set(measurements)
            else:
                raise ValueError(f"Could not find measurement for galaxy {galaxy['id']}")
        else:
            index = LOCAL_STATE.value.get_measurement_index(galaxy["id"])
            if index is not None:
                measurements = LOCAL_STATE.value.measurements
                measurement = Ref(LOCAL_STATE.fields.measurements[index])
                measurement.set(
                    measurement.value.model_copy(
                        update={
                            "est_dist_value": distance
                            }
                        )
                )
                measurements[index] = measurement.value
                Ref(LOCAL_STATE.fields.measurements).set(measurements)
            else:
                raise ValueError(f"Could not find measurement for galaxy {galaxy['id']}")
    
    ang_size_dotplot_range = solara.use_reactive([])
    dist_dotplot_range = solara.use_reactive([])
    fill_galaxy_pressed = solara.use_reactive(COMPONENT_STATE.value.distances_total >= 5)
    
    @solara.lab.computed
    def sync_dotplot_axes():
        return COMPONENT_STATE.value.current_step_between(Marker.dot_seq1, Marker.dot_seq4a)
    
    def setup_zoom_sync():
        
        sync_reactives(
            ang_size_dotplot_range,
            dist_dotplot_range,
            lambda ang: ([(DISTANCE_CONSTANT / a) for a in ang][::-1] if sync_dotplot_axes.value else None), # angular size to distance
            lambda dist: ([(DISTANCE_CONSTANT / d) for d in dist][::-1] if sync_dotplot_axes.value else None) # distance to angular size
        )
    
    solara.use_effect(setup_zoom_sync, dependencies = [])
    
    reset_canvas = solara.use_reactive(1) # increment to reset canvas
    def _on_marker_updated(marker_new, marker_old):
        # logger.info(f"Marker updated from {marker_old} to {marker_new}")
        if marker_old == Marker.est_dis3:
            _distance_cb(COMPONENT_STATE.value.meas_theta)
            Ref(COMPONENT_STATE.fields.fill_est_dist_values).set(True)
        
        if marker_new == Marker.dot_seq5:
            # clear the canvas before we get to the second measurement. 
            reset_canvas.set(reset_canvas.value + 1)
            
            
        
    
    Ref(COMPONENT_STATE.fields.current_step).subscribe_change(_on_marker_updated)

    @solara.lab.computed
    def example_galaxy_measurement_number():
        if use_second_measurement.value:
            return 'second'
        else:
            return 'first'

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
                event_next_callback=lambda _: transition_to(COMPONENT_STATE, Marker.dot_seq5b), #
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq5),
                event_force_transition=lambda _: transition_to(COMPONENT_STATE, Marker.rep_rem1),
            )
            # the 2nd measurement
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineDotplotSeq5b.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq5b),
            )

        with rv.Col():
            def show_ruler_range(marker):
                COMPONENT_STATE.value.show_ruler = Marker.is_between(marker, Marker.ang_siz3, Marker.est_dis4) or \
                Marker.is_between(marker, Marker.dot_seq5b, Marker.last())
            
            current_step = Ref(COMPONENT_STATE.fields.current_step)
            current_step.subscribe(show_ruler_range)

            @solara.lab.computed
            def on_example_galaxy_marker():
                return COMPONENT_STATE.value.current_step <= Marker.dot_seq5c

            @solara.lab.computed
            def current_galaxy():
                if on_example_galaxy_marker.value:
                    return COMPONENT_STATE.value.selected_example_galaxy
                else:
                    return COMPONENT_STATE.value.selected_galaxy

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
                _update_angular_size(on_example_galaxy_marker.value, current_galaxy.value, angle, count, example_galaxy_measurement_number.value)
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
                auto_fill_distance = (
                    COMPONENT_STATE.value.current_step_between(Marker.est_dis4, Marker.dot_seq5c) 
                    or COMPONENT_STATE.value.current_step >= Marker.fil_rem1
                    or fill_galaxy_pressed.value
                )
                # the above, but if the student goes back, the distance should update if the distance is already set.
                if on_example_galaxy_marker.value:
                    index = LOCAL_STATE.value.get_example_measurement_index(current_galaxy.value["id"], measurement_number=example_galaxy_measurement_number.value)
                    logger.info("============== auto_fill_distance ===============")
                    logger.info(f'index: {index}')
                    if index is not None and LOCAL_STATE.value.example_measurements[index].est_dist_value is not None:
                        logger.info("autofill the distance")
                        auto_fill_distance = True
                if auto_fill_distance:
                    _distance_cb(angle.to(u.arcsec).value)
            
            def _bad_measurement_cb():
                bad_measurement = Ref(COMPONENT_STATE.fields.bad_measurement)
                bad_measurement.set(True)
                
            
            def _distance_cb(theta):
                """
                Callback for when the distance is estimated. This function
                updates the distance of the galaxy in the data model and
                puts the measurements in the database.
                """
                logger.info(f'_distance_cb. example: {on_example_galaxy_marker.value}')
                _update_distance_measurement(on_example_galaxy_marker.value, current_galaxy.value, theta, example_galaxy_measurement_number.value)
                put_measurements(samples=on_example_galaxy_marker.value)

            def _get_ruler_clicks_cb(count):
                ruler_click_count = Ref(COMPONENT_STATE.fields.ruler_click_count)
                ruler_click_count.set(count)
            
            # solara.Button("Reset Canvas", on_click=lambda: reset_canvas.set(reset_canvas.value + 1))
            DistanceToolComponent(
                galaxy=current_galaxy.value,
                show_ruler=COMPONENT_STATE.value.show_ruler,
                angular_size_callback=_ang_size_cb,
                ruler_count_callback=_get_ruler_clicks_cb,
                bad_measurement_callback=_bad_measurement_cb,
                use_guard=True,
                brightness_callback=lambda b: logger.info(f'Update Brightness: {b}'),
                reset_canvas=reset_canvas.value
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
                    "fill_values": COMPONENT_STATE.value.fill_est_dist_values
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
            # the 2nd measurement
            ScaffoldAlert(
                # TODO This will need to be wired up once table is implemented
                GUIDELINE_ROOT / "GuidelineDotplotSeq5a.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq5a),
            )
            # the 2nd measurement
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineDotplotSeq5c.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq5c),
            )
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
            # if COMPONENT_STATE.value.is_current_step(Marker.rep_rem1):
            #     solara.Button(label="Shortcut: Fill Angular Size Measurements", on_click=_fill_thetas)
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
                        logger.info("\n ======= Not all galaxies have angular sizes ======= \n")
                    for measurement in dataset:
                        if measurement.galaxy is not None and measurement.ang_size_value is not None:
                            count += 1
                            _update_distance_measurement(False, measurement.galaxy.model_dump(), measurement.ang_size_value)
                        elif measurement.ang_size_value is None:
                            logger.info(f"Galaxy {measurement.galaxy_id} has no angular size")
                    logger.info(f"fill_galaxy_distances: Filled {count} distances")
                    put_measurements(samples=False)
                    distances_total.set(count)
                    fill_galaxy_pressed.set(True)

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

            if COMPONENT_STATE.value.current_step < Marker.rep_rem1:
                def update_example_galaxy(galaxy):
                    flag = galaxy.get("value", True)
                    value = galaxy["item"]["galaxy"] if flag else None
                    selected_example_galaxy = Ref(COMPONENT_STATE.fields.selected_example_galaxy)
                    logger.info(f"selected_example_galaxy: {value}")
                    selected_example_galaxy.set(value)
                    if COMPONENT_STATE.value.is_current_step(Marker.cho_row1):
                        transition_to(COMPONENT_STATE, Marker.ang_siz2)
                
                @solara.lab.computed
                def selected_example_galaxy_index() -> list:
                    if COMPONENT_STATE.value.selected_example_galaxy is None:
                        return []
                    if 'id' not in COMPONENT_STATE.value.selected_example_galaxy:
                        return []
                    return [0]
                
                @solara.lab.computed
                def example_galaxy_data():
                    if use_second_measurement.value:
                        return [
                            x.dict() for x in LOCAL_STATE.value.example_measurements if x.measurement_number == 'second'
                        ]
                    else:
                        return [
                            x.dict() for x in LOCAL_STATE.value.example_measurements if x.measurement_number == 'first'
                        ]
                
                with solara.Card('REMOVE', style={'background-color': 'var(--warning-dark)'} ):
                    solara.Text(f"selected example galaxy {selected_example_galaxy_index.value}")
                    solara.Text(f"selected example galaxy {COMPONENT_STATE.value.selected_example_galaxy}")
                    DataTable(title="Example Measurements",
                            headers=common_headers + [{ "text": "Measurement Number", "value": "measurement_number" }], 
                            items=[x.model_dump() for x in LOCAL_STATE.value.example_measurements])
                
                DataTable(
                    title="Example Galaxy",
                    headers=common_headers + [{ "text": "Measurement Number", "value": "measurement_number" }], 
                    items=example_galaxy_data.value,
                    show_select=True,
                    selected_indices=selected_example_galaxy_index.value,
                    event_on_row_selected=update_example_galaxy
                )

            else:
                def update_galaxy(galaxy):
                    flag = galaxy.get("value", True)
                    value = galaxy["item"]["galaxy"] if flag else None
                    selected_galaxy = Ref(COMPONENT_STATE.fields.selected_galaxy)
                    selected_galaxy.set(value)
                
                @solara.lab.computed
                def selected_galaxy_index():
                    try:
                        return [LOCAL_STATE.value.get_measurement_index(COMPONENT_STATE.value.selected_galaxy["id"])]
                    except:
                        return []

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
                        "selected_indices": selected_galaxy_index.value,
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

                
                
                
                def set_angular_size_line(points):
                    logger.info("Called set_angular_size_line")
                    angular_size_line = Ref(COMPONENT_STATE.fields.angular_size_line)
                    if len(points.xs) > 0:
                        logger.info(f"Setting angular size line with {points.xs}")
                        distance = points.xs[0]
                        angular_size = DISTANCE_CONSTANT / distance
                        angular_size_line.set(angular_size)
                
                def set_distance_line(points):
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
                
                if COMPONENT_STATE.value.current_step_between(Marker.dot_seq1, Marker.ang_siz5a):
                    ignore = []
                    if EXAMPLE_GALAXY_MEASUREMENTS in gjapp.data_collection:
                        ignore = [gjapp.data_collection[EXAMPLE_GALAXY_MEASUREMENTS]]
                        if COMPONENT_STATE.value.current_step_at_or_before(Marker.dot_seq5):
                            second = subset_by_label(ignore[0], 'second measurement')
                            if second is not None:
                                ignore.append(second)
                        else:
                            first = subset_by_label(ignore[0], 'first measurement')
                            if first is not None:
                                ignore.append(first)
                    
                    
                    if EXAMPLE_GALAXY_MEASUREMENTS in gjapp.data_collection:
                        DotplotViewer(gjapp, 
                                        data = [
                                            gjapp.data_collection[EXAMPLE_GALAXY_MEASUREMENTS],
                                            gjapp.data_collection[EXAMPLE_GALAXY_SEED_DATA + '_first']
                                            ],
                                            title="Distance",
                                            component_id="est_dist_value",
                                            vertical_line_visible=show_dotplot_lines,
                                            line_marker_at=Ref(COMPONENT_STATE.fields.distance_line),
                                            on_click_callback=set_angular_size_line,
                                            unit="Mpc",
                                            x_label="Distance (Mpc)",
                                            y_label="Number",
                                            zorder=[5,1],
                                            x_bounds=dist_dotplot_range,
                                            hide_layers=ignore
                                            )
                        if COMPONENT_STATE.value.current_step_at_or_after(Marker.dot_seq4):
                            DotplotViewer(gjapp, 
                                            data = [
                                                gjapp.data_collection[EXAMPLE_GALAXY_MEASUREMENTS],
                                                gjapp.data_collection[EXAMPLE_GALAXY_SEED_DATA + '_first'] 
                                                ],
                                                title="Angular Size",
                                                component_id="ang_size_value",
                                                vertical_line_visible=show_dotplot_lines,
                                                line_marker_at=Ref(COMPONENT_STATE.fields.angular_size_line),
                                                on_click_callback=set_distance_line,
                                                unit="arcsec",
                                                x_label="Angular Size (arcsec)",
                                                y_label="Number",
                                                zorder=[5,1],
                                                x_bounds=ang_size_dotplot_range,
                                                hide_layers=ignore
                                                )
                    else:
                        # raise ValueError("Example galaxy measurements not found in glue data collection")
                        pass
