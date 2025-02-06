import solara

from pydantic import BaseModel, field_validator, computed_field

from cosmicds.state import BaseState
from hubbleds.base_marker import BaseMarker
from hubbleds.base_component_state import BaseComponentState
from hubbleds.state import LOCAL_STATE

import enum

from typing import List, Any

class Marker(enum.Enum, BaseMarker):
    ran_var1 = enum.auto()
    fin_cla1 = enum.auto()
    cla_res1 = enum.auto()
    rel_age1 = enum.auto() # MC age-slope-trend
    cla_age1 = enum.auto()
    cla_age2 = enum.auto()
    cla_age3 = enum.auto()
    cla_age4 = enum.auto()
    lea_unc1 = enum.auto()
    mos_lik1 = enum.auto()
    age_dis1 = enum.auto()
    sho_mya1 = enum.auto()
    mos_lik2 = enum.auto()
    mos_lik3 = enum.auto()
    mos_lik4 = enum.auto()
    con_int1 = enum.auto()
    con_int2 = enum.auto()
    con_int3 = enum.auto()

    cla_dat1 = enum.auto()
    # tre_lin2c = enum.auto()
    bes_fit1c = enum.auto()
    you_age1c = enum.auto()
    cla_res1c = enum.auto()
    cla_age1c = enum.auto()
    age_dis1c = enum.auto()
    con_int2c = enum.auto()
    
    two_his1 = enum.auto()
    two_his2 = enum.auto() # MC histogram-range
    two_his3 = enum.auto() # MC histogram-percent-range
    two_his4 = enum.auto() # MC histogram-distribution
    two_his5 = enum.auto()
    mor_dat1 = enum.auto()
    end_sta5 = enum.auto() # This avoids the last guideline "next" being locked by the can_transition logic.


class UncertaintyState(BaseModel):
    step: int = 0

class ComponentState(BaseComponentState, BaseState):
    current_step: Marker = Marker.first()
    stage_id: str = "class_results_and_uncertainty"
    student_low_age: int = 0
    student_high_age: int = 0
    class_low_age: int = 0
    class_high_age: int = 0
    class_data_size: int = 0
    uncertainty_state: UncertaintyState = UncertaintyState()
    uncertainty_slideshow_finished: bool = False
    class_best_fit_clicked: bool = False
    
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
    def cla_age1_gate(self) -> bool:
        return LOCAL_STATE.value.question_completed("age-slope-trend")

    @property
    def mos_lik1_gate(self) -> bool:
        return COMPONENT_STATE.value.uncertainty_slideshow_finished

    # @property
    # def con_int1_gate(self) -> bool:
    #     return LOCAL_STATE.value.question_completed("best-guess-age") and LOCAL_STATE.value.question_completed("my-reasoning")    
    
    # @property
    # def cla_dat1_gate(self) -> bool:
    #     return LOCAL_STATE.value.question_completed("likely-low-age") and LOCAL_STATE.value.question_completed("likely-high-age") and LOCAL_STATE.value.question_completed("my-reasoning-2")  

    @property
    def you_age1c_gate(self) -> bool:
        return COMPONENT_STATE.value.class_best_fit_clicked
    
    # @property
    # def two_his1_gate(self) -> bool:
    #     return LOCAL_STATE.value.question_completed("new-most-likely-age") and LOCAL_STATE.value.question_completed("new-likely-low-age") and LOCAL_STATE.value.question_completed("new-likely-high-age") and LOCAL_STATE.value.question_completed("my-updated-reasoning")  

    @property
    def two_his3_gate(self) -> bool:
        return LOCAL_STATE.value.question_completed("histogram-range")
    
    @property
    def two_his4_gate(self) -> bool:
        return LOCAL_STATE.value.question_completed("histogram-percent-range")
    
    @property
    def two_his5_gate(self) -> bool:
        return LOCAL_STATE.value.question_completed("histogram-distribution")

    # @property
    # def mor_dat1_gate(self) -> bool:
    #     return LOCAL_STATE.value.question_completed("unc-range-change-reasoning")
    

COMPONENT_STATE = solara.reactive(ComponentState())
