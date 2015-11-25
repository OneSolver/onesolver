import sqlalchemy
from Core.model.Base import Base  
from CloudMath.model import Model as ModelCloudMath

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Float, PickleType
from sqlalchemy.orm import relationship, backref, column_property
from sqlalchemy.ext.declarative import declarative_base
import datetime


class DiagramCircuit(Base):
    __tablename__ = 'diagramcircuit'
    id = Column(Integer, primary_key=True)
    equation_id = Column(Integer, ForeignKey('equationstorage.id'))
    equation = relationship('EquationStorage', uselist=False)
    latex = Column(String)
    def __init__(self, latex, equation):
        self.latex = latex
        self.equation = equation
    def __repr__(self):
        return "<DiagramCircuit(%s)>" % (self.latex)
