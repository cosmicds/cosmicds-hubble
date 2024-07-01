from random import randint

import solara
from solara import Reactive
from hubbleds.base_component_state import BaseComponentState
from glue.core import Data
from reacton import ipyvuetify as rv
from hubbleds.state import LOCAL_STATE
from hubbleds.widgets import SelectionToolWidget
from typing import Callable
from hubbleds.state import GalaxyData, StudentMeasurement
from solara.lab import Ref


@solara.component
def SelectionTool(
    show_galaxies: bool,
    galaxy_selected_callback: Callable,
    galaxy_added_callback: Callable,
    selected_measurement: dict | None,
    dependencies: list = None,
):
    with rv.Card() as main:
        with rv.Card(class_="pa-0 ma-0", elevation=0):
            tool_container = rv.Html(tag="div")

        def _add_widget():
            selection_tool_widget = SelectionToolWidget(
                table_layer_data={
                    k: [x.dict()[k] for x in LOCAL_STATE.value.galaxies]
                    for k in LOCAL_STATE.value.galaxies[0].dict()
                }
            )

            tool_widget = solara.get_widget(tool_container)
            tool_widget.children = (selection_tool_widget,)

            def cleanup():
                tool_widget.children = ()
                selection_tool_widget.close()

            return cleanup

        solara.use_effect(_add_widget, dependencies=[])

        def _setup_callbacks():
            selection_tool_widget = solara.get_widget(tool_container).children[0]

            selection_tool_widget.on_galaxy_selected = (
                lambda gal: galaxy_added_callback(GalaxyData(**gal))
            )
            selection_tool_widget.observe(
                lambda change: galaxy_selected_callback(
                    GalaxyData(**change["new"]) if len(change["new"]) > 0 else None
                ),
                ["current_galaxy"],
            )

        solara.use_effect(_setup_callbacks, dependencies=[])

        def _update_selection():
            selection_tool_widget = solara.get_widget(tool_container).children[0]

            # Update selection tool
            selection_tool_widget.show_galaxies(show_galaxies)
            selection_tool_widget.highlighted = show_galaxies

            if show_galaxies:
                selection_tool_widget.center_on_start_coordinates()

        solara.use_effect(
            _update_selection, dependencies=[show_galaxies]
        )

        def _update_position():
            selection_tool_widget = solara.get_widget(tool_container).children[0]

            # Update the selected position
            if selected_measurement is not None:
                selection_tool_widget.go_to_location(
                    selected_measurement["galaxy"]["ra"],
                    selected_measurement["galaxy"]["decl"],
                )

        solara.use_effect(
            _update_position, dependencies=[selected_measurement]
        )

        return main
