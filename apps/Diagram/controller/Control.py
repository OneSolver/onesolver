"""
IMPORTS==========================================================
"""
from ServerSettings import get_server_setting
import logging
logger = logging.getLogger(__name__)
import sys, os, time

import cherrypy
import urllib, re

import sqlalchemy
from sqlalchemy.orm import sessionmaker
from Core.model import Model as ModelCore
from CloudMath.model import Model as ModelCloudMath
from CloudMath.model import MathHertz
from Diagram.model import Model as ModelDiagram
from Core.controller.GuiResponse import new_action, new_dialog
from Core.controller.Control import app_check, tab_get as tab_get_core, user_check, tab_parse_args, tab_get_reg_id, tab_search

from subprocess import Popen, PIPE, STDOUT

from ZODB import FileStorage, DB
import transaction
from BTrees.OOBTree import OOBTree

texMode = 'file' #(file, string)# todo get string mode working in linux
fileName = 'circuit'
latexEngine = 'pdflatex' #(pdflatex, xelatex)
latexPath = get_server_setting('latexdir')
# cleanup
def clean_files():
    fileExts = ('dvi', 'ps', 'log', 'aux', 'svg', 'eps')
    for ext in fileExts:
        try:
            os.remove('%s.%s'%(fileName,ext))
            cherrypy.log.error("Remove %s.%s"%(fileName,ext), 'DIAGRAM', logging.DEBUG)
        except Exception as err:
            cherrypy.log.error("Skip %s.%s"%(fileName,ext), 'DIAGRAM', logging.DEBUG) 
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
    tabParent, mode, params = tab_parse_args(*args)
    appParent = tabParent.app
    appThis = cherrypy.request.db.query(ModelCore.AppsCatalog).filter(ModelCore.AppsCatalog.name=='Diagram').first()
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
        circuit = cherrypy.request.db.query(ModelDiagram.DiagramCircuit).filter(ModelDiagram.DiagramCircuit.equation_id == equation.instance.id).first()
        if mode == 'session' and circuit == None:
            if user_check('Permission', 'AppExecute'):
                tab = appThis.tabs[0]
                regId = tab_get_reg_id('highest') + 1
                tabRegs[tab.id] = {'regId': regId, 'tabId':tab.id, 'tabName':tab.name, 'appId' : appThis.id, 'appName' : appThis.name}
        elif circuit != None:
            cherrypy.session['circuit'] = circuit   
            #load other app tabs only when there data available      
            for tab in appThis.tabs:
                if user_check('Permission', 'AppExecute'):
                    tabRegs[tab.id] = {'regId': idx, 'tabId':tab.id, 'tabName':tab.name, 'appId' : tab.app.id, 'appName' : tab.app.name}
            #check tabs in other apps
            if  tabParent.name == 'Circuit':
                tabExts = tab_get_core(tabParent, 'load',  equation.id)
                for tabIdExt, tabExt  in tabExts.items():
                    tabExt['regId'] += idx
                tabRegs = dict(tabRegs.items() + tabExts.items())
    return tabRegs 
def session_new(*args):
    cherrypy.log.error('New Session', 'DIAGRAM', logging.DEBUG)
    actions = list()
    tab, mode, params = tab_parse_args(*args)
    if len(params) > 1:
        if isinstance(params[1], int):
            equationId = params[1]
    else:
        equationId = None
    if user_check('Permission', 'AppExecute'):
        if equationId != None:
            dbCircuit = cherrypy.request.db.query(ModelDiagram.DiagramCircuit).filter(ModelDiagram.DiagramCircuit.equation_id == equationId).first()
            cherrypy.session['circuit'] = dbCircuit
            respDict = session_resume()
            actions+=respDict['actions']
        else:
            dbEquation = cherrypy.session['equation']
            dbCircuit = ModelDiagram.DiagramCircuit('', dbEquation.instance)
            cherrypy.session['circuit'] = dbCircuit
    return {'actions':actions}
def session_resume():
    cherrypy.log.error('Resume Session', 'DIAGRAM', logging.DEBUG)
    actions =list()
    if cherrypy.session.has_key('display'):
        display = cherrypy.session['display']
    else:
        display = {'symbol': True, 'value':False} # default
        cherrypy.session['display'] = display
    if cherrypy.session.has_key('circuit'):
        equation = cherrypy.session['equation']
        latex = cherrypy.session['circuit'].latex
        actions.append(new_action('actCircuitTikzSet', 'Circuit', latex = latex))
        actions.append(new_action('actCircuitTikzDisplayUpdate', 'Circuit', value = display['value'],  symbol = display['symbol']))
        if tab_search('Solver'):
            actions.append(new_action('actEquationHeadingUpdate', 'Solver', display = cherrypy.session.get('display'), circuit_id = cherrypy.session['circuit'].id)) 
        try:
            respDict = render_circuitikz(latex)
            if respDict.has_key('actions'):
                actions += respDict['actions']
                return {'actions':actions}
            elif respDict.has_key('dialog'):
                return {'dialog':dialog} 
        except Exception as err:
            msg = 'Problem encounter, %s'%str(err.message)
            cherrypy.log(msg)
            dialog = new_dialog('Latex Error', msg)
            return {'dialog':dialog} 
            dialog = respDict['dialog']
    else:
        latex = ''
    return {'actions':actions}

