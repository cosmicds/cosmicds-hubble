from dataclasses import dataclass, field

from cosmicds.state import BaseState
from hubbleds.base_marker import BaseMarker
from solara import Reactive
from solara.lab import Ref

from cosmicds.logger import setup_logger

logger = setup_logger("STATE")


def transition_to(component_state: Reactive[BaseState], step: BaseMarker, force=False):
    if component_state.value.can_transition(step) or force:
        Ref(component_state.fields.current_step).set(step)
    else:
        logger.warning(
            f"Conditions not met to transition from "
            f"{component_state.value.current_step.name} to {step.name}."
        )


def transition_next(component_state: Reactive[BaseState], force=False):
    next_marker = component_state.value.current_step.next(
        component_state.value.current_step
    )
    transition_to(component_state, next_marker, force=force)


def transition_previous(component_state: Reactive[BaseState], force=True):
    previous_marker = component_state.value.current_step.previous(
        component_state.value.current_step
    )
    transition_to(component_state, previous_marker, force=force)


class BaseComponentState:
    current_step: BaseMarker

    def is_current_step(self, step: BaseMarker):
        return self.current_step.value == step.value

    def current_step_in(self, steps: list[BaseMarker]):
        return self.current_step in steps

    def can_transition(
        self,
        step: BaseMarker = None,
        next: bool = False,
        prev: bool = False,
    ):
        if next:
            if self.current_step is self.current_step.last():
                return False  # TODO: Fix once we sort out transitions between stages
            step = self.current_step.next(self.current_step)
        elif prev:
            if self.current_step is self.current_step.first():
                return False  # TODO: Fix once we sort out transitions between stages
            step = self.current_step.previous(self.current_step)

        return getattr(self, f"{step.name}_gate", True)

    def current_step_between(self, start: BaseMarker, end: BaseMarker = None):
        end = end or self.current_step.last()
        return self.current_step.is_between(self.current_step, start, end)

    def current_step_at_or_before(self, end):
        return self.current_step.is_at_or_before(self.current_step, end)

    def current_step_at_or_after(self, start):
        return self.current_step.is_at_or_after(self.current_step, start)
