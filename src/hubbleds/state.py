from pydantic import BaseModel, computed_field, field_validator, Field
from solara import Reactive
from cosmicds.state import BaseState, GLOBAL_STATE, BaseLocalState
from typing import Optional
import solara
import datetime
from functools import cached_property
from astropy.table import Table
from pydantic import Field

from solara.toestand import Ref

from .free_response import FreeResponses
from .mc_score import MCScoring

from typing import Callable, Tuple

ELEMENT_REST = {"H-α": 6562.79, "Mg-I": 5176.7}

from cosmicds.logger import setup_logger

logger = setup_logger("HUBBLEDS-STATE")


class SpectrumData(BaseModel):
    name: str
    wave: list[float]
    flux: list[float]
    ivar: list[float]


class GalaxyData(BaseModel):
    id: int
    name: str
    ra: float
    decl: float
    z: float
    type: str
    element: str

    @cached_property
    def spectrum(self):
        from hubbleds.remote import LOCAL_API

        return LOCAL_API.load_spectrum_data(self, LOCAL_STATE)

    @cached_property
    def spectrum_as_data_frame(self):
        from hubbleds.remote import LOCAL_API

        spec_data = LOCAL_API.load_spectrum_data(self, LOCAL_STATE)

        return Table({"wave": spec_data.wave, "flux": spec_data.flux}).to_pandas()

    @property
    def rest_wave_value(self) -> float:
        return round(ELEMENT_REST[self.element])

    @property
    def redshift_rest_wave_value(self) -> float:
        return round(ELEMENT_REST[self.element] * (1 + self.z))


class StudentMeasurement(BaseModel):
    student_id: int
    class_id: int | None = None
    rest_wave_unit: str = "angstrom"
    obs_wave_value: float | None = None
    obs_wave_unit: str = "angstrom"
    velocity_value: float | None = None
    velocity_unit: str = "km/s"
    ang_size_value: float | None = None
    ang_size_unit: str = "arcsecond"
    est_dist_value: float | None = None
    est_dist_unit: str = "Mpc"
    measurement_number: str | None = None
    brightness: float = 0
    galaxy: Optional[GalaxyData] = None

    @computed_field
    @property
    def galaxy_id(self) -> int:
        return self.galaxy.id if self.galaxy else 0

    @computed_field
    @property
    def rest_wave_value(self) -> float:
        if self.galaxy:
            return self.galaxy.rest_wave_value
        return 0

    # @computed_field
    # @property
    # def last_modified(self) -> str:
    #     return f"{datetime.datetime.now(datetime.UTC)}"


class BaseSummary(BaseModel):
    hubble_fit_value: float
    hubble_fit_unit: str = "km / s"
    age_value: float
    age_unit: str = "Gyr"
    last_data_update: Optional[datetime.datetime] = None


class StudentSummary(BaseSummary):
    student_id: int


class ClassSummary(BaseSummary):
    class_id: int


class MCScore(BaseModel):
    tag: str = ""