"""API PUBLIC FUNCTIONS======================================================
The following function execute actions for the core and then checks to see if 
other tab have implemented method with the same name.  If so, core will 
execute  
"""
def execute_latex_controls(latex, equation = None, display = None):
    "Hande onesolver specific control sequences"
    if isinstance(equation, int):
        equation = MathHertz.Equation(user, equation)            
    elif isinstance(equation, ModelCloudMath.EquationStorage):
        equation = MathHertz.Equation(user, equation.number)
    elif isinstance(equation, MathHertz.Equation):
        equation = equation
    regexp1 = r"\\onesolver\[([\w =]*)\]"
    regexp2 = r"[\s*(\w*)\s*=\s*(\w*)\s*"
    if equation == None:
        equation = cherrypy.session['equation']
        solution = equation.solution_get('S')
    elif equation != None:
        solution = equation.solution_get('S')
    if display == None:
        display = {'symbol': True, 'value':False} # default
    elif display != None:
        display = cherrypy.session['display']
        
    replaceStrs = list()
    results = re.finditer(regexp1, latex)
    if results:
        for result in results:
            args = result.group(1)
            argDict = dict()
            argList= args.split('=')
            for idx in range(0,len(argList),2):
                key = str(argList[idx].strip())
                value = str(argList[idx+1].strip())
                temp = result.group(0).replace("\\", "\\\\")
                temp = temp.replace("[", "\\[")
                temp = str(temp.replace("]", "\\]"))
                variable = equation.variable_get(value, equation.instance)
                if display['symbol'] and not display['value']:
                    try:
                        replaceLatex = variable.desig.latex
                        replaceLatex= replaceLatex.replace('#', str(variable.number))
                    except AttributeError as err:
                        raise AttributeError('Unable to locate variable "%s" for desig %s with latex symbol. value = %s, error= %s'%(variable, value,value, err.message))
                elif display['value'] and not display['symbol']:
                    if solution == None:
                        varInput = equation.variable_get(value, equation.instance)
                        varValueStr = equation.variable_string(varInput, equation).split(' ')[0]
                    else:
                        varInput = equation.variable_get(value, solution)
                        varValueStr = equation.variable_string(varInput, solution).split(' ')[0]
                    varUnitSym = equation.variable_get_unit(varInput, 'selected-latex')
                    replaceLatex = varValueStr+ ' ' + varUnitSym 
                elif display['value'] and  display['symbol']:
                    replaceLatex = variable.desig.latex
                    replaceLatex= replaceLatex.replace(r'#', str(variable.number))
                    varInput = equation.variable_get(value, solution)
                    varString = equation.variable_string(varInput, solution).split(' ')[0]
                    varUnitSym = equation.variable_get_unit(varInput, 'selected-latex')
                    replaceLatex = r'\small{\doublelabel{$' + replaceLatex + r'$}{$' + varString+varUnitSym + r'$}}' 
                else:
                    replaceLatex = ''
                replaceStrs.append((temp, replaceLatex))
        for replaceStr in replaceStrs:
            latex = re.sub(replaceStr[0], replaceStr[1].replace('\\','\\\\'), latex)
    return latex
    
def change_display(displayType, value):
    actions = list()
    display = cherrypy.session['display']
    if displayType == 'value':
        display['value'] = bool(value)
    elif displayType == 'symbol':
        display['symbol'] = bool(value)
    cherrypy.session['display'] = display
    latex = cherrypy.session['circuit'].latex
    respDict = render_circuitikz(latex)
    actions += respDict['actions']
    return {'actions':actions}   
      
