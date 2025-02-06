import solara
import enum
from pydantic import BaseModel, computed_field
from cosmicds.state import BaseState
from hubbleds.base_marker import BaseMarker 
from hubbleds.base_component_state import BaseComponentState
from hubbleds.components import STAGE_2_SLIDESHOW_LENGTH

class Marker(enum.Enum, BaseMarker):
    mea_dis1 = enum.auto()

class DistanceSlideshow(BaseModel):
    step: int = 0
    max_step_completed: int = 0

class ComponentState(BaseComponentState, BaseState):
    current_step: Marker = Marker.mea_dis1
    stage_id: str = "distance_introduction"
    distance_slideshow_state: DistanceSlideshow = DistanceSlideshow()
    
    @computed_field
    @property
    def total_steps(self) -> int:
        return STAGE_2_SLIDESHOW_LENGTH
    
    @computed_field
    @property
    def progress(self) -> float:
        return (self.distance_slideshow_state.max_step_completed + 1) / self.total_steps
    
COMPONENT_STATE = solara.reactive(ComponentState())