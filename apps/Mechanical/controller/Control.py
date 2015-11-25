"""
IMPORTS==========================================================
"""
from ServerSettings import get_server_setting
import logging
logger = logging.getLogger(__name__)
import sys, os, time, datetime

import cherrypy
import urllib, re

import sqlalchemy
from sqlalchemy.orm import sessionmaker
from Core.model import Model as ModelCore
from CloudMath.model import Model as ModelCloudMath
from CloudMath.model import MathHertz
from Mechanical.model import Model as ModelMechanical
from Mechanical.model import Geometric 
from Core.controller.GuiResponse import new_action, new_dialog
from Core.controller.Control import app_check, tab_get as tab_get_core, user_check, tab_parse_args, tab_get_reg_id, tab_search

from ZODB import FileStorage, DB
import transaction
from BTrees.OOBTree import OOBTree

DRAWMODE = 'png'

"""PAGE CONTROLLER HOOKS===================================================="""
def tab_get(*args):
    """ Get tabs for applications
    List Arguments
    @param args[0]: calling tab (int, string, sqa object)
    @param args[1]: search mode (load, session)
    @param args[2:]: search parameters
    
    Descriptions
    @note: search mode -load : load data matching search parameters, remove inapplicable tabs
    @note: search mode - session: load data in sessions, keep all tabs
    """
    print 'Mechanical.tab_get tab_get, args = %s'%str(args)
    tabParent, mode, params = tab_parse_args(*args)
    appParent = tabParent.app
    appThis = cherrypy.request.db.query(ModelCore.AppsCatalog).filter(ModelCore.AppsCatalog.name=='Mechanical').first()
    if mode == 'load':
        user = cherrypy.session['user']
        if len(params) == 0:
            equation = getattr(cherrypy.session.get('equation', None), 'instance', None)
        else:  
            equation = params[0]
        if isinstance(equation, int):
            equation = MathHertz.Equation(user, equation)            
        elif isinstance(equation, ModelCloudMath.EquationStorage):
            equation = MathHertz.Equation(user, equation.id)
        elif isinstance(equation, MathHertz.Equation):
            equation = equation
        else:
            SyntaxError('Unable to find equation %s'%equation)
        cherrypy.session['equation'] = equation
    elif mode == 'session':
        equation = cherrypy.session.get('equation', None)
    tabRegs = dict()
    idx = 0
    if equation != None:
        mechDesign = cherrypy.request.db.query(ModelMechanical.MechanicalDesign).filter(ModelMechanical.MechanicalDesign.equationStorageId == equation.instance.id).first()
        if mode == 'session' and mechDesign == None:
            if user_check('Permission', 'AppExecute'):
                tab = appThis.tabs[0]
                regId = tab_get_reg_id('highest') + 1
                tabRegs[tab.id] = {'regId': regId, 'tabId':tab.id, 'tabName':tab.name, 'appId' : appThis.id, 'appName' : appThis.name}
        elif mechDesign != None:
            cherrypy.session['mechDesign'] = mechDesign
            cherrypy.session['mechOptions'] = dict()
            for drawing in mechDesign.drawings:
                if drawing.initUnit == None:
                    drawing.initUnit = 100000 #default to meters
                cherrypy.session['mechOptions'][drawing.id] = {'checkOptions': [False, True], 'ratio': '1:1', 
                                                               'size': 'none', 'unit': drawing.initUnit}
            #load other app tabs only when there data available      
            for tab in appThis.tabs:
                if user_check('Permission', 'AppExecute'):
                    tabRegs[tab.id] = {'regId': idx, 'tabId':tab.id, 'tabName':tab.name, 'appId' : tab.app.id, 'appName' : tab.app.name}
            #check tabs in other apps
            if  tabParent.name == 'Mechanical':
                tabExts = tab_get_core(tabParent, 'load',  equation.id)
                for tabIdExt, tabExt  in tabExts.items():
                    tabExt['regId'] += idx
                tabRegs = dict(tabRegs.items() + tabExts.items())
    return tabRegs 
def session_new(*args):
    print 'Mechanical.session_new, args = %s'%str(args)
    actions = list()
    tab, mode, params = tab_parse_args(*args)
    if len(params) > 1:
        if isinstance(params[1], int):
            equationId = params[1]
    else:
        equationId = None
    if user_check('Permission', 'AppExecute'):
        if equationId:
            mechDesign = cherrypy.request.db.query(ModelMechanical.MechanicalDesign).filter(ModelMechanical.MechanicalDesign.equation_id == equationId).first()
            cherrypy.session['mechDesign'] = mechDesign
            respDict = session_resume()
            actions+=respDict['actions']
        else:
            print 'Mechanical.new_session, creating new sessions equation'
    return {'actions':actions}
def session_resume():
    actions =list()
    if cherrypy.session.has_key('mechDesign'):
        mechDesign = cherrypy.session['mechDesign']
        if tab_search('Solver'):
            pass 
        try:
            respDict = mech_design_get()
            if respDict.has_key('actions'):
                actions += respDict['actions']
                return {'actions':actions}
            elif respDict.has_key('dialog'):
                return {'dialog': respDict['dialog']} 
        except Exception as err:
            msg = 'Problem encounter, %s'%str(err.message)
            cherrypy.log.error(msg,'MECHANICAL', logging.ERROR, traceback = True)
            dialog = new_dialog('Mechanical Drawing Error', msg)
            return {'dialog':dialog} 
    return {'actions':actions}

