import solara

from pydantic import BaseModel, field_validator, computed_field

from cosmicds.state import BaseState
from hubbleds.base_marker import BaseMarker
from hubbleds.base_component_state import BaseComponentState
from hubbleds.state import LOCAL_STATE

import enum

from typing import Any

class Marker(enum.Enum, BaseMarker):
    exp_dat1 = enum.auto()
    tre_dat1 = enum.auto() # MC tre-dat-mc1
    tre_dat2 = enum.auto()
    tre_dat3 = enum.auto() # MC tre-dat-mc3
    rel_vel1 = enum.auto() # MC galaxy-trend
    hub_exp1 = enum.auto()
    tre_lin1 = enum.auto()
    tre_lin2 = enum.auto()
    bes_fit1 = enum.auto()
    age_uni1 = enum.auto()
    hyp_gal1 = enum.auto()
    age_rac1 = enum.auto()
    age_uni2 = enum.auto()
    age_uni3 = enum.auto()
    age_uni4 = enum.auto()
    you_age1 = enum.auto()
    sho_est1 = enum.auto()
    sho_est2 = enum.auto()
    end_sta4 = enum.auto() # This avoids the last guideline "next" being locked by the can_transition logic.


class HubbleSlideshow(BaseModel):
    step: int = 0
    max_step_completed: int = 0


class ComponentState(BaseComponentState, BaseState):
    current_step: Marker = Marker.first()
    stage_id: str = "explore_data"
    show_hubble_slideshow_dialog: bool = False
    hubble_slideshow_finished: bool = False
    hubble_slideshow_state: HubbleSlideshow = HubbleSlideshow()
    draw_click_count: int = 0
    best_fit_click_count: int = 0
    best_fit_gal_vel: float = 100
    best_fit_gal_dist: float = 8000
    class_data_displayed: bool = False
    
    _max_step: int = 0 # not included in model
    
    # computed fields are included in the model when serialized
    @computed_field
    @property
    def total_steps(self) -> int:
        # ignore the last marker, which is a dummy marker
        return len(Marker) - 1



    @field_validator("current_step", mode="before")
    def convert_int_to_enum(cls, v: Any) -> Marker:
        if isinstance(v, int):
            return Marker(v)
        return v
    
    @property
    def tre_dat2_gate(self) -> bool:
        return LOCAL_STATE.value.question_completed("tre-dat-mc1")

    @property
    def tre_dat3_gate(self) -> bool:
        return COMPONENT_STATE.value.class_data_displayed
    
    @property
    def rel_vel1_gate(self) -> bool:
        return LOCAL_STATE.value.question_completed("tre-dat-mc3")
    
    @property
    def hub_exp1_gate(self) -> bool:
        return LOCAL_STATE.value.question_completed("galaxy-trend")

    @property
    def tre_lin1_gate(self) -> bool:
        return COMPONENT_STATE.value.hubble_slideshow_finished
    
    @property
    def bes_fit1_gate(self) -> bool:
        return COMPONENT_STATE.value.draw_click_count > 0
    
    @property
    def age_uni1_gate(self) -> bool:
        return COMPONENT_STATE.value.best_fit_click_count > 0

    
    # @property
    # def sho_est2_gate(self) -> bool:
    #     return LOCAL_STATE.value.question_completed("shortcoming-1") and LOCAL_STATE.value.question_completed("shortcoming-2")


COMPONENT_STATE = solara.reactive(ComponentState())

