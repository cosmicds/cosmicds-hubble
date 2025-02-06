import solara
import enum

from pydantic import field_validator, computed_field

from cosmicds.state import BaseState
from hubbleds.base_marker import BaseMarker 
from hubbleds.base_component_state import (
    BaseComponentState,
    transition_to,
    transition_previous,
    transition_next
)
from hubbleds.state import LOCAL_STATE

from typing import Any, Optional

class Marker(enum.Enum, BaseMarker):
    ang_siz1 = enum.auto()
    cho_row1 = enum.auto()
    ang_siz2 = enum.auto()
    ang_siz2b = enum.auto()
    ang_siz3 = enum.auto()
    ang_siz4 = enum.auto()
    ang_siz5 = enum.auto()
    est_dis1 = enum.auto()
    est_dis2 = enum.auto()
    est_dis3 = enum.auto()
    est_dis4 = enum.auto()
    dot_seq1 = enum.auto()
    dot_seq2 = enum.auto() # MC ang_meas_consensus
    dot_seq3 = enum.auto()
    dot_seq4 = enum.auto()
    dot_seq4a = enum.auto()	 # MC ang_meas_dist_relation
    ang_siz5a  = enum.auto()
    # ang_siz6  = enum.auto() We skipped this in the voila version
    dot_seq5  = enum.auto()
    dot_seq5a = enum.auto() # Skipping 2nd meas. sequence 5a-7
    dot_seq5b = enum.auto() 
    dot_seq5c = enum.auto()
    # dot_seq6  = enum.auto()	# MC ang_meas_consensus_2
    # dot_seq7 = enum.auto()
    rep_rem1 = enum.auto()
    fil_rem1 = enum.auto()
    end_sta3 = enum.auto() #This guideline doesn't actually exist - just including it to allow an exit gate on the previous guideline.



class ComponentState(BaseComponentState, BaseState):
    current_step: Marker = Marker.ang_siz1
    stage_id: str = "distance_measurements"
    
    example_angular_sizes_total: int = 0
    angular_sizes_total: int = 0
    dosdonts_tutorial_opened: bool = False
    selected_galaxy: dict = {}
    selected_example_galaxy: dict = {}
    show_ruler: bool = False
    meas_theta: float = 0.0
    ruler_click_count: int = 0
    n_meas: int = 0
    bad_measurement: bool = False
    distances_total: int = 0
    fill_est_dist_values: bool = False
    
    show_dotplot_lines: bool = True
    angular_size_line: Optional[float | int] = None
    distance_line: Optional[float | int] = None
    
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
    def ang_siz2_gate(self):
        return bool(self.selected_example_galaxy)

    @property
    def ang_siz4_gate(self):
        return self.ruler_click_count == 1

    @property
    def ang_siz5_gate(self):
        return self.n_meas > 0

    @property
    def dot_seq3_gate(self):
        return LOCAL_STATE.value.question_completed("ang_meas_consensus")

    @property
    def ang_siz5a_gate(self):
        return LOCAL_STATE.value.question_completed("ang_meas_dist_relation")

    @property
    def dot_seq7_gate(self):
        return LOCAL_STATE.value.question_completed("ang_meas_consensus_2")

    @property
    def dot_seq5_gate(self):
        return (
            bool(self.dosdonts_tutorial_opened)
        )
    
    @property
    def fil_rem1_gate(self):
        return self.angular_sizes_total >=5

    @property
    def end_sta3_gate(self):
        return self.distances_total >= 5

COMPONENT_STATE = solara.reactive(ComponentState())
