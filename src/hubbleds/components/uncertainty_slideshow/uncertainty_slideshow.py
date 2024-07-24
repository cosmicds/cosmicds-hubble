import solara
import reacton.ipyvuetify as rv
from ipyvuetify import VuetifyTemplate
from ...utils import IMAGE_BASE_URL


@solara.component_vue("UncertaintySlideshow.vue")
def UncertaintySlideshow(
    step=0,
    length=10,
    dialog=False,
    image_location=f"{IMAGE_BASE_URL}/stage_five",
    event_on_slideshow_finished=None,
    event_fr_callback = lambda event: fr_callback(event, LOCAL_STATE, lambda: LOCAL_API.put_story_state(GLOBAL_STATE, LOCAL_STATE)),
    free_responses=[],
    titles = [
                'What is the true age of the universe?',
                "Shortcomings in our measurements",
                "Shortcomings in our measurements",
                "Messiness in our distance measurements",
                "Uncertainty",            
                "Random Uncertainty (Noise)",
                "Systematic Uncertainty (Bias)",
                "Causes of Systematic Uncertainty",
                "Systematic Uncertainty",
                "Finished Uncertainty Tutorial",        
            ],
    age_calc_short1 = "",
    age_calc_short2 = "",
    age_calc_short_other = "",
):
    pass
