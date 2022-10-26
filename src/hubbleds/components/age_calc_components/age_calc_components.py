import ipyvuetify as v
from cosmicds.utils import load_template
from glue_jupyter.state_traitlets_helpers import GlueState
from traitlets import Bool, Unicode, Float

from ...utils import AGE_CONSTANT


class AgeCalc(v.VuetifyTemplate):
    template = Unicode().tag(sync=True)
    state = GlueState().tag(sync=True)
    story_state = GlueState().tag(sync=True)
    failedValidation3 = Bool(False).tag(sync=True)
    failedValidationAgeRange = Bool(False).tag(sync=True)
    age_const = Float().tag(sync=True)
    hint1_dialog = Bool(False).tag(sync=True)
    hint2_dialog = Bool(False).tag(sync=True)
    hint3_dialog = Bool(False).tag(sync=True)

    def __init__(self, filename, path, stage_state, story_state, *args, **kwargs):
        self.state = stage_state
        self.story_state = story_state
        self.age_const = AGE_CONSTANT
        super().__init__(*args, **kwargs)
        self.template = load_template(filename, path)
