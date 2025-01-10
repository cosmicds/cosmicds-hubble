
import solara
from reacton import ipyvuetify as rv
from hubbleds.state import LOCAL_STATE
from hubbleds.widgets import SelectionToolWidget
from typing import Callable
from hubbleds.state import GalaxyData


@solara.component
def SelectionTool(
    show_galaxies: bool,
    galaxy_selected_callback: Callable,
    galaxy_added_callback: Callable,
    deselect_galaxy_callback: Callable,
    selected_measurement: dict | None,
):
    with rv.Card() as main:
        with rv.Card(class_="pa-0 ma-0", elevation=0):
            tool_container = rv.Html(tag="div")

        def _add_widget():
            selection_tool_widget = SelectionToolWidget(
                table_layer_data={
                    k: [x.dict()[k] for x in LOCAL_STATE.value.galaxies.values()]
                    for k in ["id", "ra", "decl"]
                }
            )

            tool_widget = solara.get_widget(tool_container)
            tool_widget.children = (selection_tool_widget,)

            def cleanup():
                tool_widget.children = ()
                selection_tool_widget.close()

            return cleanup

        solara.use_effect(_add_widget, dependencies=[])

        def _on_galaxy_selected(gal: dict):
            data = LOCAL_STATE.value.galaxies[int(gal["id"])]
            galaxy_added_callback(data)

        def _on_current_galaxy_changed(change: dict):
            gal = change["new"]
            data = LOCAL_STATE.value.galaxies[int(gal["id"])]
            galaxy_selected_callback(data)

        def _setup_callbacks():
            selection_tool_widget = solara.get_widget(tool_container).children[0]

            selection_tool_widget.on_galaxy_selected = _on_galaxy_selected
            selection_tool_widget.observe(
                _on_current_galaxy_changed,
                ["current_galaxy"],
            )
            selection_tool_widget.deselect_galaxy = deselect_galaxy_callback

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
