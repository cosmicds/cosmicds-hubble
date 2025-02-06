import solara
import enum
from pydantic import BaseModel, computed_field
from cosmicds.state import BaseState
from hubbleds.base_marker import BaseMarker 
from hubbleds.base_component_state import BaseComponentState

class Marker(enum.Enum, BaseMarker):
    int_sli1 = enum.auto()

class IntroSlideshow(BaseModel):
    step: int = 0

class ComponentState(BaseComponentState, BaseState):
    current_step: Marker = Marker.int_sli1
    stage_id: str = "introduction"
    intro_slideshow_state: IntroSlideshow = IntroSlideshow()
    
    _max_step: int = 0 # not included in model
    
    @computed_field
    @property
    def total_steps(self) -> int:
        return len(Marker)
    
    # computed fields are included in the model when serialized
    @computed_field
    @property
    def max_step(self) -> int:
        self._max_step = max(self.current_step.value, self._max_step) # type: ignore
        return self._max_step
    
    @computed_field
    @property
    def progress(self) -> float:
        return round((self._max_step + 1) / self.total_steps, 3)


COMPONENT_STATE = solara.reactive(ComponentState())