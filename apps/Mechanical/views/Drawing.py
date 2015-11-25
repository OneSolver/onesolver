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
from pyjamas.ui.Label import Label
from pyjamas.ui.ListBox import ListBox
from pyjamas.ui.Widget import Widget
from pyjamas import Window  
import re
# Logging ------------------------------
from pyjamas import logging
from CoreSettings import lev
# view specific
from Services import MechanicalService
from MathStackPanel import MathStackPanel

class MechOptionPanel(HorizontalPanel):
    def __init__(self, handle, idx, checkOptions = [False, True]):
        HorizontalPanel.__init__(self)
        self.log = logging.getConsoleLogger(type(self).__name__, lev)
        self.log.disabled = False
        self.log.debug('__init__: Instantiation')
        self.idx = idx
        self._handle = handle
        self._checkOptions = checkOptions
        self.setStyleName('os-mech-checkbox-options')
        #checkbox = CheckBox('symbol')
        #checkbox.setChecked(checkOptions[0])
        #checkbox.addClickListener(self.onClickOption)
        #checkbox.setID('CBSY%d'%idx)
        #self.append(checkbox)
        #checkbox = CheckBox('value')
        #checkbox.setChecked(checkOptions[1])
        #checkbox.addClickListener(self.onClickOption)
        #checkbox.setID('CBVA%d'%idx)
        #self.append(checkbox)
        
        self._textBoxRatio = TextBox('1:1')
        self._ratioCache = self._textBoxRatio.getText()
        self._textBoxRatio.setTitle('Ratio')
        self._ratioCache = self._textBoxRatio.getText()
        
        self._textBoxRatio.addChangeListener(self.onRatioChange) 
        self._textBoxRatio.setID('TXRT%d'%idx)
        self._textBoxRatio.setStyleName('os-mech-textbox-ratio')
        
        self._listBoxSize = ListBox()
        self._listBoxSize.addChangeListener(self.onSizeSet)
        self._listBoxSize.setVisibleItemCount(1)
        self._listBoxSize.setStyleName('os-mech-listbox-size')

        self._listBoxUnit = ListBox()
        self._listBoxUnit.addChangeListener(self.onUnitSet)
        self._listBoxUnit.setVisibleItemCount(1)
        self._listBoxUnit.setStyleName('os-mech-listbox-unit')

        self.append(Label('Ratio'))
        self.append(self._textBoxRatio)
        self.append(Label('Size'))
        self.append(self._listBoxSize)
        self.append(Label('Unit'))
        self.append(self._listBoxUnit)
    def onSizeSet(self, sender, event):
        value = sender.getSelectedItemText()[0]
        self.log.debug('Change size to %s'%value)
        self._handle.remoteService.mech_options_set(self._handle._handle, self.idx, 'size', value)
    def onUnitSet(self, sender, event):
        value = sender.getSelectedValues()[0]
        self._handle.remoteService.mech_options_set(self._handle._handle, self.idx, 'unit',int(value))
    def onRatioChange(self, sender, event):
        #validate ratio change
        matches = re.findall(r'^\d{1,4}:\d{1,4}$', self._textBoxRatio.getText())
        if len(matches) == 1: # correct
            self._ratioCache = self._textBoxRatio.getText()
            self._handle.remoteService.mech_options_set(self._handle._handle, self.idx, 'ratio', self._ratioCache)
        else: # invalid
            self._textBoxRatio.setText(self._ratioCache)
    def actSizeFill(self, options, value = 0):
        for idx, option in enumerate(options, idx):
            self._listBoxSize.addItem(option, idx)
        self._listBoxSize.setSelectedIndex(value)
    def actUnitFill(self, options, value = 0):
        for number, name in options.items():
            self._listBoxUnit.addItem(name, number)
        if value < 100000:
            self._listBoxUnit.setSelectedIndex(value)
        else:
            self._listBoxUnit.selectValue(value)
    def actSizeSet(self, value):
        self.log.debug('actSizeSet, setting value %s'%value)
        self._listBoxSize.selectValue(value)
    def actRatioChange(self, ratio):
        self._textBoxRatio.setText(ratio)
        self._ratioCache = ratio
    def onClickOption(self, sender, event):
        sendId = int(sender.getID()[4:])
        if sendId == 0:
            self._checkOptions[0] = sender.isChecked()
            self._checkOptions[1] = not(sender.isChecked())
        else:
            self._checkOptions[0] = not(sender.isChecked())
            self._checkOptions[1] = sender.isChecked()
        checkbox = self.getWidget(0)
        checkbox.setChecked(self._checkOptions[0])
        checkbox = self.getWidget(1)
        checkbox.setChecked(self._checkOptions[1])
        self._handle.remoteService.mech_options_set(self._handle._handle, self.idx,  'checkOptions', self._checkOptions)

