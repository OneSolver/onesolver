import sqlalchemy
from Core.model.Base import Base  
from CloudMath.model import Model as ModelCloudMath
from Core.model import Model as ModelCore

from sqlalchemy import Table, Column, Integer, String, Boolean, ForeignKey, DateTime, Float, PickleType
from sqlalchemy.orm import relationship, backref, column_property
from sqlalchemy.ext.declarative import declarative_base

import glob, sys, os

AssocMechanicalDrawingVariable = Table('assocmechanicaldrawingvariable', Base.metadata,
    Column('mechanicaldrawing_id', Integer, ForeignKey('mechanicaldrawing.id')),
    Column('variable_id', Integer, ForeignKey('variable.id'))
)

class MechanicalDesign(Base):
    __tablename__ = 'mechanicaldesign'
    id = Column(Integer, primary_key=True)
    equationStorageId = Column('equationstorage_id', Integer, ForeignKey('equationstorage.id'))
    equation = relationship('EquationStorage', uselist=False)
    drawings = relationship('MechanicalDrawing', uselist=True)
    def __init__(self, equation, drawings):
        self.equation = equation
        self.drawings = drawings
    def __repr__(self):
        return "<MechanicalDesign(%s, %s)>" % (self.id, self.drawings)
    
class MechanicalDrawing(Base):
    __tablename__ = 'mechanicaldrawing'
    id = Column(Integer, primary_key=True)
    mechDesignId = Column('mechdesign_id', Integer, ForeignKey('mechanicaldesign.id'))
    perspective = Column(String)
    initUnit = Column('initunit', Integer)
    drawing = Column(String)
    variables = relationship("Variable", secondary=AssocMechanicalDrawingVariable, collection_class=list, lazy='joined',  join_depth=2)
    def __init__(self, perspective, variables, drawing, initUnit = None):
        self.perspective = perspective
        self.variables = variables
        self.drawing = drawing
        self.initUnit = initUnit
    def __repr__(self):
        return "<MechanicalDrawing(%s, %s)>" % (self.id, self.perspective)

def load_mech_design(equation, dbSession = None, unit = None):
    sys.path.append(os.path.abspath('../../../')) #server root
    sys.path.append(os.path.abspath('../../')) #apps path
    from ServerSettings import get_server_setting
    from ServerSettings import db, Session
    from re import findall, compile
    if not dbSession:
        from sqlalchemy.orm import sessionmaker
        DbSession = sessionmaker(db)
        dbSession=DbSession()
    mechDrawings = list()
    if isinstance(equation, (int, str) ):
        equationId = int(equation)
        equation = dbSession.query(ModelCloudMath.EquationStorage).filter(ModelCloudMath.EquationStorage.number == equationId).first()
    elif isinstance(equation,ModelCloudMath.EquationStorage):
        equationId = int(equation.number)
    searchStr = '%d_*.mech'%equationId
    files =  glob.glob(os.path.join(get_server_setting('mechdrawdir'), searchStr))
    if not files:
        raise Exception('Unable to locate files using search string "%s"'%searchStr)
    for file in files:
        mechVariables = list()
        fileBase  = os.path.basename(file)
        filename, ext = fileBase.split('.')
        _, perspective = filename.split('_')
        fId = open(file, 'r')
        drawing = fId.read()
        fId.close()
        #location variables in drawings
        for variable in equation.variables:
            desigStr = variable.desig.longhand + str(variable.number)
            patternStr = r'(\(| |,|\+|\-|\*)(%s)'%desigStr
            pattern = compile(patternStr)
            if len(findall(pattern, drawing)) > 0:
                mechVariables.append(variable)
        mechDrawing = MechanicalDrawing(perspective, mechVariables, drawing, unit)
        dbSession.add(mechDrawing)  
        mechDrawings.append(mechDrawing)
    return MechanicalDesign(equation, mechDrawings)
        
if __name__ == "__main__":
    print load_mech_design(6, None)
        
        