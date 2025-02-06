from os import getenv
from cosmicds.layout import BaseLayout
from .state import GLOBAL_STATE, LOCAL_STATE
import solara
from solara.toestand import Ref
from cosmicds.components import MathJaxSupport, PlotlySupport, GoogleAnalyticsSupport
from hubbleds.remote import LOCAL_API
from cosmicds.logger import setup_logger

logger = setup_logger("LAYOUT")


@solara.component
def Layout(children=[]):

    MathJaxSupport()
    PlotlySupport()
    GoogleAnalyticsSupport(tag=getenv("GOOGLE_ANALYTICS_TAG"))
    logger.info("Mounted external libraries.")

    student_id = Ref(GLOBAL_STATE.fields.student.id)
    loaded_states = solara.use_reactive(False)

    router = solara.use_router()
    Ref(LOCAL_STATE.fields.last_route).set(router.path)
    route_index = next((i for i, r in enumerate(router.routes) if r.path == router.path.strip('/')), None)
    Ref(LOCAL_STATE.fields.max_route_index).set(max(route_index or 0, LOCAL_STATE.value.max_route_index or 0))

    async def _load_global_local_states():
        if not GLOBAL_STATE.value.student.id:
            logger.warning("Failed to load measurements: no student was found.")
            return

        logger.info(
            "Loading story stage and measurements for user `%s`.",
            GLOBAL_STATE.value.student.id,
        )

        # Retrieve the student's app and local states
        LOCAL_API.get_app_story_states(GLOBAL_STATE, LOCAL_STATE)
        Ref(GLOBAL_STATE.fields.update_db).set(False)


        # Load in the student's measurements
        measurements = LOCAL_API.get_measurements(GLOBAL_STATE, LOCAL_STATE)
        sample_measurements = LOCAL_API.get_sample_measurements(
            GLOBAL_STATE, LOCAL_STATE
        )

        logger.info("Finished loading state.")
        if LOCAL_STATE.value.last_route is not None:
            router.push(LOCAL_STATE.value.last_route)
        loaded_states.set(True)

        Ref(LOCAL_STATE.fields.measurements_loaded).set(True)

    solara.lab.use_task(_load_global_local_states, dependencies=[student_id.value])

    # solara.use_memo(_load_local_state, dependencies=[student_id.value])

    async def _write_local_global_states():
        if not loaded_states.value:
            return

        # Listen for changes in the states and write them to the database
        put_state = LOCAL_API.put_story_state(GLOBAL_STATE, LOCAL_STATE)

        # Be sure to write the measurement data separately since it's stored
        #  in another location in the database
        put_meas = LOCAL_API.put_measurements(GLOBAL_STATE, LOCAL_STATE)
        put_samp = LOCAL_API.put_sample_measurements(GLOBAL_STATE, LOCAL_STATE)
        
        if put_state and put_meas and put_samp:
            logger.info("Wrote state to database.")
        else:
            logger.info(f"Did not write {'story state' if not put_state else ''} {'measurements' if not put_meas else ''} {'sample measurements' if not put_samp else ''} to database.")

    solara.lab.use_task(
        _write_local_global_states, dependencies=[GLOBAL_STATE.value, LOCAL_STATE.value]
    )

    with BaseLayout(
        local_state=LOCAL_STATE,
        children=children,
        story_name=LOCAL_STATE.value.story_id,
        story_title=LOCAL_STATE.value.title,
        force_demo=True
    ):
        pass
