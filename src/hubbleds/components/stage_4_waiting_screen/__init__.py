from ipywwt import WWTWidget
import reacton.ipyvuetify as rv
import solara
from typing import Callable

from hubbleds.components.counter import Counter


@solara.component
def Stage4WaitingScreen(
    can_advance: bool,
    on_advance_click: Callable,
    completed_count: int,
):

    with rv.Card():
        with rv.Toolbar(color="warning", dense=True, dark=True):
            rv.ToolbarTitle(class_="text-h6 text-uppercase font-weight-regular",
                                 children=["Take a quick break"])
            rv.Spacer()

        with rv.CardText():
            with rv.Container():
                with solara.Row():
                   solara.HTML(
                        unsafe_innerHTML=
                        """
                        <p>You and your classmates will be comparing your measurements in the next section, but we need to wait a few moments for more of them to catch up.</p>
                        <p>While you wait, you can explore the same sky viewer you saw in the introduction.</p>
                        <p>You will be able to advance when enough classmates are ready to proceed.</p>
                        """
                    )

                WWTWidget.element()

                Counter(text="Number of classmates who have completed measurements", value=completed_count)

                with solara.Row():
                    solara.Button(label="Advance",
                                  on_click=on_advance_click,
                                  disabled=not can_advance)

                   
