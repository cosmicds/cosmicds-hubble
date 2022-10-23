from asyncio import events
from echo import add_callback
from glue.config import viewer_tool
from numpy import isnan

from cosmicds.tools import LineDrawTool

@viewer_tool
class HubbleLineDrawTool(LineDrawTool):

    tool_id = 'hubble:linedraw'
    
    def __init__(self, viewer, **kwargs):
        super().__init__(viewer, **kwargs)
        self.viewer.add_event_callback(self._handle_dblclick, events=['dblclick'])
        
    
    def _handle_dblclick(self, data):
        """
        If the user double clicks on the plot we want
        to clear the line, but only when the tool is
        inactive so that behavior is consistent
        """
        # print('in _handle_dblclick')
        endpoint = getattr(self, 'endpoint', None)
        if endpoint is not None:
            if self.viewer.toolbar.active_tool is None:
                # print("\tclearing")
                self.clear()
                self.tool_tip = "Draw a trend line"
            # else:
            #         print('\ttool is active')
        # else:
        #     print('\tno endpoint')
    

    def activate(self):
        super().activate()
    
    def deactivate(self):
        super().deactivate()
        self.tool_tip = "Update trend line. Double click line to clear"
        
        

    