from functools import partial
from os.path import join, abspath
from pathlib import Path

from echo import CallbackProperty, add_callback, remove_callback
from glue_jupyter.link import dlink, link
from traitlets import Bool, default

from cosmicds.components.generic_state_component import GenericStateComponent
from cosmicds.phases import CDSState
from cosmicds.registries import register_stage
from cosmicds.utils import extend_tool, load_template
from hubbleds.utils import IMAGE_BASE_URL

from ..components import AgeCalc, HubbleExp, ProData, TrendsData
from ..data.styles import load_style
from ..data_management import (ALL_CLASS_SUMMARIES_LABEL, ALL_DATA_LABEL,
                               ALL_STUDENT_SUMMARIES_LABEL,
                               BEST_FIT_GALAXY_NAME, BEST_FIT_SUBSET_LABEL,
                               CLASS_DATA_LABEL, CLASS_SUMMARY_LABEL,
                               HUBBLE_1929_DATA_LABEL, HUBBLE_KEY_DATA_LABEL,
                               STUDENT_DATA_LABEL)
from ..stage import HubbleStage


class StageState(CDSState):
    
    marker = CallbackProperty("")
    indices = CallbackProperty({})
    
    markers = [
        'two_his1',
        'tru_age1',
        'tru_age2',
        'sho_est3',
        'sho_est4',
        'tru_iss1',
        'imp_met1',
        'imp_ass1',
        'imp_mea1',
        'unc_ran1',
        'unc_sys1',
        'unc_sys2',
        'two_his2',
        'lac_bia1',
        'lac_bia2',
        'lac_bia3',
        'mor_dat1',
        'acc_unc1',
        ]
        
    step_markers = CallbackProperty([
        'two_his1',
        'unc_sys1'
        ])
    
    _NONSERIALIZED_PROPERTIES = [
        'markers', 'indices', 'step_markers', 'image_location',
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.marker_index = 0
        self.marker = self.markers[0]
        self.indices = {marker: idx for idx, marker in enumerate(self.markers)}

    def marker_before(self, marker):
        return self.indices[self.marker] < self.indices[marker]

    def marker_after(self, marker):
        return self.indices[self.marker] > self.indices[marker]
    
    def marker_reached(self, marker):
        return self.indices[self.marker] >= self.indices[marker]

    def move_marker_forward(self, marker_text, _value=None):
        index = min(self.markers.index(marker_text) + 1, len(self.markers) - 1)
        self.marker = self.markers[index]


@register_stage(story="hubbles_law", index=5, steps=["STEP 4.1", "STEP 4.2"])
class StageTest(HubbleStage):
    show_team_interface = Bool(False).tag(sync=True)
    
    _state_cls = StageState

    @default('template')
    def _default_template(self):
        return load_template("stage_four.vue", __file__)

    @default('stage_icon')
    def _default_stage_icon(self):
        return "4"

    @default('title')
    def _default_title(self):
        return "Understanding Uncertainty"

    @default('subtitle')
    def _default_subtitle(self):
        return "Comparing with the class data"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.show_team_interface = self.app_state.show_team_interface
        self.stage_state.marker = self.stage_state.markers[0]
        
        state_components = [
            "guideline_class_age_distribution",
            "guideline_trend_lines_draw2_c",
            "guideline_best_fit_line_c",
            "guideline_classmates_results_c",
            "guideline_class_age_distribution_c",
            "guideline_two_histograms1",
            "guideline_true_age1",
            "guideline_true_age2",
            "guideline_shortcomings_est_reflect4",
            "guideline_true_age_issues1",
            "guideline_imperfect_methods1",
            "guideline_imperfect_assumptions1",
            "guideline_imperfect_measurements1",
            "guideline_uncertainties_random1",
            "guideline_uncertainties_systematic1",
            "guideline_uncertainties_systematic2",
            "guideline_two_histograms_mc2",
            "guideline_lack_bias_mc1",
            "guideline_lack_bias_reflect2",
            "guideline_lack_bias_reflect3",
            "guideline_more_data_distribution",
            "guideline_account_uncertainty"
        ]
        

        state_components_dir = str(Path(__file__).parent.parent / "components" / "generic_state_components" / "stage_three")
        path = join(state_components_dir, "")
        
        self.add_components_from_path(state_components, path)
        
        # load data
        dist_attr = "distance"
        vel_attr = "velocity"
        hubble1929 = self.get_data(HUBBLE_1929_DATA_LABEL)
        hstkp = self.get_data(HUBBLE_KEY_DATA_LABEL)
        student_data = self.get_data(STUDENT_DATA_LABEL)
        class_meas_data = self.get_data(CLASS_DATA_LABEL)
        

    def add_components_from_path(self, state_components, path):
        
        ext = ".vue"
        for comp in state_components:
            label = f"c-{comp}".replace("_", "-")

            component = GenericStateComponent(comp + ext, path,
                                              self.stage_state)
            self.add_component(component, label=label)

        
