from pydantic import BaseModel, field_validator, Field, computed_field
from cosmicds.state import BaseState
from hubbleds.base_marker import BaseMarker
import enum
from functools import cached_property
from hubbleds.base_component_state import BaseComponentState
import solara
from typing import Any

from hubbleds.state import LOCAL_STATE


class Marker(enum.Enum, BaseMarker):
    mee_gui1 = enum.auto()
    sel_gal1 = enum.auto()
    sel_gal2 = enum.auto()
    not_gal1 = enum.auto()
    sel_gal3 = enum.auto()
    sel_gal4 = enum.auto()
    cho_row1 = enum.auto()
    mee_spe1 = enum.auto()
    # spe_tut1 = enum.auto()  # This step doesn't seem to do anything?
    res_wav1 = enum.auto()
    obs_wav1 = enum.auto()
    obs_wav2 = enum.auto()
    dop_cal0 = enum.auto()
    dop_cal2 = enum.auto()
    dop_cal4 = enum.auto()
    dop_cal5 = enum.auto()
    che_mea1 = enum.auto()
    int_dot1 = enum.auto()
    dot_seq1 = enum.auto()
    dot_seq2 = enum.auto()
    dot_seq3 = enum.auto() # a
    dot_seq4 = enum.auto() # mark measurement on spectrum viewer
    dot_seq4a = enum.auto() 
    dot_seq5 = enum.auto() # plots should be connected
    dot_seq6 = enum.auto() # enable zoom 
    dot_seq7 = enum.auto()
    dot_seq8 = enum.auto()
    dot_seq10 = enum.auto()  
    dot_seq11 = enum.auto()  
    rem_vel1 = enum.auto() # need to be able to reameasure. should show old measurement in table still. 

    dot_seq14 = enum.auto()
    rem_gal1 = enum.auto()
    ref_dat1 = enum.auto()
    dop_cal6 = enum.auto()
    ref_vel1 = enum.auto()
    end_sta1 = enum.auto()
    nxt_stg = enum.auto()


class DopplerCalculation(BaseModel):
    step: int = 0
    length: int = 6
    current_title: str = ""
    validation_4_failed: bool = False
    validation_5_failed: bool = False
    interact_steps_5: list[int] = [3, 4]
    max_step_completed_5: int = 0
    student_c: float = 0
    velocity_calculated: bool = False
    completed: bool = False

    @cached_property
    def titles(self) -> list[str]:
        return [
            "Doppler Calculation",
            "Doppler Calculation",
            "Doppler Calculation",
            "Reflect on Your Result",
            "Enter Speed of Light",
            "Your Galaxy's Velocity",
        ]


class DotPlotTutorial(BaseModel):
    step: int = 0
    length: int = 4
    max_step_completed: int = 0
    current_title: str = ""

class VelocityReflection(BaseModel):
    step: int = 0
    max_step_completed: int = 0

class ComponentState(BaseComponentState, BaseState):
    current_step: Marker = Marker.mee_gui1
    stage_id: str = "spectra_&_velocity"
    show_example_galaxy: bool = False
    selected_galaxy: int = 0
    selected_galaxies: list[int] = []
    galaxy_is_selected: bool = False
    selected_example_galaxy: int = 0
    total_galaxies: int = 0
    spectrum_tutorial_opened: bool = False
    rest_wave_tool_activated: bool = False
    obs_wave_tool_used: bool = False
    spectrum_clicked: bool = False
    zoom_tool_activated: bool = False # has it ever been used?
    zoom_tool_active: bool = False # is it currently on?
    doppler_calc_reached: bool = False
    obs_wave: float = 0
    show_doppler_dialog: bool = Field(False, exclude=True)
    doppler_state: DopplerCalculation = DopplerCalculation()
    show_dotplot_tutorial_dialog: bool = False
    dotplot_tutorial_state: DotPlotTutorial = DotPlotTutorial()
    dotplot_tutorial_finished: bool = False
    has_bad_velocities: bool = False
    has_multiple_bad_velocities: bool = False
    obs_wave_total: int = 0
    velocities_total: int = 0
    show_reflection_dialog: bool = False
    velocity_reflection_state: VelocityReflection = VelocityReflection()
    reflection_complete: bool = False
    show_dop_cal4_values: bool = False

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
    def mee_gui1_gate(self) -> bool:
        return (
            self.current_step == Marker.mee_gui1
            and self.total_galaxies == 0
            and not self.selected_galaxy
        )

    @property
    def not_gal1_gate(self) -> bool:
        return self.total_galaxies >= 1

    @property
    def sel_gal3_gate(self) -> bool:
        return self.total_galaxies >= 1

    @property
    def sel_gal4_gate(self) -> bool:
        return self.total_galaxies == 5

    @property
    def cho_row1_gate(self) -> bool:
        return self.total_galaxies == 5

    @property
    def mee_spe1_gate(self) -> bool:
        return bool(self.selected_example_galaxy)

    @property
    def spe_tut1_gate(self) -> bool:
        return bool(self.selected_example_galaxy) and self.spectrum_tutorial_opened

    @property
    def res_wav1_gate(self) -> bool:
        return bool(self.selected_example_galaxy) and self.spectrum_tutorial_opened

    @property
    def obs_wav1_gate(self) -> bool:
        return self.rest_wave_tool_activated

    @property
    def obs_wav2_gate(self) -> bool:
        return self.obs_wave_tool_used

    @property
    def dop_cal0_gate(self) -> bool:
        return self.zoom_tool_activated

    @property
    def dot_seq1_gate(self) -> bool:
        return self.dotplot_tutorial_finished
    
    @property
    def dot_seq10_gate(self) -> bool:
        return LOCAL_STATE.value.question_completed("vel_meas_consensus")

    @property
    def ref_dat1_gate(self) -> bool:
        return self.obs_wave_total >= 5

    @property
    def dop_cal6_gate(self) -> bool:
        return self.reflection_complete

    @property
    def ref_vel1_gate(self) -> bool:
        return self.velocities_total >= 5

    @property
    def nxt_stg_gate(self) -> bool:
        return not (self.has_bad_velocities or self.has_multiple_bad_velocities)


COMPONENT_STATE = solara.reactive(ComponentState())
