from pyjamas.ui.RootPanel import RootPanel
#from pyjamas import Window
from pyjamas.ui.VerticalPanel import VerticalPanel
from pyjamas.ui.HorizontalPanel import HorizontalPanel
from pyjamas.ui import HasAlignment
from pyjamas.ui.TextArea import TextArea
from pyjamas.ui.TextBox import TextBox
from pyjamas.ui.Button import Button
from pyjamas.ui.CheckBox import CheckBox
from pyjamas.ui.Label import Label
from pyjamas.ui.HTML import HTML
from pyjamas.ui.HTMLPanel import HTMLPanel
from pyjamas.ui.Image import Image
from pyjamas.Cookies import getCookie
from Services import DiagramService
from pyjamas import Window
# Logging ------------------------------
from pyjamas import logging
from CoreSettings import lev

   
class Circuit(object):
    def __init__(self, handle):
        self.log = logging.getConsoleLogger(type(self).__name__, lev)
        self.log.disabled = False
        self.log.debug('__init__: Instantiation')
        self._cacheBreaker = 0
        self._handle = handle 
        self.remoteService=DiagramService(handle.spinner)
        labelDisplay = Label('Diagram')
        self.display = HTMLPanel('No circuit created.')
        self.latex = TextArea()
        
        buttonPanel =  HorizontalPanel()
        
        labelFormatting = Label('Formatting')
        labelCheckbox = Label('Show: ')
        self.checkboxValue = CheckBox('value')
        self.checkboxValue.setID('CBXV1')
        self.checkboxValue.addClickListener(self.onCirctuiTikzClick)
        self.checkboxSymbol = CheckBox('symbol')
        self.checkboxSymbol.setID('CBXS1')
        self.checkboxSymbol.addClickListener(self.onCirctuiTikzClick)
        checkboxPanel =  HorizontalPanel()
        checkboxPanel.add(labelCheckbox)
        checkboxPanel.add(self.checkboxSymbol)
        checkboxPanel.add(self.checkboxValue)
        
        #layout
        self.layout=VerticalPanel(HorizontalAlignment=HasAlignment.ALIGN_LEFT, Spacing=10)
        self.layout.add(labelDisplay)
        self.layout.add(self.display)
        self.layout.add(Label('Circuitikz Markup'))
        self.layout.add(self.latex)
        self.layout.add(buttonPanel)
        self.layout.add(labelFormatting)
        self.layout.add(checkboxPanel)
        RootPanel().add(self.layout)
        
        #Set Default view
        self.actCircuitTikzLock(lock = True)
    def actClear(self):
        self.latex.setText('')
        self.layout.remove(self.display)
        self.display = HTMLPanel('No circuit created.')
        self.layout.insert(self.display, 1)
    def onMenuResume(self):
        self.remoteService.session_resume(self._handle)
    def onCirctuiTikzClick(self, sender, event):
        sendId = sender.getID()
        if sendId == 'CBXV1':
            self.log.debug('click value')
            self.remoteService.change_display(self._handle, 'value', self.checkboxValue.getChecked())
        elif sendId == 'CBXS1':
            self.log.debug('click symbol')
            self.remoteService.change_display(self._handle, 'symbol', self.checkboxSymbol.getChecked())
    def onCircuitTikzSubmit(self):
        self.log.debug('onCircuitTikzSubmit - entry')
        self.remoteService.render_circuitikz(self._handle, self.latex.getText())
    def actCircuitTikzSubmit(self, **kwargs):
        id = kwargs.get('id')
        app = 'Circuit'
        sessionId = getCookie('session_id')
        image = 'api/image?app=Diagram&tab=Circuit&Id=%d&Cache=%d'%(id, self._cacheBreaker)
        self.layout.remove(self.display)
        self.display = Image(image)
        self.layout.insert(self.display, 1)
        self._cacheBreaker = self._cacheBreaker + 1
    def actCircuitTikzLock(self, **kwargs):
        lock = bool(kwargs.get('lock'))
        self.latex.setReadonly(lock)
        self.latex.setStyleName('os-diagram-code-lock')
    def actCircuitTikzSet(self, **kwargs):
        latex = kwargs['latex']
        self.latex.setText(latex)
    def actCircuitTikzFail(self):
        pass
    def actCircuitTikzDisplayUpdate(self, **kwargs):
        symbol = kwargs.get('symbol', None)
        value = kwargs.get('value', None)
        if symbol != None:
            self.checkboxSymbol.setChecked(symbol)
        if value != None:
            self.checkboxValue.setChecked(value)
            
            
        
        