class LocalState(BaseLocalState):
    title: str = "Hubble's Law"
    story_id: str = "hubbles_law"
    measurements: list[StudentMeasurement] = []
    example_measurements: list[StudentMeasurement] = []
    class_measurements: list[StudentMeasurement] = []
    all_measurements: list[StudentMeasurement] = []
    student_summaries: list[StudentSummary] = []
    class_summaries: list[ClassSummary] = []
    measurements_loaded: bool = False
    calculations: dict = {}
    validation_failure_counts: dict = {}
    has_best_fit_galaxy: bool = False
    best_fit_slope: Optional[float] = None
    enough_students_ready: bool = False
    class_data_students: list = []
    class_data_info: dict = {}
    mc_scoring: MCScoring = Field(default_factory=MCScoring)
    free_responses: FreeResponses = Field(default_factory=FreeResponses)
    show_snackbar: bool = False
    snackbar_message: str = ""
    stage_4_class_data_students: list[int] = []
    stage_5_class_data_students: list[int] = []
    last_route: Optional[str] = None

    @cached_property
    def galaxies(self) -> dict[int, GalaxyData]:
        from hubbleds.remote import LOCAL_API

        gal_data = LOCAL_API.get_galaxies(LOCAL_STATE)
        return { galaxy.id: galaxy for galaxy in gal_data }

    def as_dict(self):
        return self.model_dump(exclude={
            "example_measurements",
            "measurements",
            "measurements_loaded",
            "class_measurements",
            "all_measurements",
            "student_summaries",
            "class_summaries",
        })

    def get_measurement(self, galaxy_id: int) -> StudentMeasurement | None:
        return next((x for x in self.measurements if x.galaxy_id == galaxy_id), None)

    def get_example_measurement(self, galaxy_id: int) -> StudentMeasurement | None:
        return next(
            (x for x in self.example_measurements if x.galaxy_id == galaxy_id), None
        )

    def get_measurement_index(self, galaxy_id: int) -> int | None:
        return next(
            (i for i, x in enumerate(self.measurements) if x.galaxy_id == galaxy_id),
            None,
        )

    def get_example_measurement_index(self, galaxy_id: int) -> int | None:
        return next(
            (
                i
                for i, x in enumerate(self.example_measurements)
                if x.galaxy_id == galaxy_id
            ),
            None,
        )

    def question_completed(self, tag: str) -> bool:
        if tag in self.free_responses:
            return self.free_responses[tag].completed
        elif tag in self.mc_scoring:
            return self.mc_scoring[tag].completed

        return False


LOCAL_STATE = solara.reactive(LocalState())


def get_free_response(local_state: Reactive[LocalState], tag: str):
    # get question as serializable dictionary
    # also initializes the question by using get_or_create method
    free_responses = local_state.value.free_responses
    return free_responses.get_or_create(tag).model_dump()


def get_multiple_choice(local_state: Reactive[LocalState], tag: str):
    # get question as serializable dictionary
    # also initializes the question by using get_or_create method
    multiple_choices = local_state.value.mc_scoring
    return multiple_choices.get_model_dump(tag)


def mc_callback(
    event,
    local_state: Reactive[LocalState],
    callback: Optional[Callable[[MCScoring], None]] = None,
):
    """
    Multiple Choice callback function
    """

    mc_scoring = local_state.value.mc_scoring
    piggybank_total = Ref(local_state.fields.piggybank_total)
    logger.info(f"MC Callback Event: {event[0]}")
    logger.info(f"Current mc_scoring: {mc_scoring}")

    # mc-initialize-callback returns data which is a string
    if event[0] == "mc-initialize-response":
        if event[1] not in mc_scoring:
            mc_scoring.add(event[1])
            LOCAL_STATE.set(local_state.value)
            if callback is not None:
                callback(mc_scoring)

    # mc-score event returns a data which is an mc-score dictionary (includes tag)
    elif event[0] == "mc-score":
        mc_scoring.update_mc_score(**event[1])

        # update piggybank_total
        try:
            score = int(event[1]["score"])
        except (TypeError, ValueError):
            score = 0
        total_score = piggybank_total.value + score
        piggybank_total.set(total_score)
        
        if callback is not None:
            callback(mc_scoring)

    else:
        raise ValueError(f"Unknown event in mc_callback: <<{event}>> ")


def fr_callback(
    event: Tuple[str, dict[str, str]],
    local_state: Reactive[LocalState],
    callback: Optional[Callable] = None,
):
    """
    Free Response callback function
    """
    
    free_responses = local_state.value.free_responses
    
    logger.info(f"Free Response Callback Event: {event[0]}")
    logger.info(f"Current fr_response value: {free_responses}")
    if event[0] == "fr-initialize":
        if event[1]["tag"] not in free_responses:
            free_responses.add(event[1]["tag"])
            LOCAL_STATE.set(local_state.value)
            if callback is not None:
                callback()

    elif event[0] == "fr-update":
        free_responses.update(event[1]["tag"], response=event[1]["response"])
        LOCAL_STATE.set(local_state.value)
        print(f"local state set")
        if callback is not None:
            if (len(event) > 1) and ("response" in event[1]):
                callback()
    else:
        raise ValueError(f"Unknown event in fr_callback: <<{event}>> ")