class MechDrawing(VerticalPanel):
    def __init__(self, handle, idx, image, variables = None, code = None, 
                 perspective = '', checkOptions = [False, True]):
        VerticalPanel.__init__(self)
        self._handle = handle
        self.idx = idx
        # set style
        self.setStyleName('os-mech-drawing')  
        # create widgets
        self._img = Image(image)
        self._img.setStyleName('os-mech-thumb')
        self._img.addClickListener(self.onClickDrawing)
        self._perspective = '%d - %s'%(idx, perspective.capitalize())
        self._optionPanel = MechOptionPanel(handle, idx, checkOptions)
        textArea  = TextArea(code)
        textArea.setText(code)
        textArea.setStyleName('os-mech-code-locked')
        textArea.setReadonly(self, True)
        # populate drawing
        self.add(self._img)
        self.add(self._optionPanel)
        self.add(textArea)
    def actRatioChange(self, ratio):
        self._optionPanel.actRatioChange(ratio)
    def onClickDrawing(self, sender, event):
        Window.open(self._img.getUrl() + '&render=html&title=%s'%self._perspective, self._perspective, "status=1,resizeable=1,scrollbars=1")
        
class Drawing(object):
    def __init__(self, handle = None):
        self.idx = 0
        self.log = logging.getConsoleLogger(type(self).__name__, lev)
        self.log.disabled = False
        self.log.debug('__init__: Instantiation')
        self._handle = handle 
        if handle:
            self.remoteService = MechanicalService(handle.spinner)
        self.layout = MathStackPanel()
    def searchDrawing(self, idx):
        for idxPosition, stackItem in enumerate(self.layout.getChildren()):
            drawing = stackItem.getWidget()
            if int(drawing.idx) == int(idx):
                return drawing, idxPosition
        return None, None
    def actDrawingAdd(self, **kwargs):
        image = kwargs.get('image')
        code = kwargs.get('code')
        perspective = kwargs.get('perspective')
        idx = kwargs.get('idx')
        newDrawing = MechDrawing(self, idx, image, None, code, perspective)
        oldDrawing, _ = self.searchDrawing(idx)
        if oldDrawing:
            self.layout.replace(oldDrawing, newDrawing, perspective)
        else:
            self.layout.add(newDrawing, perspective)
        self.log.debug('actDrawingAdd %s, %s'%(oldDrawing, idx))
    def actSizeFill(self, idx, options, value):
        drawing, _ = self.searchDrawing(idx)
        drawing._optionPanel.actSizeFill(options, value)
    def actUnitFill(self, idx, options, value):
        drawing, _ = self.searchDrawing(idx)
        drawing._optionPanel.actUnitFill(options, value)
    def actSizeSet(self, **kwargs):
        idx = kwargs.get('idx')
        value = kwargs.get('value')
        drawing, _ = self.searchDrawing(idx)
        drawing._optionPanel.actSizeSet(value)
    def actRatioChange(self, idx, ratio):
        drawing, _ = self.searchDrawing(idx)
        drawing._optionPanel.actRatioChange(ratio)           
    def actClear(self, **kwargs):
        self.log.debug('actClear, kwargs %s'%kwargs)
        idx = kwargs.get('idx', None)
        if idx:
            _, idxPosition = self.searchDrawing(idx)
            self.layout.remove(idxPosition)
        else:
            self.layout.clear()
    def actRefresh(self, **kwargs):
        idx = kwargs.get('idx', None)
        self.remoteService.mech_design_get(self._handle, idx)
    def actPass(self, *kwargs):
        self.log.debug('actPass, do nothing')
    def onMenuResume(self):
        self.actRefresh()