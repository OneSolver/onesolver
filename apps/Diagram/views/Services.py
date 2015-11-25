from ServiceCustom import JSONProxyCustom
from pyjamas import logging
lev = logging.DEBUG

class DiagramService(JSONProxyCustom):
    def __init__(self, spinnerWidget = None):
        self.log = logging.getConsoleLogger(type(self).__name__, lev)
        self.log.disabled = False        
        self._serviceURL = "services/Diagram"
        self.headers = {} 
        self.methods=["session_new", "session_resume", "session_save", 
                      "system_load",
                      "render_circuitikz", "change_display"
                    ]
        self.methodUseSpinner = ["session_resume", "change_display"]
        self._spinner = spinnerWidget
        self._registerMethods(self.methods)