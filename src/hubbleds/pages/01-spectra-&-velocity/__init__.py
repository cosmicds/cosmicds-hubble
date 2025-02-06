import solara
from solara.lab import computed
from hubbleds.state import LOCAL_STATE, GLOBAL_STATE, get_multiple_choice, mc_callback
from .component_state import COMPONENT_STATE, Marker
from hubbleds.remote import LOCAL_API
from glue_jupyter import JupyterApplication
import asyncio
from pathlib import Path
from cosmicds.components import ScaffoldAlert, StateEditor
import reacton.ipyvuetify as rv
from hubbleds.base_component_state import (
    transition_to,
    transition_previous,
    transition_next,
)
from hubbleds.components import (
    SelectionTool,
    DataTable,
    DopplerSlideshow,
    SpectrumViewer,
    SpectrumSlideshow,
    DotplotViewer,
    ReflectVelocitySlideshow,
    DotplotTutorialSlideshow,
)
from hubbleds.state import GalaxyData, StudentMeasurement
from hubbleds.viewer_marker_colors import MY_DATA_COLOR, MY_DATA_COLOR_NAME, LIGHT_GENERIC_COLOR, GENERIC_COLOR

# from solara.lab import Ref
from solara.toestand import Ref
from cosmicds.logger import setup_logger
from ...data_management import (
    EXAMPLE_GALAXY_SEED_DATA,
    DB_VELOCITY_FIELD,
    EXAMPLE_GALAXY_MEASUREMENTS,
    DB_MEASWAVE_FIELD,
)
import numpy as np
from glue.core import Data
from hubbleds.utils import (
    models_to_glue_data, 
    velocity_from_wavelengths, 
    v2w, w2v, sync_reactives,
    _add_or_update_data,
    _add_link,
    subset_by_label
)
from hubbleds.example_measurement_helpers import (
    create_example_subsets,
    create_measurement_subsets,
    link_example_seed_and_measurements,
    link_seed_data,
    _update_second_example_measurement
)

logger = setup_logger("STAGE")

GUIDELINE_ROOT = Path(__file__).parent / "guidelines"

EXAMPLE_GALAXY_MEASUREMENTS_FIRST = EXAMPLE_GALAXY_MEASUREMENTS + '_first'
EXAMPLE_GALAXY_MEASUREMENTS_SECOND = EXAMPLE_GALAXY_MEASUREMENTS + '_second'

def is_wavelength_poorly_measured(measwave, restwave, z, tolerance = 0.5):
    z_meas =  (measwave - restwave) / restwave
    fractional_difference = (((z_meas - z) / z)** 2)**0.5
    return fractional_difference > tolerance