"""API PUBLIC FUNCTIONS======================================================
The following function execute actions for the core and then checks to see if 
other tab have implemented method with the same name.  If so, core will 
execute  
"""
def mech_options_set(idx, option, value):
    print 'Mechanical.mech_options_set, entry, %s, %s'%(option, value)
    actions = list()
    if cherrypy.session['mechOptions'][idx][option] != value:
        print 'set option %s'%value
        cherrypy.session['mechOptions'][idx][option] = value
        if option in ('checkOptions', 'ratio', 'size', 'unit'):
            actions.append(new_action('actRefresh','Drawing', idx = idx)) 
    else:
        actions.append(new_action('actPass','Drawing', idx = idx ))
    return {'actions':actions}
    
def mech_design_get(idxMech = None):
    actions = list()
    user = cherrypy.session['user']
    mechDesign = cherrypy.session['mechDesign']
    equation = cherrypy.session['equation']
    solution = equation.solution_get('S')
    ds = Geometric.DraftSpace(backend = 'Agg')
    ds.clear()
    ds.showGrid = False
    ds.showTick = False
    ds.showAnchor = False
    mechPath = os.path.join(get_server_setting('imagesdir'), cherrypy.session.id)
    ds.path = mechPath
    ds.authorOrigin = equation.instance.owner.firstName + ' ' +  equation.instance.owner.lastName
    ds.authorModify  = user.firstName + ' ' + user.lastName
    ds.dateOrigin = equation.instance.timestamp.strftime("%m-%d-%Y")
    ds.title = equation.instance.title
    if not os.path.exists(mechPath):
        os.mkdir(mechPath)
    idxList = list()
    if idxMech != None:
        idxList.append(idxMech)
    else:
        for drawing in mechDesign.drawings:
            idxList.append(drawing.id)
    storage = FileStorage.FileStorage(os.path.join(get_server_setting('cachedir'), 'cache.fs'))
    db = DB(storage)
    connection = db.open()
    root = connection.root()
    for idxMech in idxList:
        for drawing in mechDesign.drawings: #search for drawing
            if drawing.id == idxMech:
                break
        mechOptions = cherrypy.session['mechOptions'][idxMech]
        ds.ratio = mechOptions['ratio']
        ds.perspective = drawing.perspective.capitalize()
        ds.name = 'Mechanical-Drawing' + drawing.perspective.capitalize() + time.strftime('%y%m%d%H%M%S')
        imgUrl = 'api/image?app=Mechanical&tab=Drawing&id1=%d&id2=%d'%(mechDesign.id, drawing.id) + '&image=' + ds.name   + '.' + DRAWMODE
        values = dict()
        symbols = dict()
        baseUnit = equation.unumDict[int(mechOptions['unit'])]
        for variableSol in solution.variables: 
            for variableMech in drawing.variables:
                desig = variableMech.desig.longhand + str(variableMech.number)
                if variableMech.id == variableSol.variable.id:
                    symbols[desig] = variableMech.desig.latex.replace('#', str(variableMech.number))
                    if variableSol.variable.desig.name == 'Length':
                        unumSelected = equation.variable_get_unit(variableSol, 'selected-unum')
                        unumValue = variableSol.value*unumSelected
                        unumValue = unumValue.asUnit(baseUnit)
                        value = unumValue._value
                    else:
                        value = variableSol.value
                    
                    values[desig] = value
                     
        key = '%s\n%s\n%s\n%s\n%s'%(mechOptions['size'], mechOptions['checkOptions'], mechOptions['ratio'], mechOptions['unit'], ds.get_cmd(drawing.drawing, values))
        cache = root.cache_image.get(key, None)
        imgFileLoc = os.path.join(ds.path, ds.name + '.' + DRAWMODE)
        if cache:
            fId = open(imgFileLoc, 'wb+')
            fId.write(cache.image)
            cache.update() # update timestamp
            root.cache_image[key] = cache
            transaction.commit()
        else:
            cherrypy.log.error('Draw %s, %s'%(drawing, values), 'MECHANICAL', logging.DEBUG)
            ds.load(drawing.drawing, values)
            cherrypy.log.error('Set background.', 'MECHANICAL', logging.DEBUG)
            ds.draw_background(mechOptions['size'])
            ds.save(fmt = DRAWMODE)
            root.cache_image[key] = ModelCore.CacheImage(imgFileLoc)
            transaction.commit()      
        ds.clear()
        actions.append(new_action('actDrawingAdd','Drawing', idx = idxMech, image =  imgUrl, variables = None, code = drawing.drawing,  perspective = drawing.perspective))   
        actions.append(new_action('actRatioChange','Drawing', idx = idxMech, ratio = mechOptions['ratio']))
        actions.append(new_action('actSizeFill','Drawing',  idx = idxMech, options = Geometric.options, value = mechOptions['size']))
        actions.append(new_action('actUnitFill','Drawing',  idx = idxMech, options = {100000:'m', 302800:'ft', 300103:'cm', 302700:'in',300102:'mm',302900:'mil'}, value = int(mechOptions['unit'])))              
    connection.close() #close cache
    db.close()
    storage.close()
    return {'actions':actions}
def tab_select(tabId):
    logger.debug('tab_select - user selected tabId - %d'%tabId)
    actions = list()
    if tabId == 2: # primary key for solver
        print 'Mechanical: Clicked Solver '
    elif tabId == 5: # primary key for mechanical
        actions.append(new_action('actRefresh','Drawing'))        
        return {'actions':actions}

    