def render_circuitikz(latex, dest = None, equation = None, display = None):
    actions = list()
    if dest:
        filePath, fileName = os.path.split(dest)
        imageSessPath = filePath
        imagePath = os.path.join(imageSessPath, fileName + '.png')
    else:
        equation = cherrypy.session['equation']
        display = cherrypy.session['display']
        fileName = 'Diagram-Circuit%s'%time.strftime('%y%m%d%H%M%S')
        imageSessPath = os.path.join(get_server_setting('imagesdir'), cherrypy.session.id)
        actions.append(new_action('actCircuitTikzSubmit', 'Circuit', id =cherrypy.session['circuit'].id))      
        actions.append(new_action('actCircuitTikzSubmit', 'Solver', id =cherrypy.session['circuit'].id))
    imagePath = os.path.join(imageSessPath, fileName + '.png')
    if not os.path.isdir(imageSessPath):
        os.mkdir(imageSessPath)
        cherrypy.log.error('Making directory %s'%imageSessPath, 'DIAGRAM', logging.DEBUG)
    if latex == '':
        return {'actions':actions}
    else:
        # look in cache for existing results
        storage = FileStorage.FileStorage(os.path.join(get_server_setting('cachedir'), 'cache.fs'))
        db = DB(storage)
        connection = db.open()
        root = connection.root()
        cache = root.cache_image.get(latex, None)
        if cache:
            imgFile = open(imagePath, 'wb+')
            imgFile.write(cache.image)
            cache.update() # update timestamp
            root.cache_image[latex] = cache
            transaction.commit()
        else:            
            head =  \
"""\\documentclass[border=4pt]{standalone}
\\usepackage{tikz}
\\usepackage{circuitikz}
\\usepackage{siunitx}
\\pagestyle{empty}
\\begin{document}
\\begin{circuitikz}[%s]
\\newcommand*{\\doublelabel}[3][3em]{\\parbox{#1}{\\raggedleft #2 \\\\ #3}}
"""
            head = head%('american')
            tail = \
"""
\\end{circuitikz}
\\end{document}
"""
            latexDoc = head + latex + tail
            latexDoc = execute_latex_controls(latexDoc, equation, display)
            imagePath = os.path.join(imageSessPath, fileName + '.png')
            args = '-interaction=nonstopmode -halt-on-error -jobname %s -output-directory=%s '%(fileName, imageSessPath)
            # string -> txt (\todo: fix, should render as a string
            if texMode == 'file':
                texFileLoc = os.path.join(imageSessPath, fileName + '.tex')
                f = open(texFileLoc, 'w')
                f.write(latexDoc)
                f.close()
                # tex -> pdf processingsa
                cmd = '"%s" %s %s'%(os.path.join(latexPath, latexEngine), args, texFileLoc)
            elif texMode == 'string':
                # string -> pdf processing
                cmd = '"%s" %s "%s"'%(os.path.join(latexPath, latexEngine), args, latexDoc.replace('\n', ' '))
            cherrypy.log.error("Running %s"%cmd, 'DIAGRAM', logging.DEBUG)
            p = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
            stdoutdata, stderrdata  = p.communicate()
            if stderrdata:
                cherrypy.log.error('Error: %s'%stderrdata, 'DIAGRAM', logging.ERROR)
            idx = stdoutdata.find('!')
            if idx >0 :
                cherrypy.log.error('Error: %s'%stdoutdata[idx:], 'DIAGRAM', logging.ERROR, True)
                raise Exception('Latex Error ' + stdoutdata[idx:])
            else:
                imgMagicCmd = 'convert -trim -density 128 "%s.pdf" -background none -undercolor none -pointsize 6 label:"               " -gravity SouthEast -append -pointsize 6 label:"(c) OneSolver.com" -gravity SouthEast -append "%s"'
                if not dest:
                    # latex did not have any errors, save to ram
                    if cherrypy.session.has_key('circuit'):
                        dbCircuit = cherrypy.session['circuit']
                    else:
                        session_new()
                    dbCircuit.latex = latex
                    dbCircuit.equation.instance = equation.instance
                    cherrypy.session['circuit'] = dbCircuit
                    # pdf -> png processing (imagemagick)   
                    cmd = imgMagicCmd%(os.path.join(imageSessPath, fileName), imagePath)
                    cherrypy.log.error('Running %s'%cmd, 'DIAGRAM', logging.DEBUG)
                    p = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
                    stdoutdata, stderrdata  = p.communicate()
                    if stdoutdata:
                        cherrypy.log.error('Output: %s'%stdoutdata, 'DIAGRAM', logging.INFO)
                    if stderrdata:
                        cherrypy.log.error('Error: %s'%stderrdata, 'DIAGRAM', logging.ERROR)
                else:
                    cmd = imgMagicCmd%(os.path.join(imageSessPath, fileName), imagePath)
                    p = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
                    stdoutdata, stderrdata  = p.communicate()
                    if stdoutdata:
                        cherrypy.log.error('Output: %s'%stdoutdata, 'DIAGRAM', logging.INFO)
                    if stderrdata:
                        cherrypy.log.error('Error: %s'%stderrdata, 'DIAGRAM', logging.ERROR)
                cache = ModelCore.CacheImage(imagePath)
                root.cache_diagram[latex] = cache
                transaction.commit()
        connection.close() #close cache
        db.close()
        storage.close()
        return {'actions':actions}