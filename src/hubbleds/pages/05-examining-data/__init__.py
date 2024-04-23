import solara
from cosmicds import load_custom_vue_components
from cosmicds.components import ScaffoldAlert, ViewerLayout
from glue_jupyter import JupyterApplication
from glue_plotly.viewers.scatter import PlotlyScatterView 
from pathlib import Path
from reacton import ipyvuetify as rv

from ...state import GLOBAL_STATE, LOCAL_STATE
from .component_state import ComponentState, Marker


GUIDELINE_ROOT = Path(__file__).parent / "guidelines"

component_state = ComponentState()

gjapp = JupyterApplication(GLOBAL_STATE.data_collection, GLOBAL_STATE.session)

viewer = gjapp.new_data_viewer(PlotlyScatterView)

@solara.component
def Page():
    # Custom vue-only components have to be registered in the Page element
    #  currently, otherwise they will not be available in the front-end
    load_custom_vue_components()

    # Solara's reactivity is often tied to the _context_ of the Page it's
    #  being rendered in. Currently, in order to trigger subscribed callbacks,
    #  state connections need to be initialized _inside_ a Page.
    # component_state.setup()

    solara.Text(
        f"Current step: {component_state.current_step.value}, "
        f"Next step: {Marker(component_state.current_step.value.value + 1)}"
        f"Can advance: {component_state.can_transition(next=True)}"
    )

    with rv.Row():
        with rv.Col(cols=4):
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineRandomVariability.vue",
                event_next_callback=lambda *args: component_state.transition_next(),
                can_advance=component_state.can_transition(next=True),
                show=component_state.is_current_step(Marker.ran_var1),
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineFinishedClassmates.vue",
                event_next_callback=lambda *args: component_state.transition_next(),
                event_back_callback=lambda *args: component_state.transition_previous(),
                can_advance=component_state.can_transition(next=True),
                show=component_state.is_current_step(Marker.fin_cla1),
            )
            ScaffoldAlert(
                GUIDELINE_ROOT / "GuidelineClassData.vue",
                event_next_callback=lambda *args: component_state.transition_next(),
                event_back_callback=lambda *args: component_state.transition_previous(),
                can_advance=component_state.can_transition(next=True),
                show=component_state.is_current_step(Marker.cla_dat1),
            )

        with rv.Col(cols=8):
            ViewerLayout(viewer=viewer)