@solara.component
def Page():
    solara.Title("HubbleDS")
    logger.info("Rendering Stage 1: Spectra & Velocity")
    loaded_component_state = solara.use_reactive(False)
    router = solara.use_router()

    async def _load_component_state():
        # Load stored component state from database, measurement data is
        #   considered higher-level and is loaded when the story starts.
        LOCAL_API.get_stage_state(GLOBAL_STATE, LOCAL_STATE, COMPONENT_STATE)

        total_galaxies = Ref(COMPONENT_STATE.fields.total_galaxies)

        if len(LOCAL_STATE.value.measurements) != total_galaxies.value:
            logger.error(
                "Detected mismatch between stored measurements and current "
                "recorded number of galaxies."
            )
            total_galaxies.set(len(LOCAL_STATE.value.measurements))

        logger.info("Finished loading component state.")
        loaded_component_state.set(True)

    solara.lab.use_task(_load_component_state)
    # solara.use_memo(_load_component_state)

    async def _write_component_state():
        if not loaded_component_state.value:
            return

        # Listen for changes in the states and write them to the database
        res = LOCAL_API.put_stage_state(GLOBAL_STATE, LOCAL_STATE, COMPONENT_STATE)
        if res:
            logger.info("Wrote component state to database.")
        else:
            logger.info("Did not write component state to database.")

    solara.lab.use_task(_write_component_state, dependencies=[COMPONENT_STATE.value])

    def _glue_setup() -> JupyterApplication:
        # NOTE: use_memo has to be part of the main page render. Including it
        #  in a conditional will result in an error.
        gjapp = JupyterApplication(
            GLOBAL_STATE.value.glue_data_collection, GLOBAL_STATE.value.glue_session
        )

        if EXAMPLE_GALAXY_SEED_DATA not in gjapp.data_collection:
            example_seed_data = LOCAL_API.get_example_seed_measurement(LOCAL_STATE, which='both')
            
            data = Data(
                label=EXAMPLE_GALAXY_SEED_DATA,
                **{
                    k: np.asarray([r[k] for r in example_seed_data])
                    for k in example_seed_data[0].keys()
                }
            )
            gjapp.data_collection.append(data)
            # create 'first measurement' and 'second measurement' datasets
            # create_measurement_subsets(gjapp, data)
            first = Data(label = EXAMPLE_GALAXY_SEED_DATA + '_first', 
                         **{k: np.asarray([r[k] for r in example_seed_data if r['measurement_number'] == 'first'])
                            for k in example_seed_data[0].keys()}
                            )
            first.style.color = GENERIC_COLOR
            gjapp.data_collection.append(first)
            second = Data(label = EXAMPLE_GALAXY_SEED_DATA + '_second', 
                         **{k: np.asarray([r[k] for r in example_seed_data if r['measurement_number'] == 'second'])
                            for k in example_seed_data[0].keys()}
                            )
            second.style.color = GENERIC_COLOR
            gjapp.data_collection.append(second)
            
            link_seed_data(gjapp)
        
        return gjapp

    gjapp = solara.use_memo(_glue_setup)

    def add_or_update_data(data: Data):
        return _add_or_update_data(gjapp, data)

    def _state_callback_setup():
        # We want to minize duplicate state handling, but also keep the states
        #  independent. We'll set up observers for changes here so that they
        #  automatically keep the states in sync.
        measurements = Ref(LOCAL_STATE.fields.measurements)
        total_galaxies = Ref(COMPONENT_STATE.fields.total_galaxies)
        measurements.subscribe_change(
            lambda *args: total_galaxies.set(len(measurements.value))
        )

    solara.use_memo(_state_callback_setup)

    @computed
    def use_second_measurement():
        return COMPONENT_STATE.value.current_step.value >= Marker.rem_vel1.value

    @computed
    def selected_example_measurement():
        return LOCAL_STATE.value.get_example_measurement(
            COMPONENT_STATE.value.selected_example_galaxy,
            measurement_number='second' if use_second_measurement.value else 'first')

    @computed
    def selected_measurement():
        return LOCAL_STATE.value.get_measurement(COMPONENT_STATE.value.selected_galaxy)
    
    def add_link(from_dc_name, from_att, to_dc_name, to_att):
        _add_link(gjapp, from_dc_name, from_att, to_dc_name, to_att)

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
    
    
    

    
    

    def add_example_measurements_to_glue():
        logger.info('in add_example_measurements_to_glue')
        if len(LOCAL_STATE.value.example_measurements) > 0:
            logger.info(f'has {len(LOCAL_STATE.value.example_measurements)} example measurements')
            example_measurements_glue = models_to_glue_data(
                LOCAL_STATE.value.example_measurements,
                label=EXAMPLE_GALAXY_MEASUREMENTS,
            )
            example_measurements_glue.style.color = MY_DATA_COLOR
            create_example_subsets(gjapp, example_measurements_glue)

            use_this = add_or_update_data(example_measurements_glue)
            use_this.style.color = MY_DATA_COLOR

            link_example_seed_and_measurements(gjapp)
        else:
            logger.info('no example measurements yet')

    
    def _glue_sync_setup():
        logger.info('running _glue_sync_setup')
        if LOCAL_STATE.value.measurements_loaded:
            logger.info(f'\texample_measurements: {len(LOCAL_STATE.value.example_measurements)}')
            logger.info(f'\tmeasurements: {len(LOCAL_STATE.value.measurements)}')
            add_example_measurements_to_glue()
            update_second_example_measurement()
    
    
    solara.use_memo(_glue_sync_setup, dependencies=[Ref(LOCAL_STATE.fields.measurements_loaded)])

    # Flag to show/hide the selection tool. TODO: we shouldn't need to be
    #   doing this here; revisit in the future and implement proper handling
    #   in the ipywwt package itself.
    show_selection_tool, set_show_selection_tool = solara.use_state(False)

    selection_tool_bg_count = solara.use_reactive(0)

    async def _delay_selection_tool():
        await asyncio.sleep(3)
        set_show_selection_tool(True)

    solara.lab.use_task(_delay_selection_tool)

    def _fill_galaxies():
        dummy_measurements = LOCAL_API.get_dummy_data()
        measurements = []
        for measurement in dummy_measurements:
            measurements.append(StudentMeasurement(student_id=GLOBAL_STATE.value.student.id,
                                                   galaxy=measurement.galaxy,
                                                   obs_wave_value=measurement.obs_wave_value,
                                                   velocity_value=measurement.velocity_value,
                                                   ang_size_value=measurement.ang_size_value,
                                                   est_dist_value=measurement.est_dist_value))
        Ref(LOCAL_STATE.fields.measurements).set(measurements)

    def _fill_lambdas():
        dummy_measurements = LOCAL_API.get_dummy_data()
        measurements = []
        for measurement in dummy_measurements:
            measurements.append(StudentMeasurement(student_id=GLOBAL_STATE.value.student.id,
                                                   obs_wave_value=measurement.obs_wave_value,
                                                   galaxy=measurement.galaxy))
        Ref(LOCAL_STATE.fields.measurements).set(measurements)

    def _fill_stage1_go_stage2():
        dummy_measurements = LOCAL_API.get_dummy_data()
        measurements = []
        for measurement in dummy_measurements:
            measurements.append(StudentMeasurement(student_id=GLOBAL_STATE.value.student.id,
                                                   obs_wave_value=measurement.obs_wave_value,
                                                   galaxy=measurement.galaxy,
                                                   velocity_value=measurement.velocity_value))
        Ref(LOCAL_STATE.fields.measurements).set(measurements)
        router.push("02-distance-introduction")

    def _select_random_galaxies():
        need = 5 - len(LOCAL_STATE.value.measurements)
        if need <= 0:
            return
        galaxies = LOCAL_API.get_galaxies(LOCAL_STATE)
        sample = np.random.choice(galaxies, size=need, replace=False)
        new_measurements = [StudentMeasurement(student_id=GLOBAL_STATE.value.student.id,
                                               galaxy=galaxy)
                             for galaxy in sample]
        measurements = LOCAL_STATE.value.measurements + new_measurements
        Ref(LOCAL_STATE.fields.measurements).set(measurements)
    
    def num_bad_velocities():
        measurements = Ref(LOCAL_STATE.fields.measurements)
        num = 0
        for meas in measurements.value:
            if meas.obs_wave_value is None or meas.rest_wave_value is None:
                # Skip measurements with missing data cuz they have not been attempted
                continue
            elif is_wavelength_poorly_measured(meas.obs_wave_value, meas.rest_wave_value, meas.galaxy.z):
                num += 1
        
        has_multiple_bad_velocities = Ref(COMPONENT_STATE.fields.has_multiple_bad_velocities)
        has_multiple_bad_velocities.set(num > 1)
        return num
    
    def set_obs_wave_total():
        obs_wave_total = Ref(COMPONENT_STATE.fields.obs_wave_total)
        measurements = LOCAL_STATE.value.measurements
        num = 0
        for meas in measurements:
            # print(meas)
            if meas.obs_wave_value is not None:
                num += 1
        obs_wave_total.set(num)

    def _initialize_state(isloaded):
        if (not isloaded):
            return

        if COMPONENT_STATE.value.current_step == Marker.sel_gal2:
            if COMPONENT_STATE.value.total_galaxies == 5:
                transition_to(COMPONENT_STATE, Marker.sel_gal3, force=True)

        if COMPONENT_STATE.value.current_step > Marker.cho_row1:
            COMPONENT_STATE.value.selected_example_galaxy = 1576  # id of the first example galaxy

    loaded_component_state.subscribe(_initialize_state)
    
    def print_selected_galaxy(galaxy):
        print('selected galaxy is now:', galaxy)

    

    def print_selected_example_galaxy(galaxy):
        print('selected example galaxy is now:', galaxy)

    

    sync_wavelength_line = solara.use_reactive(6565.0)
    sync_velocity_line = solara.use_reactive(0.0)
    spectrum_bounds = solara.use_reactive([])
    dotplot_bounds = solara.use_reactive([])
    max_spectrum_bounds = solara.use_reactive([])

    @computed
    def show_synced_lines():
        return COMPONENT_STATE.value.current_step >= Marker.dot_seq5

    @computed
    def sync_plot_lines():
        return COMPONENT_STATE.value.current_step >= Marker.dot_seq5

    @computed
    def sync_plot_zoom():
        return COMPONENT_STATE.value.current_step >= Marker.dot_seq5

    ## ----- Make sure we are initialized in the correct state ----- ##
    def sync_example_velocity_to_wavelength(velocity):
        if len(LOCAL_STATE.value.example_measurements) > 0:
            lambda_rest = LOCAL_STATE.value.example_measurements[0].rest_wave_value
            lambda_obs = v2w(velocity, lambda_rest)
            print(f'sync_example_velocity_to_wavelength {velocity:0.2f} -> {lambda_obs:0.2f}')
            return lambda_obs
    
    def sync_example_wavelength_to_velocity(wavelength):
        if len(LOCAL_STATE.value.example_measurements) > 0:
            lambda_rest = LOCAL_STATE.value.example_measurements[0].rest_wave_value
            velocity = w2v(wavelength, lambda_rest)
            print(f'sync_example_wavelength_to_velocity {wavelength:0.2f} -> {velocity:0.2f}')
            return velocity
    
    def sync_spectrum_to_dotplot_range(value):
        if sync_plot_zoom.value:
            logger.info('Setting dotplot range from spectrum range')
            lambda_rest = LOCAL_STATE.value.example_measurements[0].rest_wave_value
            return [w2v(v, lambda_rest) for v in value]
    
    def sync_dotplot_to_spectrum_range(value):
        if sync_plot_zoom.value:
            logger.info('Setting spectrum range from dotplot range')
            lambda_rest = LOCAL_STATE.value.example_measurements[0].rest_wave_value
            return [v2w(v, lambda_rest) for v in value]
            
    
    @computed
    def dotplot_reset_bounds():
        if COMPONENT_STATE.value.current_step <= Marker.dot_seq4:
            return []
        if len(LOCAL_STATE.value.example_measurements) > 0:
            lambda_rest = LOCAL_STATE.value.example_measurements[0].rest_wave_value
            return [w2v(w, lambda_rest) for w in max_spectrum_bounds.value]
        return []

    def initialize_bounds(value):
        logger.info('Initializing dotplot to max spectrum bounds')
        if len(value) == 2:
            lr = LOCAL_STATE.value.example_measurements[0].rest_wave_value
            dotplot_bounds.set([w2v(w, lr) for w in max_spectrum_bounds.value])
            spectrum_bounds.set([value[0], value[1]])
    
    
    def _reactive_subscription_setup():
        Ref(COMPONENT_STATE.fields.selected_galaxy).subscribe(print_selected_galaxy)
        Ref(COMPONENT_STATE.fields.selected_example_galaxy).subscribe(print_selected_example_galaxy)
        max_spectrum_bounds.subscribe(initialize_bounds)
        
        sync_reactives(spectrum_bounds, 
                       dotplot_bounds, 
                       sync_spectrum_to_dotplot_range, 
                       sync_dotplot_to_spectrum_range)
        
    solara.use_effect(_reactive_subscription_setup, dependencies=[])

    

    def create_dotplot_viewer(first_dotplot = True, show_which_meas = 'first', show_which_seed = 'first', ignore_full_seed_data = True, ignore_full_meas_data = True):
        print("\n\n ======== \ncreate_dotplot_viewer\n\n")
        show_meas = COMPONENT_STATE.value.current_step >= Marker.int_dot1        
        ignore = []
        
        if show_meas and (EXAMPLE_GALAXY_MEASUREMENTS in gjapp.data_collection):
            
            if show_which_seed == 'first':
                seed = gjapp.data_collection[EXAMPLE_GALAXY_SEED_DATA + '_first']
            elif show_which_seed == 'second':
                seed = gjapp.data_collection[EXAMPLE_GALAXY_SEED_DATA + '_second']
            else:
                seed = gjapp.data_collection[EXAMPLE_GALAXY_SEED_DATA]
            
            viewer_data = [
                gjapp.data_collection[EXAMPLE_GALAXY_MEASUREMENTS],
                seed
            ]
            # If the student has made a measurement, that is the 0th layer.
            layer0 = gjapp.data_collection[EXAMPLE_GALAXY_MEASUREMENTS]
            zorder = [1,5]
            if ignore_full_meas_data:
                ignore.append(gjapp.data_collection[EXAMPLE_GALAXY_MEASUREMENTS])
            if show_which_meas == 'second': # ignore the first
                first = subset_by_label(layer0, "first measurement")
                if first is not None:
                    ignore.append(first)
            elif show_which_meas == 'first': # ignore the second
                second = subset_by_label(layer0, "second measurement")
                if second is not None:
                    ignore.append(second)
        else:
            viewer_data = [gjapp.data_collection[EXAMPLE_GALAXY_SEED_DATA]]
            # If the student has NOT made a measurement, the seed data is the 0th layer.
            layer0 = gjapp.data_collection[EXAMPLE_GALAXY_SEED_DATA]
            zorder = None
        
        # seed_data = gjapp.data_collection[EXAMPLE_GALAXY_SEED_DATA]
        # if ignore_full_seed_data:
        #     ignore.append(gjapp.data_collection[EXAMPLE_GALAXY_SEED_DATA])
        # if show_which_seed == 'second': # ignore the first
        #     first = subset_by_label(seed_data, "first measurement")
        #     if first is not None:
        #         ignore.append(first)
        # elif show_which_seed == 'first': # ignore the second
        #     second = subset_by_label(seed_data, "second measurement")
        #     if second is not None:
        #         ignore.append(second)

        
        
        
        # we'll need to use/modify this for syncing 2 dot plots or for syncing auto-zoomed in x-ranges.
        def _on_click_callback(point):
            sync_velocity_line.set(point.xs[0])
            wavelength = sync_example_velocity_to_wavelength(point.xs[0])
            if wavelength:
                sync_wavelength_line.set(wavelength)
        logger.info(f"\n IGNORED LAYERS: {ignore} \n")
        with solara.Div() as main:
            title = "Dotplot: Example Galaxy Velocities"
            if not first_dotplot:
                title += " (2nd Measurement)"
            solara.Text(title)
            solara.Text(f"Ignored layers: {ignore}")
            solara.Switch(label='show bins', value = Ref(COMPONENT_STATE.fields.highlight_bins))
            DotplotViewer(
                gjapp,
                title=title,
                data=viewer_data,
                component_id=DB_VELOCITY_FIELD,
                vertical_line_visible=show_synced_lines.value,  #COMPONENT_STATE.value.current_step_between(Marker.dot_seq2, Marker.dot_seq6),
                line_marker_at=sync_velocity_line,
                line_marker_color=LIGHT_GENERIC_COLOR,
                on_click_callback=_on_click_callback,
                unit="km / s",
                x_label="Velocity (km/s)",
                y_label="Count",
                zorder=[1,5],
                nbin=74,
                x_bounds=dotplot_bounds,
                reset_bounds=dotplot_reset_bounds,
                hide_layers=ignore,  # type: ignore
                highlight_bins=COMPONENT_STATE.value.highlight_bins
            )
        return main
    
    speech = Ref(GLOBAL_STATE.fields.speech)


    def _on_marker_updated(marker):
        if COMPONENT_STATE.value.is_current_step(Marker.dot_seq4):
            initialize_bounds(max_spectrum_bounds.value)
        if COMPONENT_STATE.value.current_step >= Marker.rem_vel1:
            update_second_example_measurement() # either set them to current or keep from DB
        if COMPONENT_STATE.value.current_step_between(Marker.mee_gui1, Marker.sel_gal4):
            selection_tool_bg_count.set(selection_tool_bg_count.value + 1)

    Ref(COMPONENT_STATE.fields.current_step).subscribe(_on_marker_updated)
    

    
    with solara.Row():
        with solara.Column():
            StateEditor(Marker, COMPONENT_STATE, LOCAL_STATE, LOCAL_API, show_all=True)
        with solara.Column():
            solara.Button(label="Shortcut: Fill in galaxy velocity data & Jump to Stage 2", on_click=_fill_stage1_go_stage2, classes=["demo-button"])
            solara.Button(label="Choose 5 random galaxies", on_click=_select_random_galaxies, classes=["demo-button"])

    with rv.Row():
        with rv.Col(cols=12, lg=4):
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineIntro.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.mee_gui1),
                speech=speech.value,
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineSelectGalaxies1.vue",
                # If at least 1 galaxy has already been selected, we want to go straight from here to sel_gal3.
                event_next_callback=lambda _: transition_to(COMPONENT_STATE, Marker.sel_gal2 if COMPONENT_STATE.value.total_galaxies == 0 else Marker.sel_gal3, force=True),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.sel_gal1),
                speech=speech.value,
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineSelectGalaxies2.vue",
                # I think we don't need this next callback because meeting the "next" criteria will autoadvance you to not_gal1 anyway, and then we skip over this guideline if we go backwards from sel_gal3. (But leave it just in case)
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.sel_gal2),
                state_view={
                    "total_galaxies": COMPONENT_STATE.value.total_galaxies,
                    "galaxy_is_selected": COMPONENT_STATE.value.galaxy_is_selected,
                },
                speech=speech.value,
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineSelectGalaxies3.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                # You can't get to this marker until at least 1 galaxy has been selected. Once a galaxy has been selected, sel_gal2 doesn't make sense, so jump back to sel_gal1.
                event_back_callback=lambda _: transition_to(COMPONENT_STATE, Marker.sel_gal1, force=True),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.sel_gal3),
                state_view={
                    "total_galaxies": COMPONENT_STATE.value.total_galaxies,
                    "galaxy_is_selected": COMPONENT_STATE.value.galaxy_is_selected,
                },
                speech=speech.value,
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineSelectGalaxies4.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.sel_gal4),
                speech=speech.value,
            )

        with rv.Col(cols=12, lg=8):
            
            show_snackbar = Ref(LOCAL_STATE.fields.show_snackbar)
            async def snackbar_off(value = None):
                if show_snackbar.value:
                    await asyncio.sleep(3)
                    show_snackbar.set(False)
            solara.lab.use_task(snackbar_off, dependencies=[show_snackbar])
            
            def _galaxy_added_callback(galaxy_data: GalaxyData):
                already_exists = galaxy_data.id in [
                    x.galaxy_id for x in LOCAL_STATE.value.measurements
                ]

                if already_exists:
                    return

                if len(LOCAL_STATE.value.measurements) == 5:
                    show_snackbar = Ref(LOCAL_STATE.fields.show_snackbar)
                    snackbar_message = Ref(LOCAL_STATE.fields.snackbar_message)

                    show_snackbar.set(True)
                    snackbar_message.set(
                        "You've already selected 5 galaxies. Continue forth!"
                    )
                    logger.info("Attempted to add more than 5 galaxies.")
                    return

                logger.info("Adding galaxy `%s` to measurements.", galaxy_data.id)

                measurements = Ref(LOCAL_STATE.fields.measurements)

                measurements.set(
                    measurements.value
                    + [
                        StudentMeasurement(
                            student_id=GLOBAL_STATE.value.student.id,
                            galaxy=galaxy_data,
                        )
                    ]
                )
                
                
            total_galaxies = Ref(COMPONENT_STATE.fields.total_galaxies)
            def advance_on_total_galaxies(value):
                if COMPONENT_STATE.value.current_step == Marker.sel_gal2:
                    if value == 1:
                        transition_to(COMPONENT_STATE, Marker.not_gal1)
            total_galaxies.subscribe(advance_on_total_galaxies)

            def _galaxy_selected_callback(galaxy_data: GalaxyData | None):
                if galaxy_data is None:
                    return
                selected_galaxy = Ref(COMPONENT_STATE.fields.selected_galaxy)
                selected_galaxy.set(galaxy_data.id)
                galaxy_is_selected = Ref(COMPONENT_STATE.fields.galaxy_is_selected)
                galaxy_is_selected.set(True)  

            def _deselect_galaxy_callback():
                galaxy_is_selected = Ref(COMPONENT_STATE.fields.galaxy_is_selected)
                galaxy_is_selected.set(False)  
                print("is galaxy selected:", galaxy_is_selected.value)             

            show_example_data_table = COMPONENT_STATE.value.current_step_between(
            Marker.cho_row1, Marker.dot_seq14 #placeholder so it doesn't break - change to last new dot_seq marker.
            )
            if show_example_data_table:
                selection_tool_galaxy = selected_example_measurement
            else:
                selection_tool_galaxy = selected_measurement
            
            SelectionTool(
                show_galaxies=COMPONENT_STATE.value.current_step_in(
                    [Marker.sel_gal2, Marker.not_gal1, Marker.sel_gal3]
                ),
                galaxy_selected_callback=_galaxy_selected_callback,
                galaxy_added_callback=_galaxy_added_callback,
                selected_measurement=(
                    selection_tool_galaxy.value.dict()
                    if selection_tool_galaxy.value is not None
                    else None
                ),
                deselect_galaxy_callback=_deselect_galaxy_callback,
                sdss_counter=selection_tool_bg_count,
            )
            
            if show_snackbar.value:
                solara.Info(label=LOCAL_STATE.value.snackbar_message)        

    # Measurement Table Row

    with rv.Row():
        with rv.Col(cols=12, lg=4):
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineNoticeGalaxyTable.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                # You can't get to this marker until at least 1 galaxy has been selected. Once a galaxy has been selected, sel_gal2 doesn't make sense, so jump back to sel_gal1.
                event_back_callback=lambda _: transition_to(COMPONENT_STATE, Marker.sel_gal1, force=True),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.not_gal1),
                speech=speech.value,
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineChooseRow.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.cho_row1),
                speech=speech.value,
            )
            
            validation_4_failed = Ref(
                COMPONENT_STATE.fields.doppler_state.validation_4_failed
            )
            
            show_values = Ref(COMPONENT_STATE.fields.show_dop_cal4_values)
            
            def _on_validate_transition(validated):
                logger.info("Validated transition to dop_cal5: %s", validated)
                validation_4_failed.set(not validated)
                show_values.set(validated)
                if not validated:
                    return
                
                if validated:
                    transition_to(COMPONENT_STATE, Marker.dop_cal5)

                show_doppler_dialog = Ref(COMPONENT_STATE.fields.show_doppler_dialog)
                logger.info("Setting show_doppler_dialog to %s", validated)
                show_doppler_dialog.set(validated)

            
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineDopplerCalc4.vue",
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.current_step_in(
                    [Marker.dop_cal4, Marker.dop_cal5]
                ),
                state_view={
                    "lambda_obs": round(COMPONENT_STATE.value.obs_wave),
                    "lambda_rest": (
                        selected_example_measurement.value.rest_wave_value
                        if selected_example_measurement.value is not None
                        else None
                    ),
                    "failed_validation_4": validation_4_failed.value,
                    "fill_values": show_values.value,
                },
                event_on_validate_transition=_on_validate_transition,
                speech=speech.value,
            )

            # This whole slideshow is basically dop_cal5
            if COMPONENT_STATE.value.is_current_step(Marker.dop_cal5):
                show_doppler_dialog = Ref(COMPONENT_STATE.fields.show_doppler_dialog)
                step = Ref(COMPONENT_STATE.fields.doppler_state.step)
                validation_5_failed = Ref(
                    COMPONENT_STATE.fields.doppler_state.validation_5_failed
                )
                max_step_completed_5 = Ref(
                    COMPONENT_STATE.fields.doppler_state.max_step_completed_5
                )
                student_c = Ref(COMPONENT_STATE.fields.doppler_state.student_c)
                velocity_calculated = Ref(
                    COMPONENT_STATE.fields.doppler_state.velocity_calculated
                )

                def _velocity_calculated_callback(value):
                    example_measurement_index = (
                        LOCAL_STATE.value.get_example_measurement_index(
                            COMPONENT_STATE.value.selected_example_galaxy,
                            measurement_number='first'
                        )
                    )
                    if example_measurement_index is None:
                        return
                    example_measurement = Ref(
                        LOCAL_STATE.fields.example_measurements[
                            example_measurement_index
                        ]
                    )
                    example_measurement.set(
                        example_measurement.value.model_copy(
                            update={"velocity_value": round(value)}
                        )
                    )
                    
                    if COMPONENT_STATE.value.current_step == Marker.rem_vel1:
                        add_example_measurements_to_glue()

                DopplerSlideshow(
                    dialog=COMPONENT_STATE.value.show_doppler_dialog,
                    titles=COMPONENT_STATE.value.doppler_state.titles,
                    step=COMPONENT_STATE.value.doppler_state.step,
                    length=COMPONENT_STATE.value.doppler_state.length,
                    lambda_obs=round(COMPONENT_STATE.value.obs_wave),
                    lambda_rest=(
                        selected_example_measurement.value.rest_wave_value
                        if selected_example_measurement.value is not None
                        else None
                    ),
                    max_step_completed_5=COMPONENT_STATE.value.doppler_state.max_step_completed_5,
                    failed_validation_5=COMPONENT_STATE.value.doppler_state.validation_5_failed,
                    interact_steps_5=COMPONENT_STATE.value.doppler_state.interact_steps_5,
                    student_c=COMPONENT_STATE.value.doppler_state.student_c,
                    student_vel_calc=COMPONENT_STATE.value.doppler_state.velocity_calculated,
                    event_set_dialog=show_doppler_dialog.set,
                    event_set_step=step.set,
                    event_set_failed_validation_5=validation_5_failed.set,
                    event_set_max_step_completed_5=max_step_completed_5.set,
                    event_set_student_vel_calc=velocity_calculated.set,
                    event_set_student_vel=_velocity_calculated_callback,
                    event_set_student_c=student_c.set,
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_mc_callback=lambda event: mc_callback(event, LOCAL_STATE, COMPONENT_STATE),
                    state_view={
                        "mc_score": get_multiple_choice(LOCAL_STATE, COMPONENT_STATE, "interpret-velocity"
                        ),
                        "score_tag": "interpret-velocity",
                    },
                )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineCheckMeasurement.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: _on_validate_transition(True), # Send user back to dop_cal5 and open dialog
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.che_mea1),
                speech=speech.value,
            )
            # Skip for now since we aren't offering 2nd measurement.
            # ScaffoldAlert(
            #     GUIDELINE_ROOT / "GuidelineDotSequence13.vue",
            #     event_next_callback=lambda _: transition_next(COMPONENT_STATE),
            #     event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
            #     can_advance=COMPONENT_STATE.value.can_transition(next=True),
            #     show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq13),
            # )
            set_obs_wave_total()
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineRemainingGals.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.rem_gal1),
                state_view={
                    "obswaves_total": COMPONENT_STATE.value.obs_wave_total,
                    "has_bad_velocities": COMPONENT_STATE.value.has_bad_velocities,
                    "has_multiple_bad_velocities": COMPONENT_STATE.value.has_multiple_bad_velocities,
                    "selected_galaxy": (
                        selected_measurement.value.dict()
                        if selected_measurement.value is not None
                        else None
                    ),
                },
                speech=speech.value,
            )
            if COMPONENT_STATE.value.is_current_step(Marker.rem_gal1):
                solara.Button(label="DEMO SHORTCUT: FILL λ MEASUREMENTS", on_click=_fill_lambdas, style="text-transform: none;", classes=["demo-button"])
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineDopplerCalc6.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.dop_cal6),
                speech=speech.value,
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineReflectVelValues.vue",
                event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                event_mc_callback=lambda event: mc_callback(event, LOCAL_STATE, COMPONENT_STATE),
                show=COMPONENT_STATE.value.is_current_step(Marker.ref_vel1),
                state_view={'mc_score': get_multiple_choice(LOCAL_STATE, COMPONENT_STATE, "reflect_vel_value"), 'score_tag': 'reflect_vel_value'},
                speech=speech.value,
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineEndStage1.vue",
                event_next_callback=lambda _: router.push("02-distance-introduction"),
                event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                can_advance=COMPONENT_STATE.value.can_transition(next=True),
                show=COMPONENT_STATE.value.is_current_step(Marker.end_sta1),
                state_view={
                    "has_bad_velocities": COMPONENT_STATE.value.has_bad_velocities,
                    "has_multiple_bad_velocities": COMPONENT_STATE.value.has_multiple_bad_velocities,
                },
                speech=speech.value,
            )

        with rv.Col(cols=12, lg=8):
            show_example_data_table = COMPONENT_STATE.value.current_step_between(
                Marker.cho_row1, Marker.dot_seq14  # TODO: change this back to dot_seq14 if we put back 2nd galaxy measurement
            )

            if show_example_data_table:
                selected_example_galaxy = Ref(
                    COMPONENT_STATE.fields.selected_example_galaxy
                )
                
                @computed
                def example_galaxy_data():
                    if use_second_measurement.value:
                        return [
                            x.dict() for x in LOCAL_STATE.value.example_measurements if x.measurement_number == 'second'
                        ]
                    else:
                        return [
                            x.dict() for x in LOCAL_STATE.value.example_measurements if x.measurement_number == 'first'
                        ]

                @computed
                def selected_example_galaxy_index():
                    index = LOCAL_STATE.value.get_example_measurement_index(
                        selected_example_galaxy.value,
                        measurement_number='second' if use_second_measurement.value else 'first')
                    if index is None:
                        return []
                    else:
                        return [0]

                def update_example_galaxy(galaxy):
                    flag = galaxy.get("value", True)
                    value = galaxy["item"]["galaxy_id"] if flag else None
                    selected_example_galaxy = Ref(COMPONENT_STATE.fields.selected_example_galaxy)
                    if value is not None:
                        galaxy = LOCAL_STATE.value.get_example_measurement(value, measurement_number='second' if use_second_measurement.value else 'first')
                        if galaxy is not None:
                            value = galaxy.galaxy_id
                        else:
                            value = None
                        
                    selected_example_galaxy.set(value)
                
                
                common_headers = [
                                    {"text": "Galaxy Name", "align": "start","sortable": False,"value": "name",},
                                    {"text": "Element", "value": "element"},
                                    {"text": "&lambda;<sub>rest</sub> (&Aring;)",
                                     "value": "rest_wave_value"},
                                    {"text": "&lambda;<sub>obs</sub> (&Aring;)",
                                     "value": "obs_wave_value"},
                                    {"text": "Velocity (km/s)", "value": "velocity_value"},
                                ]
                if use_second_measurement.value:
                    measnum_header = {"text": "Measurement Number", "value": "measurement_number"}
                    common_headers.append(measnum_header)

                
                # with solara.Card(title="Remove: for testing", style={'background-color': 'var(--warning-dark)'}):
                #     solara.Text(f"{COMPONENT_STATE.value.obs_wave}")
                #     DataTable(title="Example Measurements",
                #             items=[x.model_dump() for x in LOCAL_STATE.value.example_measurements])
                

                DataTable(
                    title="Example Galaxy",
                    headers=common_headers,
                    items=example_galaxy_data.value,
                    selected_indices=selected_example_galaxy_index.value,
                    show_select=COMPONENT_STATE.value.current_step_at_or_after(Marker.cho_row1),
                    event_on_row_selected=update_example_galaxy,
                )
            else:
                selected_galaxy = Ref(COMPONENT_STATE.fields.selected_galaxy)

                def _on_table_row_selected(row):
                    galaxy_measurement = LOCAL_STATE.value.get_measurement(
                        row["item"]["galaxy_id"]
                    )
                    if galaxy_measurement is not None:
                        selected_galaxy.set(galaxy_measurement.galaxy_id)

                    obs_wave = Ref(COMPONENT_STATE.fields.obs_wave)
                    obs_wave.set(0)

                def _on_calculate_velocity():
                    for i in range(len(LOCAL_STATE.value.measurements)):
                        measurement = Ref(LOCAL_STATE.fields.measurements[i])
                        velocity = round(
                            3e5
                            * (
                                measurement.value.obs_wave_value
                                / measurement.value.rest_wave_value
                                - 1
                            )
                        )
                        measurement.set(
                            measurement.value.model_copy(
                                update={"velocity_value": velocity}
                            )
                        )

                        velocities_total = Ref(COMPONENT_STATE.fields.velocities_total)
                        velocities_total.set(velocities_total.value + 1)

                @computed
                def selected_galaxy_index():
                    index = LOCAL_STATE.value.get_measurement_index(selected_galaxy.value)
                    if index is None:
                        return []
                    else:
                        return [index]

                DataTable(
                    title="My Galaxies",
                    items=[x.dict() for x in LOCAL_STATE.value.measurements],
                    selected_indices=selected_galaxy_index.value,
                    show_select=COMPONENT_STATE.value.current_step_at_or_after(
                        Marker.cho_row1
                    ),
                    button_icon="mdi-run-fast",
                    show_button=COMPONENT_STATE.value.is_current_step(
                        Marker.dop_cal6
                    ),
                    event_on_row_selected=_on_table_row_selected,
                    event_on_button_pressed=lambda _: _on_calculate_velocity(),
                )

    # dot plot slideshow button row

    if COMPONENT_STATE.value.current_step_between(Marker.int_dot1, Marker.dot_seq14): # TODO: Change this back to dot_seq14 if we put back 2nd galaxy measurement
        with rv.Row(class_="no-padding"):
            with rv.Col(cols=12, lg=4, class_="no-padding"):
                pass
            with rv.Col(cols=12, lg=8, class_="no-padding"):
                with rv.Col(cols=4, offset=4, class_="no-padding"):
                    dotplot_tutorial_finished = Ref(
                        COMPONENT_STATE.fields.dotplot_tutorial_finished
                    )
                    
                    tut_viewer_data = None
                    if EXAMPLE_GALAXY_SEED_DATA in gjapp.data_collection:
                        tut_viewer_data = gjapp.data_collection[EXAMPLE_GALAXY_SEED_DATA]
                    DotplotTutorialSlideshow(
                        dialog=COMPONENT_STATE.value.show_dotplot_tutorial_dialog,
                        step=COMPONENT_STATE.value.dotplot_tutorial_state.step,
                        length=COMPONENT_STATE.value.dotplot_tutorial_state.length,
                        max_step_completed=COMPONENT_STATE.value.dotplot_tutorial_state.max_step_completed,
                        dotplot_viewer=DotplotViewer(gjapp,
                                                    data=tut_viewer_data,
                                                    component_id=DB_VELOCITY_FIELD,
                                                    vertical_line_visible=False,
                                                    line_marker_color=LIGHT_GENERIC_COLOR,
                                                    unit="km / s",
                                                    x_label="Velocity (km/s)",
                                                    y_label="Count"
                                                    ),
                                                    
                        event_tutorial_finished=lambda _: dotplot_tutorial_finished.set(
                            True
                        ),
                    )
                
    # Dot Plot 1st measurement row
    if COMPONENT_STATE.value.current_step_between(Marker.int_dot1, Marker.dot_seq14): # TODO: Change this back to dot_seq14 if we put back 2nd galaxy measurement
        with rv.Row(class_="no-y-padding"):
            with rv.Col(cols=12, lg=4, class_="no-y-padding"):
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineIntroDotplot.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.int_dot1),
                    speech=speech.value,
                    state_view={
                        "color": MY_DATA_COLOR_NAME
                    }
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineDotSequence01.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq1),
                    speech=speech.value,
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineDotSequence02.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq2),
                    speech=speech.value,
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineDotSequence03.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq3),
                    speech=speech.value,
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineDotSequence04a.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq4a),
                    speech=speech.value,
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineDotSequence05.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq5),
                    speech=speech.value,
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineDotSequence06.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq6),
                    speech=speech.value,
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineDotSequence07.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq7),
                    speech=speech.value,
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineDotSequence08.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    event_mc_callback=lambda event: mc_callback(event, LOCAL_STATE, COMPONENT_STATE),
                    show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq8),
                    state_view={
                        "mc_score": get_multiple_choice(LOCAL_STATE, COMPONENT_STATE, "vel_meas_consensus"),
                        "score_tag": "vel_meas_consensus",
                    },
                    speech=speech.value,
                )


            with rv.Col(cols=12, lg=8, class_="no-y-padding"):
                                        
                if EXAMPLE_GALAXY_MEASUREMENTS in gjapp.data_collection:
                    # add_example_measurements_to_glue() # make sure updated measurements are in glue
                    create_dotplot_viewer(
                        show_which_meas='first' if COMPONENT_STATE.value.current_step != Marker.rem_vel1 else 'second',
                        show_which_seed='first'
                    )

    # Dot Plot 2nd measurement row

    if COMPONENT_STATE.value.current_step_between(Marker.dot_seq14, Marker.dot_seq14):
        with rv.Row():
            with rv.Col(cols=12, lg=4):
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineDotSequence14.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq14),
                    speech=speech.value,
                )
            with rv.Col(cols=12, lg=8):
                print("Creating 2nd dotplot viewer")
                create_dotplot_viewer(
                    first_dotplot=False,
                    show_which_meas='second',
                    show_which_seed='second'
                )


    # Spectrum Viewer row
    if COMPONENT_STATE.value.current_step_between(Marker.mee_spe1, Marker.che_mea1) or COMPONENT_STATE.value.current_step_between(Marker.dot_seq4, Marker.rem_vel1) or COMPONENT_STATE.value.current_step_at_or_after(Marker.rem_gal1):
        with rv.Row():
            with rv.Col(cols=12, lg=4):
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineSpectrum.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.mee_spe1),
                    state_view={
                        "spectrum_tutorial_opened": COMPONENT_STATE.value.spectrum_tutorial_opened
                    },
                    speech=speech.value,
                )

                selected_example_galaxy_data = (
                    selected_example_measurement.value.galaxy.dict()
                    if selected_example_measurement.value is not None
                    else None
                )

                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineRestwave.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.res_wav1),
                    state_view={
                        "selected_example_galaxy": selected_example_galaxy_data,
                        "lambda_on": COMPONENT_STATE.value.rest_wave_tool_activated,
                    },
                    speech=speech.value,
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineObswave1.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.obs_wav1),
                    state_view={"selected_example_galaxy": selected_example_galaxy_data},
                    speech=speech.value,
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineObswave2.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.obs_wav2),
                    state_view={
                        "selected_example_galaxy": selected_example_galaxy_data,
                        "zoom_tool_activated": COMPONENT_STATE.value.zoom_tool_activated,
                        "zoom_tool_active": COMPONENT_STATE.value.zoom_tool_active,
                    },
                    speech=speech.value,
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineDopplerCalc0.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.dop_cal0),
                    speech=speech.value,
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineDopplerCalc2.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.dop_cal2),
                    speech=speech.value,
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineDotSequence04.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq4),
                    speech=speech.value,
                    state_view={
                        "color": MY_DATA_COLOR_NAME,
                    },
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineDotSequence10.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq10),
                    speech=speech.value,
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineDotSequence11.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq11),
                    speech=speech.value,
                )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineRemeasureVelocity.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.rem_vel1),
                    speech=speech.value,
                )
                # ScaffoldAlert(
                #     GUIDELINE_ROOT / "GuidelineDotSequence13a.vue",
                #     event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                #     event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                #     can_advance=COMPONENT_STATE.value.can_transition(next=True),
                #     show=COMPONENT_STATE.value.is_current_step(Marker.dot_seq13a),
                #     speech=speech.value,
                # )
                ScaffoldAlert(
                    GUIDELINE_ROOT / "GuidelineReflectOnData.vue",
                    event_next_callback=lambda _: transition_next(COMPONENT_STATE),
                    event_back_callback=lambda _: transition_previous(COMPONENT_STATE),
                    can_advance=COMPONENT_STATE.value.can_transition(next=True),
                    show=COMPONENT_STATE.value.is_current_step(Marker.ref_dat1),
                    speech=speech.value,
                )

            with rv.Col(cols=12, lg=8):
                show_example_spectrum = COMPONENT_STATE.value.current_step_between(
                    Marker.mee_spe1, Marker.che_mea1
                ) or COMPONENT_STATE.value.current_step_between(
                    Marker.dot_seq4, Marker.dot_seq14  # TODO: Change this back to dot_seq14 if we put back 2nd galaxy measurement
                )

                show_galaxy_spectrum = COMPONENT_STATE.value.current_step_at_or_after(
                    Marker.rem_gal1
                )

                if show_example_spectrum:
                    def _example_wavelength_measured_callback(value):
                        example_measurement_index = (
                            LOCAL_STATE.value.get_example_measurement_index(
                                COMPONENT_STATE.value.selected_example_galaxy,
                                measurement_number='second' if use_second_measurement.value else 'first'
                            )
                        )
                        if example_measurement_index is None:
                            return
                        
                        example_measurements = LOCAL_STATE.value.example_measurements
                        example_measurement = Ref(
                            LOCAL_STATE.fields.example_measurements[
                                example_measurement_index
                            ]
                        )

                        obs_wave = Ref(COMPONENT_STATE.fields.obs_wave)
                        obs_wave.set(value)
                        
                        if example_measurement.value.velocity_value is None:
                            example_measurement.set(
                                example_measurement.value.model_copy(
                                    update={"obs_wave_value": round(value)}
                                )
                            )
                        else:
                            velocity = velocity_from_wavelengths(value, example_measurement.value.rest_wave_value)
                            example_measurement.set(
                                example_measurement.value.model_copy(
                                    update={"obs_wave_value": round(value), "velocity_value": velocity}
                                )
                            )
                        example_measurements[example_measurement_index] = example_measurement.value
                        Ref(LOCAL_STATE.fields.example_measurements).set(example_measurements)
                        obs_wave_tool_used.set(True)
                        obs_wave = Ref(COMPONENT_STATE.fields.obs_wave)
                        obs_wave.set(value)
                        
                    def _on_set_marker_location(value):
                        logger.info('Setting marker location spectrum -> dotplot')
                        velocity = sync_example_wavelength_to_velocity(value)
                        if velocity:
                            logger.info(f'Setting velocity {velocity: 0.2f} ')
                            sync_velocity_line.set(velocity)

                    obs_wave_tool_used = Ref(COMPONENT_STATE.fields.obs_wave_tool_used)
                    rest_wave_tool_activated = Ref(
                        COMPONENT_STATE.fields.rest_wave_tool_activated
                    )
                    zoom_tool_activated = Ref(
                        COMPONENT_STATE.fields.zoom_tool_activated
                    )
                    zoom_tool_active = Ref(
                        COMPONENT_STATE.fields.zoom_tool_active
                    )
                    
                    @computed
                    def obs_wav_marker_value():
                        meas = LOCAL_STATE.value.example_measurements
                        if LOCAL_STATE.value.measurements_loaded and len(meas) > 0:
                            step = COMPONENT_STATE.value.current_step
                            if step >= Marker.rem_vel1 and meas[1].obs_wave_value is not None:
                                return meas[1].obs_wave_value
                            elif step >= Marker.dot_seq1 and meas[0].velocity_value is not None:
                                return meas[0].obs_wave_value
                        return COMPONENT_STATE.value.obs_wave


                    def _on_zoom():
                        zoom_tool_activated.set(True)
                        zoom_tool_active.set(True)

                    def _on_reset():
                        zoom_tool_active.set(False)
                    
                    SpectrumViewer(
                        galaxy_data=(
                            selected_example_measurement.value.galaxy
                            if selected_example_measurement.value is not None
                            else None
                        ),
                        obs_wave=obs_wav_marker_value.value, #COMPONENT_STATE.value.obs_wave if COMPONENT_STATE.value.current_step < Marker.dot_seq1 else E,
                        spectrum_click_enabled=(
                            COMPONENT_STATE.value.current_step_between(
                            Marker.obs_wav1, Marker.obs_wav2
                        )
                        or COMPONENT_STATE.value.current_step == Marker.rem_vel1
                        ),
                        on_obs_wave_measured=_example_wavelength_measured_callback,
                        on_rest_wave_tool_clicked=lambda: rest_wave_tool_activated.set(
                            True
                        ),
                        on_zoom=_on_zoom,
                        on_reset_tool_clicked=_on_reset,
                        marker_position=sync_wavelength_line if show_synced_lines.value else None,
                        spectrum_bounds = spectrum_bounds, # type: ignore
                        max_spectrum_bounds=max_spectrum_bounds,
                        show_obs_wave_line=COMPONENT_STATE.value.current_step_at_or_after(Marker.dot_seq4),
                        on_set_marker_position=_on_set_marker_location,
                    )

                elif show_galaxy_spectrum:
                    def _wavelength_measured_callback(value):
                        measurement_index = LOCAL_STATE.value.get_measurement_index(
                            COMPONENT_STATE.value.selected_galaxy
                        )
                        if measurement_index is None:
                            return

                        has_bad_velocities = Ref(
                            COMPONENT_STATE.fields.has_bad_velocities
                        )
                        is_bad = is_wavelength_poorly_measured(
                            value,
                            selected_measurement.value.rest_wave_value,
                            selected_measurement.value.galaxy.z,
                        )
                        has_bad_velocities.set(is_bad)
                        num_bad_velocities()

                        if not is_bad:

                            obs_wave = Ref(COMPONENT_STATE.fields.obs_wave)
                            obs_wave.set(value)

                            measurement = Ref(
                                LOCAL_STATE.fields.measurements[measurement_index]
                            )
                            
                            if measurement.value.velocity_value is None:
                                measurement.set(
                                    measurement.value.model_copy(
                                        update={"obs_wave_value": round(value)}
                                    )
                                )
                                
                            else:
                                velocity = velocity_from_wavelengths(value, measurement.value.rest_wave_value)
                                measurement.set(
                                    measurement.value.model_copy(
                                        update={"obs_wave_value": round(value), "velocity_value": velocity}
                                    )
                                )
                            
                            set_obs_wave_total()
                            
                            
                        else:
                            logger.info('Wavelength measurement is bad')

                    SpectrumViewer(
                        galaxy_data=(
                            selected_measurement.value.galaxy
                            if selected_measurement.value is not None
                            else None
                        ),
                        obs_wave=COMPONENT_STATE.value.obs_wave,
                        spectrum_click_enabled=COMPONENT_STATE.value.current_step_at_or_after(
                            Marker.obs_wav1
                        ),
                        on_obs_wave_measured=_wavelength_measured_callback,
                    )
                if COMPONENT_STATE.value.current_step_between(Marker.mee_spe1, Marker.rem_gal1): # center single button
                    with rv.Row():
                        with rv.Col(cols=4, offset=4):
                            spectrum_tutorial_opened = Ref(
                                COMPONENT_STATE.fields.spectrum_tutorial_opened
                            )
                            SpectrumSlideshow(
                                event_dialog_opened_callback=lambda _: spectrum_tutorial_opened.set(
                                    True
                                )
                            )
                
                if COMPONENT_STATE.value.current_step_at_or_after(Marker.ref_dat1): # space 2 buttons nicely
                    with rv.Row():
                        with rv.Col(cols=4, offset=2):
                            SpectrumSlideshow()
                        with rv.Col(cols=4):
                            show_reflection_dialog = Ref(
                                COMPONENT_STATE.fields.show_reflection_dialog
                            )
                            reflect_step = Ref(
                                COMPONENT_STATE.fields.velocity_reflection_state.step
                            )
                            reflect_max_step_completed = Ref(
                                COMPONENT_STATE.fields.velocity_reflection_state.max_step_completed
                            )
                            reflection_complete = Ref(COMPONENT_STATE.fields.reflection_complete)

                            ReflectVelocitySlideshow(
                                length=8,
                                titles=[
                                    "Reflect on your data",
                                    "What would a 1920's scientist wonder?",
                                    "Observed vs. rest wavelengths",
                                    "How galaxies move",
                                    "Do your data agree with 1920's thinking?",
                                    "Do your data agree with 1920's thinking?",
                                    "Did your peers find what you found?",
                                    "Reflection complete",
                                ],
                                interact_steps=[2, 3, 4, 5, 6],
                                require_responses=True,
                                dialog=COMPONENT_STATE.value.show_reflection_dialog,
                                step=COMPONENT_STATE.value.velocity_reflection_state.step,
                                max_step_completed=COMPONENT_STATE.value.velocity_reflection_state.max_step_completed,
                                reflection_complete=COMPONENT_STATE.value.reflection_complete,
                                state_view={
                                    "mc_score_2": get_multiple_choice(LOCAL_STATE, COMPONENT_STATE, "wavelength-comparison"),
                                    "score_tag_2": "wavelength-comparison",
                                    "mc_score_3": get_multiple_choice(LOCAL_STATE, COMPONENT_STATE, "galaxy-motion"),
                                    "score_tag_3": "galaxy-motion",
                                    "mc_score_4": get_multiple_choice(LOCAL_STATE, COMPONENT_STATE, "steady-state-consistent"),
                                    "score_tag_4": "steady-state-consistent",
                                    "mc_score_5": get_multiple_choice(LOCAL_STATE, COMPONENT_STATE, "moving-randomly-consistent"),
                                    "score_tag_5": "moving-randomly-consistent",
                                    "mc_score_6": get_multiple_choice(LOCAL_STATE, COMPONENT_STATE, "peers-data-agree"),
                                    "score_tag_6": "peers-data-agree",
                                },
                                event_set_dialog=show_reflection_dialog.set,
                                event_mc_callback=lambda event: mc_callback(event, LOCAL_STATE, COMPONENT_STATE),
                                # These are numbered based on window-item value
                                event_set_step=reflect_step.set,
                                event_set_max_step_completed=reflect_max_step_completed.set,
                                event_on_reflection_complete=lambda _: reflection_complete.set(
                                    True
                                ),
                            )
