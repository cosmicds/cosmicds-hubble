import json

import ipyvuetify as v
import requests
from cosmicds.components import Table
from cosmicds.phases import Stage
from cosmicds.utils import API_URL, CDSJSONEncoder
from echo import add_callback

from .data_management import MEAS_TO_STATE, STUDENT_MEASUREMENTS_LABEL, UNITS_TO_STATE, DISTANCE_COMPONENT, VELOCITY_COMPONENT
from .utils import HUBBLE_ROUTE_PATH, distance_from_angular_size, velocity_from_wavelengths


class HubbleStage(Stage):

    def __init__(self, session, story_state, app_state, *args, **kwargs):
        super().__init__(session, story_state, app_state, *args, **kwargs)

        # Respond to dark/light mode change
        add_callback(self.app_state, 'dark_mode', self._on_dark_mode_change)

    @staticmethod
    def _map_key(key):
        return MEAS_TO_STATE.get(key, key)

    def _prepare_measurement(self, measurement):
        prepared = {HubbleStage._map_key(k): measurement.get(k, None) for k in
                    MEAS_TO_STATE.keys()}
        prepared.update(UNITS_TO_STATE)
        prepared["student_id"] = self.app_state.student["id"]
        ext = ".fits"
        if not prepared["galaxy_name"].endswith(ext):
            prepared["galaxy_name"] += ext
        prepared = json.loads(json.dumps(prepared, cls=CDSJSONEncoder))
        return prepared
    
    def _prepare_sample_measurement(self, measurement):
        """ for the example galaxy data """
        prepared = {HubbleStage._map_key(k): measurement.get(k, None) for k in
                    MEAS_TO_STATE.keys()}
        prepared.update(UNITS_TO_STATE)
        prepared["student_id"] = self.app_state.student["id"]
        ext = ".fits"
        if not prepared["galaxy_name"].endswith(ext):
            prepared["galaxy_name"] += ext
        prepared = json.loads(json.dumps(prepared, cls=CDSJSONEncoder))
        return prepared


    def submit_measurement(self, measurement):
        if self.app_state.update_db:
            prepared = self._prepare_measurement(measurement)
            print('submit now')
            # requests.put(f"{API_URL}/{HUBBLE_ROUTE_PATH}/submit-measurement",
                        # json=prepared)
            
    
    def submit_example_galaxy_measurement(self, measurement):
        if self.app_state.update_db:
            prepared = self._prepare_sample_measurement(measurement)
            requests.put(f"{API_URL}/{HUBBLE_ROUTE_PATH}/sample-measurements",
                        json=prepared)


    def remove_measurement(self, galaxy_name):
        name = str(galaxy_name)
        condition = lambda x: x == name
        if not galaxy_name.endswith(".fits"):
            galaxy_name += ".fits"
        self.remove_data_values("student_measurements", "name", condition,
                                single=True)
        user = self.app_state.student
        if self.app_state.update_db and user.get("id", None) is not None:
            requests.delete(
                f"{API_URL}/{HUBBLE_ROUTE_PATH}/measurement/{user['id']}/{galaxy_name}")

    def update_data_value(self, dc_name, comp_name, value, index, block_submit=False):
        super().update_data_value(dc_name, comp_name, value, index)

        if dc_name != STUDENT_MEASUREMENTS_LABEL:
            return

        # Update dependent values, if the student has already has a value for them
        # We block submission to avoid sending unnecessary requests
        data = self.data_collection[dc_name]
        if comp_name == "measwave":
            velocity = data[VELOCITY_COMPONENT][index]
            if velocity is not None:
                rest = data["restwave"][index]
                new_velocity = velocity_from_wavelengths(value, rest)
                self.update_data_value(dc_name, VELOCITY_COMPONENT , new_velocity, index, block_submit=True)

        if comp_name == "angular_size":
            distance = data[DISTANCE_COMPONENT][index]
            if distance is not None:
                new_distance = distance_from_angular_size(value)
                self.update_data_value(dc_name, DISTANCE_COMPONENT, new_distance, index, block_submit=True)

        # Submit a measurement, if necessary
        if self.app_state.update_db \
                and comp_name in MEAS_TO_STATE.keys() \
                and not block_submit:
            measurement = {comp.label: data[comp][index] for comp in
                           data.main_components}
            self.submit_measurement(measurement)

    def add_data_values(self, dc_name, values):
        super().add_data_values(dc_name, values)
        self.story_state.update_student_data()

        if self.app_state.update_db and dc_name == STUDENT_MEASUREMENTS_LABEL:
            self.submit_measurement(values)

    def table_selected_color(self, dark):
        theme = v.theme.themes.dark if dark else v.theme.themes.light
        return theme.info

    def _on_dark_mode_change(self, dark):
        color = self.table_selected_color(dark)
        for widget in self.widgets.values():
            if isinstance(widget, Table):
                widget.selected_color = color
