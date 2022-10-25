from echo import delay_callback
from glue.viewers.scatter.state import ScatterViewerState
from glue_jupyter.bqplot.histogram import BqplotHistogramView
from glue_jupyter.bqplot.scatter import BqplotScatterView
from cosmicds.viewers import cds_viewer

__all__ = [
    "HubbleScatterViewerState", "HubbleFitViewerState",
    "HubbleFitView", "HubbleScatterView", "HubbleClassHistogramView"
]


class HubbleScatterViewerState(ScatterViewerState):

    def reset_limits(self):
        with delay_callback(self, 'x_min', 'x_max', 'y_min', 'y_max'):
            super().reset_limits()
            self.x_min = min(self.x_min, 0)
            self.y_min = min(self.y_min, 0)


class HubbleFitViewerState(HubbleScatterViewerState):
    
    def reset_limits(self):
        with delay_callback(self, 'x_min', 'x_max', 'y_min', 'y_max'):
            super().reset_limits()
            self.x_max = 1.1 * self.x_max
            self.y_max = 1.1 * self.y_max


HubbleFitView = cds_viewer(
    BqplotScatterView,
    name="HubbleFitView",
    viewer_tools=[
        "bqplot:home",
        "bqplot:rectzoom",
        "bqplot:rectangle",
        "cds:linedraw",
        "hubble:linefit"
    ],
    label='Fit View',
    state_cls=HubbleFitViewerState
)

HubbleFitLayerView = cds_viewer(
    BqplotScatterView,
    name="HubbleFitLayerView",
    viewer_tools=[
        # "bqplot:home",
        # 'bqplot:rectangle',
        "hubble:linefit",
        "hubble:linedraw",
        "hubble:togglelayer",
    ],
    label='Layer View',
    state_cls=HubbleFitViewerState
)

HubbleScatterView = cds_viewer(
    BqplotScatterView,
    name="HubbleScatterView",
    viewer_tools=[
        'bqplot:home',
        'bqplot:rectzoom',
        'hubble:linefit'
    ],
    label='Scatter View',
    state_cls=HubbleScatterViewerState
)

HubbleHistogramView = cds_viewer(
    BqplotHistogramView,
    name="HubbleHistogramView",
    viewer_tools=[
        "bqplot:home",
        "bqplot:xzoom",
    ],
    label="Class Histogram"
)

HubbleClassHistogramView = cds_viewer(
    BqplotHistogramView,
    name="HubbleClassHistogramView",
    viewer_tools=[
        "bqplot:home",
        "bqplot:xzoom",
        "bqplot:xrange"
    ],
    label="Class Histogram"
)
