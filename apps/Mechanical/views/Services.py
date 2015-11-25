from ServiceCustom import JSONProxyCustom
from pyjamas import logging
lev = logging.DEBUG

class MechanicalService(JSONProxyCustom):
    def __init__(self, spinnerWidget = None):
        self.log = logging.getConsoleLogger(type(self).__name__, lev)
        self.log.disabled = False        
        self._serviceURL = "services/Mechanical"
        self.headers = {} 
        self.methods=["session_new", "session_resume", "session_save", 
                      "mech_design_get", "mech_options_set"
                    ]
        self.methodUseSpinner = ["session_resume", "mech_design_get"]
        self._spinner = spinnerWidget
        self._registerMethods(self.methods)