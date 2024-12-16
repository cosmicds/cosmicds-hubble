from cosmicds.utils import CDSJSONEncoder
from hubbleds.state import ClassSummary, StudentMeasurement, StudentSummary
from contextlib import closing
from io import BytesIO
import json
from astropy.io import fits
from hubbleds.state import GalaxyData, SpectrumData, LocalState
from cosmicds.remote import BaseAPI
from cosmicds.state import GlobalState, BaseState, GLOBAL_STATE
from solara import Reactive
from solara.toestand import Ref
from cosmicds.logger import setup_logger
from typing import List

from pathlib import Path
from csv import DictReader

logger = setup_logger("API")

from .data_management import DB_VELOCITY_FIELD
from numpy.random import Generator, PCG64, SeedSequence
from numpy import arange, asarray, ravel, column_stack
from typing import Any

ELEMENT_REST = {"H-α": 6562.79, "Mg-I": 5176.7}
DEBOUNCE_TIMEOUT = 1


class LocalAPI(BaseAPI):
    def get_galaxies(self, local_state: Reactive[LocalState]) -> list[GalaxyData]:
        galaxy_data_json = self.request_session.get(
            f"{self.API_URL}/{local_state.value.story_id}/galaxies?types=Sp"
        ).json()

        galaxy_data = [GalaxyData(**x) for x in galaxy_data_json]

        return galaxy_data

    def load_spectrum_data(
        self, gal_data: GalaxyData, local_state: Reactive[LocalState]
    ) -> SpectrumData | None:
        file_name = f"{gal_data.name.replace('.fits', '')}.fits"

        type_folders = {"Sp": "spiral", "E": "elliptical", "Ir": "irregular"}
        folder = type_folders[gal_data.type]
        url = (
            f"{self.API_URL}/{local_state.value.story_id}/spectra/{folder}/{file_name}"
        )
        response = self.request_session.get(url)

        with closing(BytesIO(response.content)) as f:
            f.name = gal_data.name

            with fits.open(f) as hdulist:
                data = hdulist["COADD"].data if "COADD" in hdulist else None

        if data is None:
            logger.error("No extension named 'COADD' in spectrum file.")
            return

        spec_data = SpectrumData(
            name=gal_data.name,
            wave=10 ** data["loglam"],
            flux=data["flux"],
            ivar=data["ivar"],
        )

        logger.info("Loaded spectrum data for galaxy `%s` from database.", gal_data.id)

        return spec_data

    def get_dummy_data(self) -> List[StudentMeasurement]:
        path = (Path(__file__).parent / "data" / "dummy_student_data.csv").as_posix()
        measurements = []
        galaxy_prefix = "galaxy."
        galaxy_pref_len = len(galaxy_prefix)
        with open(path, 'r') as f:
            reader = DictReader(f)
            for row in reader:
                galaxy = {}
                keys_to_remove = set()
                for key, value in row.items():
                    if key.startswith(galaxy_prefix):
                        galaxy[key[galaxy_pref_len:]] = value
                        keys_to_remove.add(key)
                measurement = { k: v for k, v in row.items() if k not in keys_to_remove }
                measurement["galaxy"] = galaxy
                measurements.append(StudentMeasurement(**measurement))
        return measurements

    def get_measurements(
        self, global_state: Reactive[GlobalState], local_state: Reactive[LocalState]
    ) -> list[StudentMeasurement]:
        url = (
            f"{self.API_URL}/{local_state.value.story_id}/measurements/"
            f"{global_state.value.student.id}"
        )
        r = self.request_session.get(url)
            
        measurements = Ref(local_state.fields.measurements)
        if r.status_code == 200:
            measurement_json = r.json()

            parsed_measurements = []

            for measurement in measurement_json["measurements"]:
                measurement = StudentMeasurement(**measurement)
                parsed_measurements.append(measurement)

            measurements.set(parsed_measurements)

        Ref(local_state.fields.measurements_loaded).set(True)

        logger.info("Loaded measurements from database.")

        return measurements.value

    def get_sample_measurements(
        self, global_state: Reactive[GlobalState], local_state: Reactive[LocalState]
    ) -> list[StudentMeasurement]:
        r = self.request_session.get(
            f"{self.API_URL}/{local_state.value.story_id}/sample-"
            f"measurements/{global_state.value.student.id}"
        )

        sample_measurement_json = r.json()

        if len(sample_measurement_json["measurements"]) == 0:
            logger.info(
                "Failed to find sample galaxies for user `%s`: creating new "
                "sample measurement.",
                global_state.value.student.id,
            )
            sample_gal_data = LOCAL_API.get_sample_galaxy(local_state)
            for meas in ['first', 'second']:
                sample_measurement_json["measurements"].append(
                    StudentMeasurement(
                        student_id=global_state.value.student.id,
                        galaxy=sample_gal_data,
                        measurement_number=meas
                    ).dict()
                )
        elif len(sample_measurement_json["measurements"]) == 1:
            logger.info(
                "Example measurements only had the first. Creating missing second measurement"
            )
            sample_gal_data = LOCAL_API.get_sample_galaxy(local_state)
            sample_measurement_json["measurements"].append(
                StudentMeasurement(
                    student_id=global_state.value.student.id,
                    galaxy=sample_gal_data,
                    measurement_number='second'
                ).dict()
            )

        sample_measurements = Ref(local_state.fields.example_measurements)
        parsed_sample_measurements = []

        for measurement in sample_measurement_json["measurements"]:
            measurement = StudentMeasurement(**measurement)
            parsed_sample_measurements.append(measurement)

        sample_measurements.set(parsed_sample_measurements)

        logger.info("Loaded example measurements from database.")

        return sample_measurements.value

    def put_measurements(
        self, global_state: Reactive[GlobalState], local_state: Reactive[LocalState]
    ):  
        
        if not GLOBAL_STATE.value.update_db: 
            logger.info('Skipping DB write')
            return False
        
        url = f"{self.API_URL}/{local_state.value.story_id}/submit-measurement/"

        for measurement in local_state.value.measurements:
            r = self.request_session.put(url, json=measurement.dict(exclude={"galaxy"}))

            if r.status_code != 200:
                logger.warning(
                    f"Failed to add measurement for galaxy `%s` by student `%s`.",
                    global_state.value.student.id,
                    measurement.galaxy_id,
                )

        logger.info(
            "Stored measurements for student `%s`.",
            global_state.value.student.id,
        )
        return True

    def put_sample_measurements(
        self, global_state: Reactive[GlobalState], local_state: Reactive[LocalState]
    ):
        if not GLOBAL_STATE.value.update_db: 
            logger.info('Skipping DB write')
            return False
        
        url = f"{self.API_URL}/{local_state.value.story_id}/sample-measurement/"
    
        for i, measurement in enumerate(local_state.value.example_measurements):
            if i == 0:
                logger.info(
                    f"Adding example measurement for galaxy `%s` by student `%s`.",
                    measurement.galaxy_id,
                    global_state.value.student.id,
                )

            r = self.request_session.put(url, json=measurement.dict(exclude={"galaxy"}))

            if r.status_code != 200:
                logger.warning(
                    f"Failed to add example measurement for galaxy `%s` by student `%s`.",
                    measurement.galaxy_id,
                    global_state.value.student.id,
                )

            logger.info(
                "Stored example measurements for student %s.",
                global_state.value.student.id,
            )
        return True

    def get_measurement(
        self,
        galaxy_id: int,
        global_state: Reactive[GlobalState],
        local_state: Reactive[LocalState],
    ) -> StudentMeasurement:
        logger.info(
            "Retrieving measurement of galaxy %s for student %s...",
            (galaxy_id, global_state.value.student.id),
        )
        url = (
            f"{self.API_URL}/{local_state.value.story_id}/measurements/"
            f"{global_state.value.student.id}/{galaxy_id}"
        )
        measurement_json = self.request_session.get(url).json()
        measurement = measurement_json["measurements"]

        measurements = Ref(local_state.fields.measurements)

        measurements.set(measurements.value + [measurement])

        return measurement

    def get_sample_measurement(
        self,
        galaxy_id: int,
        global_state: Reactive[GlobalState],
        local_state: Reactive[LocalState],
    ) -> StudentMeasurement:
        logger.info(
            "Retrieving sample measurement of galaxy %s for student %s...",
            (galaxy_id, global_state.value.student.id),
        )
        url = (
            f"{self.API_URL}/{local_state.value.story_id}/"
            f"sample-measurements/{global_state.value.student.id}/"
            f"{galaxy_id}"
        )
        measurement_json = self.request_session.get(url).json()
        measurement = measurement_json["measurements"]

        measurements = Ref(local_state.fields.measurements)

        measurements.set(measurements.value + [measurement])

        return measurement

    def delete_all_measurements(
        self, global_state: Reactive[GlobalState], local_state: Reactive[LocalState]
    ):
        url = f"{self.API_URL}/{local_state.value.story_id}/measurements/{global_state.value.student.id}"
        measurements_json = self.request_session.get(url).json()

        for measurement in measurements_json["measurements"]:
            # url = url + "/first" if samples else url + f"/{measurement['galaxy']['id']}"
            url += f"/{measurement['galaxy']['id']}"
            r = self.request_session.delete(url)

            if r.status_code != 200:
                logger.error(
                    "Failed to delete measurement of galaxy `%s` for student `%s`.",
                    measurement["galaxy"]["id"],
                    global_state.value.student.id,
                )
                logger.error(r.text)

    def get_sample_galaxy(self, local_state: Reactive[LocalState]) -> GalaxyData:
        galaxy_json = self.request_session.get(
            f"{self.API_URL}/{local_state.value.story_id}/sample-galaxy"
        ).json()

        galaxy_data = GalaxyData(**galaxy_json)

        return galaxy_data

    def get_class_measurements(
        self,
        global_state: Reactive[GlobalState],
        local_state: Reactive[LocalState],
    ) -> list[StudentMeasurement]:
        url = (
            f"{self.API_URL}/{local_state.value.story_id}/class-measurements/"
            f"{global_state.value.student.id}/{global_state.value.classroom.class_info['id']}"
            f"?complete_only=true"
        )
        r = self.request_session.get(url)
        measurement_json = r.json()

        measurements = Ref(local_state.fields.class_measurements)
        parsed_measurements = []

        for measurement in measurement_json["measurements"]:
            measurement = StudentMeasurement(**measurement)
            parsed_measurements.append(measurement)

        measurements.set(parsed_measurements)

        logger.info("Loaded class measurements from database.")

        return measurements.value

    def get_students_completed_measurements_count(
        self,
        global_state: Reactive[GlobalState],
        local_state: Reactive[LocalState],
    ) -> int:
        url = (
            f"{self.API_URL}/{local_state.value.story_id}/class-measurements/students-completed/"
            f"{global_state.value.student.id}/{global_state.value.classroom.class_info['id']}"
        )
        r = self.request_session.get(url)
        # TODO: Handle non-200 status codes
        return r.json()["students_completed_measurements"]

    def get_all_data(
        self,
        global_state: Reactive[GlobalState],
        local_state: Reactive[LocalState],
    ) -> tuple[list[StudentMeasurement], list[StudentSummary], list[ClassSummary]]:
        url = f"{self.API_URL}/{local_state.value.story_id}/all-data?minimal=True"
        if global_state.value.classroom.class_info is not None:
            url += f"&class_id={global_state.value.classroom.class_info['id']}"
        r = self.request_session.get(url)
        res_json = r.json()

        measurements = Ref(local_state.fields.all_measurements)
        parsed_measurements = []
        for measurement in res_json["measurements"]:
            if measurement["class_id"] is None:
                continue
            measurement = StudentMeasurement(**measurement)
            parsed_measurements.append(measurement)

        measurements.set(parsed_measurements)

        student_summaries = Ref(local_state.fields.student_summaries)
        parsed_student_summaries = []
        for summary in res_json["studentData"]:
            summary = StudentSummary(**summary)
            parsed_student_summaries.append(summary)

        student_summaries.set(parsed_student_summaries)

        class_summaries = Ref(local_state.fields.class_summaries)
        parsed_class_summaries = []
        for summary in res_json["classData"]:
            summary = ClassSummary(**summary)
            parsed_class_summaries.append(summary)

        class_summaries.set(parsed_class_summaries)

        logger.info("Loaded all measurements and summary data from database.")

        return measurements.value, student_summaries.value, class_summaries.value

    def put_stage_state(
        self,
        global_state: Reactive[GlobalState],
        local_state: Reactive[LocalState],
        component_state: Reactive[BaseState],
    ):
        if not GLOBAL_STATE.value.update_db: 
            logger.info('Skipping DB write')
            return False
        
        logger.info("Serializing stage state into DB.")

        comp_state_dict = component_state.value.dict(
            exclude={"selected_galaxy", "selected_example_galaxy"}
        )
        comp_state_dict.update(
            {"current_step": component_state.value.current_step.value}
        )

        r = self.request_session.put(
            f"{self.API_URL}/stage-state/{global_state.value.student.id}/"
            f"{local_state.value.story_id}/{component_state.value.stage_id}",
            json=comp_state_dict,
        )

        if r.status_code != 200:
            logger.error("Failed to write story state to database.")
            logger.error(r.text)
            return False
        
        return True

    def put_story_state(
        self,
        global_state: Reactive[GlobalState],
        local_state: Reactive[LocalState],
    ):
        if not GLOBAL_STATE.value.update_db: 
            logger.info('Skipping DB write')
            return False
        
        logger.info("Serializing state into DB.")

        state = {
            "app": global_state.value.model_dump(),
            "story": local_state.value.as_dict(),
        }

        state_json = json.dumps(state, cls=CDSJSONEncoder)
        r = self.request_session.put(
            f"{self.API_URL}/story-state/{global_state.value.student.id}/{local_state.value.story_id}",
            headers={"Content-Type": "application/json"},
            data=state_json,
        )

        if r.status_code != 200:
            logger.error("Failed to write story state to database.")
            logger.error(r.text)
            return False
        
        return True


    def get_example_seed_measurement(
            self, 
            local_state: Reactive[LocalState],
            which="both"
            ) -> list[dict[str, Any]]:
        url = f"{self.API_URL}/{local_state.value.story_id}/sample-measurements"
        r = self.request_session.get(url)
        res_json = r.json()
        
        
        # TODO: Note that though this is from the old code
        # it seems to only pick the 2nd measurement
        vels = [record[DB_VELOCITY_FIELD] for record in res_json]
        good = [(vel is not None and vel > 0) for vel in vels]
        seq = SeedSequence(42)
        gen = Generator(PCG64(seq))
        indices = arange(len(good))
        indices = indices[1::2][:85] # we need to keep the first 85 so that it always selects the same galaxies "randomly"
        random_subset = gen.choice(indices[good[1::2][:85]], size=40, replace=False)
        random_subset = ravel(column_stack((random_subset, random_subset+1)))
        # This is the subset
        # [121 122  13  14 159 160  23  24 161 162 137 138 111 112 155 156  69  70
        #     75  76  81  82  11  12 129 130  93  94  99 100  17  18  37  38 169 170
        #     67  68 107 108 119 120  65  66  45  46 141 142  73  74 165 166  85  86
        #     59  60  87  88  27  28 109 110  51  52  47  48  97  98  89  90  63  64
        #     91  92 143 144 149 150 103 104]
        measurements = []

        _filter_func = lambda x: res_json[x]['measurement_number'] == which
        filtered = filter(_filter_func, random_subset) if which != 'both' else random_subset
        for i in filtered:
            measurements.append(res_json[i])

        return measurements

LOCAL_API = LocalAPI()
