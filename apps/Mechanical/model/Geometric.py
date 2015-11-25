import matplotlib
import matplotlib.lines as lines
import matplotlib.transforms as transforms
import matplotlib.font_manager as FontManager
from matplotlib.patches import Rectangle as rectangle

#from shapely import geometry as geo
#import descartes
import time
from FuncDesigner import *
from openopt import *
from numpy import linspace, abs, sqrt, sign
from numpy import tan, sin, cos, arctan2, degrees, radians
from shapely import geometry as shapelygeo
from shapely import affinity as shapelyaff
from shapely import ops, wkt
import descartes
from collections import defaultdict
import threading
import datetime
import cherrypy
# constants
options = ['none', 'letter-landscape']
class ConstraintDimensional():
    """Dimensional constraints control the distance, length, angle, and radius values of objects"""
    def __init__(self, *args, **kwargs):
        pass
class ConstraintDistance(ConstraintDimensional):
    def __init__(self, geo1, geo2, distance):
        self.geos = [geo1, geo2]
        self.distance = distance
class ConstraintGeometric():
    """Geometric constraints control the relationships of objects with respect to each other"""
    def __init__(self):
        pass
            
class ModifierBase(object):
    """ modify multiple shapes returns only one shape"""
    def __init__(self, *args):
        self.geometries = list()
        for arg in args:
            self.geometries.append(arg)
    def modify(self):
        pass
class ModifierSymetricDifference(ModifierBase):
    def __init__(self, *args):
        ModifierBase.__init__(self, *args)
    def modify(self):
        geoDiff = self.geometries[0].symmetric_difference(self.geometries[1])
        if geoDiff.is_empty:
            raise Exception('Symetric difference was empty.')
        else: 
            return geoDiff 
class GroupShapes(object):
    def __init__(self, *args):
        self.geometries = list()
        self.annotations = list()
        self.anchors = list()
        for arg in args:
            self.geometries.append(arg)
            self.annotations += arg.annotations
            self.anchors += arg.anchors  
        self._update_geometry()
    def _update_geometry(self):
        geos = list()
        for geometry in self.geometries:
            geos.append(geometry.geometry)
        geoCollect ="GEOMETRYCOLLECTION (%s)" % ", ".join(g.wkt for g in geos)
        self.geometry = wkt.loads(geoCollect)
    def append(self, geometry):
        self.geometries.append(geometry)
        self.annotations+=geometry.annotations
        self.anchors+=geometry.anchors
        self._update_geometry()
    def get_lim(self):
        lims = self.geometries[0].get_lim()
        if len(self.geometries) > 1:
            for geometry in self.geometries[1:]:
                geoLim = geometry.get_lim()
                if geoLim[0] < lims[0]: lims[0] = geoLim[0] 
                if geoLim[1] > lims[1]: lims[1] = geoLim[1]
                if geoLim[2] < lims[2]: lims[2] = geoLim[2]
                if geoLim[3] > lims[3]: lims[3] = geoLim[3]
        return lims
    def __getattr__(self, name):
        if name == 'patches':
            patches = list()
            for geometry in self.geometries:
                patches.append(descartes.PolygonPatch(geometry.geometry, edgecolor = geometry.edgecolor, facecolor = geometry.facecolor, 
                                                      linewidth = geometry.linewidth, linestyle = geometry.linestyle,  hatch = geometry.hatch))
            return patches
        elif name == 'x':  
            center = self.geometry.centroid
            return center.x
        elif name == 'y': 
            center = self.geometry.centroid
            return center.y
        elif name == 'width': 
            xmin, _, xmax, _ = self.geometry.bounds
            return float(xmax-xmin)
        elif name == 'height': 
            _, ymin, _, ymax = self.geometry.bounds
            return float(ymax-ymin)
    def __repr__(self):
        return '<GroupShapes(%s)>'%(self.geometries)

class ModifierUnion(ModifierBase):
    def __init__(self, *args):
        ModifierBase.__init__(self, *args)
    def modify(self):
        return ops.cascaded_union(self.geometries)
class ModifierTranslate(ModifierBase):
    def __init__(self, geometry, *args):
        ModifierBase.__init__(self, geometry)
        if len(args) == 1:
            xOffset, yOffset= args[0]
        else:
            xOffset = args[0]
            yOffset = args[1]
        self.xOffset = xOffset
        self.yOffset = yOffset
    def modify(self):
        return shapelyaff.translate(self.geometries[0], self.xOffset, self.yOffset)
class ModifierScale(ModifierBase):
    def __init__(self, geometry, *args):
        ModifierBase.__init__(self, geometry)
        self.xFactor = float(args[0])
        self.yFactor = float(args[1])
    def modify(self):
        return shapelyaff.scale(self.geometries[0], self.xFactor, self.yFactor)
             

class Annotate(object):
    anchors = list()
    def __init__(self, shape, anchors, mode = 'auto', direction = 'n', 
                 labelLocation = 'inner', labelOffset = 45.0, show = 'value'):
        self.show = show
        self.shape = shape
        self.mode = mode
        self.anchors = anchors
        self.factor = 1.0
        self.direction = direction.lower()[0]
        self.labelLocation = labelLocation
        self.offset = 0.0
        self.start = 0.0
        self.labelOffset = labelOffset
    def __setattr__(self, name, value):
        if  name == 'offset': 
            if hasattr(self, '_transScale'):
                pass
            self.__dict__['offset'] = value
        else:
            self.__dict__[name] = value
    def update(self, draftspace):
        fig = draftspace.fig
        ax = fig.gca()
        anchor1, anchor2 = (self.anchors[0], self.anchors[1])
        dx = anchor2.x - anchor1.x
        dy = anchor2.y - anchor1.y
        if self.direction in ('n', 's'): 
            xy1 = [anchor1.x, self.start]
            xy2 = [anchor2.x, self.start]
        if self.direction in ('e', 'w'): 
            xy1 = [self.start, anchor1.y]
            xy2 = [self.start, anchor2.y]
        xytext1 = ((xy1[0] + xy2[0])/2, (xy1[1] + xy2[1])/2)
        # convert data coordinates into display coordinates
        data2display = ax.transData.transform
        display2data = ax.transData.inverted().transform
        transdisplay2data = transforms.ScaledTranslation
        xy3 = data2display(xy1)
        xy4 = data2display(xy2)
        xytext2 = data2display(xytext1)
        dx1, dy1 = (abs(xy3[0] - xy4[0]), abs(xy3[1] - xy4[1]))
        xStart2, yStart2 = data2display((self.start, self.start))
        # apply adjustements in display coordinates
        if self.direction == 'n': 
            xy3[1] =  yStart2 + self.offset
            xy4[1] =  yStart2 + self.offset
            xytext2[1] =  yStart2 + self.offset
            if self.show == 'value':
                self._label  = '%0.1f'%abs(dx)
            elif self.show == 'symbol':
                self._label = self.symbol
            self._lengthPx = dx1
            # transformation
            offset = transdisplay2data(0.0, self.offset/72, fig.dpi_scale_trans)
            offsetTransform = ax.transData + offset
        elif self.direction == 's':
            xy3[1] =  yStart2 - self.offset
            xy4[1] =  yStart2 - self.offset
            xytext2[1] =  yStart2 - self.offset
            if self.show == 'value':
                self._label  = '%0.1f'%abs(dx)
            elif self.show == 'symbol':
                self._label = self.symbol
            self._lengthPx = dx1
            # transformation
            offset = transdisplay2data(0.0, -self.offset/72, fig.dpi_scale_trans)
            offsetTransform = ax.transData + offset           
        elif self.direction == 'e': 
            xy3[0] =  xStart2 + self.offset
            xy4[0] =  xStart2 + self.offset
            xytext2[0] =  xStart2 + self.offset
            if self.show == 'value':
                self._label  = '%0.1f'%abs(dy)
            elif self.show == 'symbol':
                self._label = self.symbol
            self._lengthPx = dy1
            # transformation
            offset = transdisplay2data(self.offset/72, 0.0, fig.dpi_scale_trans)
            offsetTransform = ax.transData + offset           
        elif self.direction == 'w':
            xy3[0] =  xStart2 - self.offset
            xy4[0] =  xStart2 - self.offset
            xytext2[0] =  xStart2 - self.offset
            if self.show == 'value':
                self._label  = '%0.1f'%abs(dy)
            elif self.show == 'symbol':
                self._label = self.symbol
            self._lengthPx = dy1
            # transformation
            offset = transdisplay2data(-self.offset/72, 0.0, fig.dpi_scale_trans)
            offsetTransform = ax.transData + offset           
        # change label location based available spacing
        xylabel1 = xytext2
        if self._lengthPx < 40.0 and self.mode == 'auto':
            self.labelLocation = 'outer'
            if self.direction in  ('e', 'w'):
                xylabel1[1] = xylabel1[1] + self.labelOffset
            elif self.direction in ('n', 's'):
                xylabel1[0] = xylabel1[0] + self.labelOffset
        # convert display to data coordinates
        xy5 = display2data(xy3)
        xy6 = display2data(xy4)
        xytext3 = display2data(xytext2)
        xylabel2 = display2data(xylabel1)
        # final assignnment
        self._xy1 = xy5
        self._xy2 = xy6
        self._xytext = xytext3
        self._xylabel = xylabel2
        self._transScale = offsetTransform
    def draw(self, drawSpace):
        fig = drawSpace.fig
        ax = fig.gca()
        font = FontManager.FontProperties(family='Arial', size=12)
        bbox = dict(boxstyle="square,pad=0.0", fc="w", ec="w", lw=1)
        #draw lines
        color = 'c'
        alpha = .5
        if self.labelLocation == 'inner':
            self._annotate1 = ax.annotate('', xy = self._xy1, xycoords = self._transScale, xytext = self._xy2, textcoords = self._transScale, horizontalalignment= 'center',
                            verticalalignment='center', arrowprops=dict(arrowstyle='<->', color = color), zorder = 4)
            xArrow, yArrow = self._annotate1._get_xy_display()
            self._annotate2 = ax.annotate('', xy = (self.anchors[0].x, self.anchors[0].y), xycoords = 'data', xytext = self._xy1, textcoords = self._transScale, horizontalalignment= 'center',
                            verticalalignment='center', arrowprops=dict(arrowstyle='-', color = color, alpha = alpha), zorder = 4)
            self._annotate3 = ax.annotate('', xy = (self.anchors[1].x, self.anchors[1].y), xycoords = 'data', xytext = self._xy2, textcoords = self._transScale, horizontalalignment= 'center',
                            verticalalignment='center', arrowprops=dict(arrowstyle='-', color = color, alpha = 0.5), zorder = 4)
            self._textbox1 = ax.text( self._xytext[0], self._xytext[1], self._label, horizontalalignment= 'center', verticalalignment='center', color = 'blue', 
                    fontproperties=font, bbox = bbox, transform=self._transScale, zorder = 5)
        elif self.labelLocation == 'outer':
            self._annotate1 = ax.annotate('', xy = self._xy1, xycoords = self._transScale, xytext = self._xy2, textcoords = self._transScale, horizontalalignment= 'center',
                            verticalalignment='center', arrowprops=dict(arrowstyle='<->', color = color), zorder = 4)
            xArrow, yArrow = self._annotate1._get_xy_display()
            self._annotate2 = ax.annotate('', xy = (self.anchors[0].x, self.anchors[0].y), xycoords = 'data', xytext = self._xy1, textcoords = self._transScale, zorder = 4, horizontalalignment= 'center',
                            verticalalignment='center', arrowprops=dict(arrowstyle='-', color = color, alpha = alpha))
            self._annotate3 = ax.annotate('', xy = (self.anchors[1].x, self.anchors[1].y), xycoords = 'data', xytext = self._xy2, textcoords = self._transScale, zorder = 4, horizontalalignment= 'center',
                            verticalalignment='center', arrowprops=dict(arrowstyle='-', color = color, alpha = alpha))
            self._textbox1 = ax.text( self._xytext[0], self._xytext[1], self._label, horizontalalignment= 'center', verticalalignment='center', color = 'blue', zorder = 5, fontproperties=font, bbox = bbox, transform=self._transScale)
            self._annotate4 = ax.annotate('', xy =  self._xytext, xycoords = self._transScale, xytext = self._xy1, textcoords = self._transScale, horizontalalignment= 'center',
                            verticalalignment='center', arrowprops=dict(arrowstyle='-', color = color, alpha = 0.5), zorder = 4)

class Anchor(object):
    def __init__(self, x, y):
        self.base = dict()
        self.base['x'] = float(x)
        self.base['y'] = float(y)
        self.geometry = shapelygeo.Point(x,y)
        self.modifiers = list()
        self.color = 'b'
    def __getattr__(self, name):
        if name == 'x':  
            return self.geometry.x
        elif name == 'y': 
            return self.geometry.y
        else:
            return self.__dict__[name]
    def __repr__(self):
        return '<Anchor(%s,%s)>'%(self.x, self.y)
     
class Geo(object):
    def __init__(self, *args, **kwargs):
        self.__dict__['modifiers'] = list()
        self.__dict__['geometry'] = None
        self.__dict__['base'] = dict()
        self.__dict__['name'] = kwargs.get('name', self.__class__.__name__)
        self.__dict__['idGeo'] = kwargs.get('idGeo', 1)
        self.__dict__['color'] = kwargs.get('color', 'k')
        self.__dict__['anchors'] = kwargs.get('anchors', list())
        self.__dict__['annotations'] = kwargs.get('annotations', list())
    def __setattr__(self, name, value):
        self.__dict__[name] = value
    def __getattr__(self, name):
        return self.__dict__[name]
    def get_lim(self, ax = None):
        pass
    def add_anchor(self, *args):
        if len(args) == 2:
            x = args[0]
            y = args[1]
        else:
            x, y = args
        self.anchors.append(Anchor(x, y))
        return self.anchors[-1]
    def modify_anchors(self, modifer):
        for anchor in self.anchors:
            if isinstance(modifer, ModifierTranslate):
                anchorModifier= ModifierTranslate(anchor.geometry, modifer.xOffset , modifer.yOffset)
            elif isinstance(modifer, ModifierScale):
                dx = (anchor.x-self.x)*modifer.xFactor - (anchor.x-self.x)
                dy = (anchor.y-self.y)*modifer.yFactor - (anchor.y-self.y)
                anchorModifier= ModifierTranslate(anchor.geometry, dx , dy)
            anchor.geometry = anchorModifier.modify()
            anchor.modifiers.append(anchorModifier)
    def add_annotation(self, anchors, mode = None, direction = None):
        self.annotations.append(Annotate(self, anchors, mode, direction))
    def transform(self):
        self.update()
    def update(self):
        for annotation in self.annotations:
            annotation.update()
               
class Shape(Geo):
    def __init__(self, *args, **kwargs):
        Geo.__init__(self, *args, **kwargs)
        self.__dict__['facecolor'] = kwargs.get('facecolor', 'none')
        self.__dict__['edgecolor'] = kwargs.get('edgecolor', 'k')
        self.__dict__['hatch'] = kwargs.get('hatch', '')
        self.__dict__['fill'] = kwargs.get('fill', False)
        self.__dict__['linewidth'] = kwargs.get('linewidth', 2.0)
        self.__dict__['linestyle'] = kwargs.get('linestyle', 'solid') #solid ,dashed , dashdot , dotted
    def __setattr__(self, name, value):
        if name == 'x':
            dx = value - self.x
            modifier = ModifierTranslate(self.geometry, dx, 0)
            self.modifiers.append(modifier)
            self.geometry = modifier.modify()
            self.modify_anchors(modifier)
            return
        elif name == 'y':
            dy = value - self.y
            modifier = ModifierTranslate(self.geometry,0, dy)
            self.modifiers.append(modifier)
            self.geometry = modifier.modify()
            self.modify_anchors(modifier)
            return
        elif name == 'width':
            factor = float(value)/float(self.width)
            modifier = ModifierScale(self.geometry, factor, 1)
            self.modifiers.append(modifier)
            self.geometry = modifier.modify()
            self.modify_anchors(modifier)
            return
        elif name == 'height':
            factor = float(value)/float(self.height)
            modifier = ModifierScale(self.geometry, 1, factor)
            self.modifiers.append(modifier)
            self.geometry = modifier.modify()
            self.modify_anchors(modifier)
            return
        else:
            Geo.__setattr__(self, name, value)
    def __getattr__(self, name):
        if name == 'patch':
            return descartes.PolygonPatch(self.geometry, edgecolor = self.edgecolor, facecolor = self.facecolor, linewidth = self.linewidth, linestyle = self.linestyle,  hatch = self.hatch)
        elif name == 'x':  
            center = self.geometry.centroid
            return center.x
        elif name == 'y': 
            center = self.geometry.centroid
            return center.y
        elif name == 'width': 
            xmin, _, xmax, _ = self.geometry.bounds
            return float(xmax-xmin)
        elif name == 'height': 
            _, ymin, _, ymax = self.geometry.bounds
            return float(ymax-ymin)
        else:
            return Geo.__getattr__(self, name)
    def get_lim(self, ax = None):
        extent = self.geometry.bounds
        xMin, xMax, yMin, yMax = (extent[0], extent[2], extent[1], extent[3])
        if ax:
            for annotate in self.annotations:
                annotate.update(ax)
                if hasattr(annotate, '_xy1'):
                    if annotate._xy1[0] < xMin: xMin = annotate._xy1[0]
                    elif annotate._xy1[0] > xMax: xMax = annotate._xy1[0]
                    if annotate._xy1[1] < yMin: yMin = annotate._xy1[1]
                    elif annotate._xy1[1] > yMax: yMax = annotate._xy1[1]
        return [xMin, xMax, yMin, yMax]
    def modify_scale(self, value):  
        factor = float(value)
        modifier = ModifierScale(self.geometry, factor, factor)
        self.modifiers.append(modifier)
        self.geometry = modifier.modify()
        self.modify_anchors(modifier)
    def __repr__(self):
        return '<Shape(%s)>'%(self.id)         

class ShapeRectangle(Shape):
    def __init__(self, *args, **kwargs):
        Shape.__init__(self, *args, **kwargs)
        if len(args) == 4:
            self.base['x'] = float(args[0])
            self.base['y'] = float(args[1])
            self.base['width'] = float(args[2])
            self.base['height'] = float(args[3])
        elif len(args) == 3:
            x, y = args[0]
            self.base['x'] = float(x)
            self.base['y'] = float(y)
            self.base['width'] = float(args[2])
            self.base['height'] = float(args[3])
        self.geometry = shapelygeo.box(self.base['x'] - self.base['width']/2, self.base['y'] - self.base['height']/2, self.base['x'] + self.base['width']/2, self.base['y'] + self.base['height']/2)
    def __getattr__(self, name):
        return Shape.__getattr__(self, name)
    def __setattr__(self, name, value):
        Shape.__setattr__(self, name, value)
    def add_anchor(self, *args):
        anchor =  Shape.add_anchor(self, *args)
        return anchor
    def __repr__(self):
        return '<ShapeRectangle(%s, %s, %s, %s)>'%(self.base['x'], self.base['y'],self.base['width'], self.base['height'])
    
class ShapeCircle(Shape):
    def __init__(self, *args, **kwargs):
        Shape.__init__(self, *args, **kwargs)
        if len(args) == 3:
            self.base['x'] = float(args[0])
            self.base['y'] = float(args[1])
            self.base['radius'] = float(args[2])
        elif len(args) == 2:
            x, y = args[0]
            self.base['x'] = float(x)
            self.base['y'] = float(y)
            self.base['radius'] = float(args[2])
        self.geometry = shapelygeo.Point(self.base['x'], self.base['y']).buffer(self.base['radius'])
    def __getattr__(self, name):
        if name == 'radius':
            xmin, _, xmax, _ = self.geometry.bounds
            return (xmax-xmin)/2.0
        else:
            return Shape.__getattr__(self, name)
    def __setattr__(self, name, value):
        if name == 'radius':
            factor = float(value)/self.radius
            modifier = ModifierScale(self.geometry, factor, factor)
            self.modifiers.append(modifier)
            self.geometry = modifier.modify()
            self.modify_anchors(modifier)
            return
        else:
            Shape.__setattr__(self, name, value)
    def add_anchor(self, *args):
        if len(args) == 2:
            anchor = Shape.add_anchor(self, *args)
        elif len(args) == 1:
            if isinstance(args[0], (list, tuple)):
                anchor =  Shape.add_anchor(self, *args)
            else:
                angDeg = float(args[0])
                angRad = radians(angDeg)
                dx = self.radius*cos(angRad)
                dy = self.radius*sin(angRad)
                y = self.y + dy
                x = self.x + dx
                anchor = Shape.add_anchor(self, x, y)
        return anchor
    def __repr__(self):
        return '<ShapeCircle(%s, %s, %s)>'%(self.x, self.y, self.radius)
class ShapeCompound(Shape):
    def __init__(self, *args, **kwargs):
        Shape.__init__(self, *args, **kwargs)
        shapes = list()
        for arg in args:
            if isinstance(arg, Geo):
                shapes.append(arg)
            elif isinstance(arg, str):
                modifierName = arg
            elif isinstance(arg, list):
                for shape in arg:
                    shapes.append(shape)
            else:
                raise Exception('Unknown argument %s.'%arg)    
        self.base['x'] = shapes[0].base['x']
        self.base['y'] = shapes[0].base['y']
        geometries = list()
        if modifierName == 'Union':
            for shape in shapes:
                geometries.append(shape.geometry)
            modifier = ModifierUnion(*geometries)
        elif modifierName == 'SymetricDifference':
            for shape in shapes:
                geometries.append(shape.geometry)
            modifier = ModifierSymetricDifference(*geometries)
        else:
            raise Exception('Unknown modifier %s'%modifierName)            
        self.modifiers.append(modifier)
        self.geometry = modifier.modify()
    def __getattr__(self, name):
        return Shape.__getattr__(self, name)
    def __setattr__(self, name, value):
        Shape.__setattr__(self, name, value)
    def add_anchor(self, *args):
        anchor =  Shape.add_anchor(self, *args)
        return anchor
    def __repr__(self):
        return '<ShapeCompound(%s, %s, %s)>'%(self.idGeo, self.x, self.y)
            
class DrawDraftSpace():
    def __init__(self, draftSpace):
        fig = draftSpace.fig
        fig.set_dpi(draftSpace.dpi)
        self.xLim = [0.0, 0.0]
        self.yLim = [0.0, 0.0]
        xFigInch, yFigInch = fig.get_size_inches()
        self.dpiRes = [xFigInch*draftSpace.dpi, yFigInch*draftSpace.dpi]          
        
    def set_limit(self, draftSpace, margin = 0.0):
        fig = draftSpace.fig
        ax = fig.gca()
        dx = abs(self.xLim[0] - self.xLim[1])
        dy = abs(self.yLim[0] - self.yLim[1])
        xLim0 = self.xLim[0] - dx*margin
        xLim1 = self.xLim[1] + dx*margin
        yLim0 = self.yLim[0] - dy*margin
        yLim1 = self.yLim[1] + dy*margin
        ax.set_xlim([xLim0, xLim1])
        ax.set_ylim([yLim0, yLim1])
        
    def draw(self, draftSpace, spacing = 0):
        fig = draftSpace.fig
        ax = fig.gca()
        #calculate text width
        dotPerInch = fig.get_dpi()
        figWidthInch, figHeightInch = fig.get_size_inches()
        figWidthDot, figHeightDot = (dotPerInch*figWidthInch, dotPerInch*figHeightInch)
        # transformations
        display2data = ax.transData.inverted().transform
        data2display = ax.transData.transform
        transdisplay2data = transforms.ScaledTranslation
        # get extents of shape in data space
        limDraft = draftSpace.shapes[0].get_lim()
        if len(draftSpace.shapes) > 1:
            for shape in draftSpace.shapes[1:]:
                lims = shape.get_lim()
                if lims[0] < limDraft[0]: limDraft[0] = lims[0] 
                if lims[1] > limDraft[1]: limDraft[1] = lims[1]
                if lims[2] < limDraft[2]: limDraft[2] = lims[2]
                if lims[3] > limDraft[3]: limDraft[3] = lims[3]
        #group annotations by direction
        anchorDirection = defaultdict(list)
        for idx, shape in enumerate(draftSpace.shapes):
            for annotation in shape.annotations:
                if annotation.mode == 'auto':
                    anchorDirection[annotation.direction].append(annotation)
        # set limits to size of shapes and annotation
        self.xLim = list(limDraft[0:2])
        self.yLim = list(limDraft[2:4])
        self.set_limit(draftSpace, 0.04)
        for idx, shape in enumerate(draftSpace.shapes):
            # define annotation locations
            xMin, xMax = self.xLim
            yMin, yMax = self.yLim
            for direction, annotations in anchorDirection.items():
                offset = 0.0
                start = 0.0
                for idx, annotation in enumerate(annotations):
                    # draw annotation
                    annotation.update(draftSpace)
                    annotation.draw(draftSpace)
                    bb = annotation._textbox1.get_window_extent(fig.canvas.get_renderer())
                    bbWidth = bb.width
                    bbHeight = bb.height
                    if direction == 'e':
                        start = xMax
                        offset += bbWidth + spacing
                    elif direction == 'w':
                        start = xMin
                        offset += bbWidth + spacing
                    elif direction == 'n':
                        start = yMax
                        offset += bbHeight + spacing
                    elif direction == 's':
                        start = yMin
                        offset += bbHeight + spacing
                    annotation.start = start
                    annotation.offset = offset
                    annotation.update(draftSpace)
                    annotation._textbox1.remove()
                    annotation._annotate1.remove()
                    annotation._annotate2.remove()
                    annotation._annotate3.remove()
                    if hasattr(annotation, '_annotate4'):
                        annotation._annotate4.remove()
        for idx, shape in enumerate(draftSpace.shapes):
            if isinstance(shape, GroupShapes):
                patches = shape.patches
            else:
                patches = [shape.patch]
            for patch in patches:
                patch = ax.add_patch(patch)
                if draftSpace.showAnchor:
                    xAnchor = list()
                    yAnchor = list()
                    for anchor in shape.anchors:
                        xAnchor.append(anchor.x)
                        yAnchor.append(anchor.y)
                    if xAnchor:
                        ax.plot(xAnchor, yAnchor, marker='x',color= anchor.color, linestyle='None', zorder = 10)
        for direction, annotations in anchorDirection.items():
            for idx, annotation in enumerate(annotations):
                annotation.draw(draftSpace)
        fig.canvas.draw()
                
class DraftSpace():
    xAspect = 0.0
    yAspect = 0.0
    dpi = 75
    showAnchor = False
    showGrid = False
    showTick = False
    drawSpace = None
    path = ''
    name = 'mech'
    def __init__(self, **kwargs):
        self.shapes = list()
        self.ratio = kwargs.get('ratio', '1:1')
        self.title = kwargs.get('title', 'Untitled')
        self.authorOrigin = kwargs.get('author', 'Grant Pitel')
        self.authorModify = kwargs.get('author', 'Anonymous')
        self.number = kwargs.get('number', 'N/A')
        self.dateOrigin = kwargs.get('date', datetime.date.today().strftime("%m-%d-%Y"))
        self.dateModify = kwargs.get('date', datetime.date.today().strftime("%m-%d-%Y"))
        self.company = kwargs.get('company', 'OneSolver LLC')
        self.perspective = kwargs.get('perspective', 'N/A')
        backend = kwargs.get('backend', 'Agg')
        matplotlib.use(backend)
        import  matplotlib.pyplot as pyplot 
        self.fig = pyplot.figure()
    def draw_background(self, size = 'none'):
        #definitions
        fig = self.fig
        tc = 'k' #title color
        bc = 'k' #border color
        ptnperinch = 72.0
        txtPadInch = 0.05
        txtHeightInch = 12.0/ptnperinch
        borderWidth = 0.25
        xyTitle = (8.0, 1.0)
        if size == 'letter-landscape':
            xyPaper = (11.0, 8.5)
            margins = {'top': 0.25, 'bottom': 0.25, 'left':0.25, 'right':0.25}
            self.fig.set_size_inches(xyPaper[0], xyPaper[1])
        print 'the size is %s'%size
        #background
        ax = self.fig.gca()
        objDim, draftDim = self.ratio.split(':')
        scale = float(objDim)/float(draftDim)
        if size != 'none':
            ax.set_axis_on()
            xLim = scale*(xyPaper[0] - margins['left'] - margins['right'])/2.0
            yLim = scale*(xyPaper[1] - margins['top'] - margins['bottom'])/2.0
            ax.set_xlim(-xLim, xLim)
            ax.set_ylim(-yLim, yLim)
            #border
            ax.spines['top'].set_linewidth(2.0)
            ax.spines['bottom'].set_linewidth(2.0)
            ax.spines['right'].set_linewidth(2.0)
            ax.spines['left'].set_linewidth(2.0)
            position = [margins['left']/xyPaper[0], margins['bottom']/xyPaper[1],
                             1.0 - (margins['right']+margins['left'])/xyPaper[0], 1.0 - (margins['top']+margins['bottom'])/xyPaper[1]]
            ax.set_position(position)
            ax.tick_params(axis='both', which='both', left = 'off', right = 'off', bottom='off', top='off',
                                labelbottom='off', labeltop='off', labelleft='off', labelright='off')
            llCorner = ((margins['left']+borderWidth)/xyPaper[0], 
                        (margins['bottom']+borderWidth)/xyPaper[1])
            urCorner = (1.0-(margins['right']+borderWidth)/xyPaper[0], 
                        1.0-(margins['top']+borderWidth)/xyPaper[1])
            lrCorner = (urCorner[0], llCorner[1])
            ulCorner = (llCorner[0], urCorner[1])
            lineLeft1 = lines.Line2D((llCorner[0],  ulCorner[0]), (llCorner[1], ulCorner[1]), transform = fig.transFigure, color = bc)
            lineRight1 = lines.Line2D( (lrCorner[0], urCorner[0]),(lrCorner[1], urCorner[1]) , transform = fig.transFigure, color = bc)
            lineTop1= lines.Line2D( (urCorner[0], ulCorner[0]), (urCorner[1], ulCorner[1]), transform = fig.transFigure, color = bc)
            lineBottom1 = lines.Line2D( (llCorner[0], lrCorner[0]), (llCorner[1], lrCorner[1]), transform = fig.transFigure, color = bc)
            ax.add_artist(lineBottom1)
            ax.add_artist(lineRight1)
            ax.add_artist(lineTop1)
            ax.add_artist(lineLeft1) 
            #title block border
            lineTop2 = lines.Line2D((lrCorner[0],  lrCorner[0] - xyTitle[0]/xyPaper[0]), (lrCorner[1]+xyTitle[1]/xyPaper[1], lrCorner[1]+xyTitle[1]/xyPaper[1]), transform = fig.transFigure, color = tc)
            lineLeft2 = lines.Line2D((lrCorner[0] - xyTitle[0]/xyPaper[0], lrCorner[0] - xyTitle[0]/xyPaper[0]), (lrCorner[1]+xyTitle[1]/xyPaper[1], lrCorner[1]), transform = fig.transFigure, color = tc)
            lineCenter2 = lines.Line2D((lrCorner[0],  lrCorner[0] - xyTitle[0]/xyPaper[0]), (lrCorner[1]+0.5*xyTitle[1]/xyPaper[1], lrCorner[1]+0.5*xyTitle[1]/xyPaper[1]), transform = fig.transFigure, color = tc)
            ax.add_artist(lineTop2)
            ax.add_artist(lineLeft2)
            ax.add_artist(lineCenter2)
            #labels
            #column 1 (creator, modifier)
            anchor1 = (lrCorner[0] - xyTitle[0]/xyPaper[0], lrCorner[1]+xyTitle[1]/xyPaper[1])
            fig.text(anchor1[0] + txtPadInch/xyPaper[0], anchor1[1] - txtPadInch/xyPaper[1] -txtHeightInch/xyPaper[1] , 'CREATOR',transform = fig.transFigure,
                                 fontsize=12, horizontalalignment='left', verticalalignment='baseline')
            fig.text(anchor1[0] + txtPadInch/xyPaper[0], anchor1[1] - txtPadInch/xyPaper[1] - 2.0*txtHeightInch/xyPaper[1] , self.authorOrigin, transform = fig.transFigure,
                                 fontsize=12, horizontalalignment='left', verticalalignment='baseline')
            anchor2 = (lrCorner[0] - xyTitle[0]/xyPaper[0], lrCorner[1]+0.5*xyTitle[1]/xyPaper[1])
            fig.text(anchor2[0] + txtPadInch/xyPaper[0], anchor2[1] - txtPadInch/xyPaper[1] -txtHeightInch/xyPaper[1] , 'MODIFIED BY', transform = fig.transFigure,
                                 fontsize=12, horizontalalignment='left', verticalalignment='baseline')
            fig.text(anchor2[0] + txtPadInch/xyPaper[0], anchor2[1] - txtPadInch/xyPaper[1] - 2.0*txtHeightInch/xyPaper[1] , self.authorModify, transform = fig.transFigure,
                                 fontsize=12, horizontalalignment='left', verticalalignment='baseline')
            #column2 (origin date, modify date)
            width3 = 1.5
            anchor3 = (lrCorner[0] - xyTitle[0]/xyPaper[0] + width3/xyPaper[0],  lrCorner[1]+xyTitle[1]/xyPaper[1])
            fig.text(anchor3[0] + txtPadInch/xyPaper[0], anchor3[1] - txtPadInch/xyPaper[1] -txtHeightInch/xyPaper[1] , 'CREATE DATE', transform = fig.transFigure,
                                 fontsize=12, horizontalalignment='left', verticalalignment='baseline')
            
            fig.text(anchor3[0] + txtPadInch/xyPaper[0], anchor3[1] - txtPadInch/xyPaper[1] - 2.0*txtHeightInch/xyPaper[1] , self.dateOrigin, transform = fig.transFigure,
                                 fontsize=12, horizontalalignment='left', verticalalignment='baseline')
            anchor4 = (lrCorner[0] - xyTitle[0]/xyPaper[0] + width3/xyPaper[0], lrCorner[1]+0.5*xyTitle[1]/xyPaper[1])
            fig.text(anchor4[0] + txtPadInch/xyPaper[0], anchor4[1] - txtPadInch/xyPaper[1] -txtHeightInch/xyPaper[1] , 'MODIFY DATE',transform = fig.transFigure,
                                 fontsize=12, horizontalalignment='left', verticalalignment='baseline')
            fig.text(anchor4[0] + txtPadInch/xyPaper[0], anchor4[1] - txtPadInch/xyPaper[1] - 2.0*txtHeightInch/xyPaper[1] , self.dateModify ,transform = fig.transFigure,
                                 fontsize=12, horizontalalignment='left', verticalalignment='baseline')
            #column split
            lineLeft3 = lines.Line2D((anchor3[0], anchor3[0]), (anchor3[1], lrCorner[1]), transform = fig.transFigure, color = tc)
            ax.add_artist(lineLeft3)
            #column3
            width4 = 1.5
            anchor5 = (lrCorner[0] - xyTitle[0]/xyPaper[0] + width3/xyPaper[0] + width4/xyPaper[0],  lrCorner[1]+xyTitle[1]/xyPaper[1])
            fig.text(anchor5[0] + txtPadInch/xyPaper[0], anchor5[1] - txtPadInch/xyPaper[1] -txtHeightInch/xyPaper[1] , 'SCALE',transform = fig.transFigure,
                                 fontsize=12, horizontalalignment='left', verticalalignment='baseline')
            fig.text(anchor5[0] + txtPadInch/xyPaper[0], anchor5[1] - txtPadInch/xyPaper[1] - 2.0*txtHeightInch/xyPaper[1] , self.ratio ,transform = fig.transFigure,
                                 fontsize=12, horizontalalignment='left', verticalalignment='baseline')
            anchor6 = (lrCorner[0] - xyTitle[0]/xyPaper[0] + width3/xyPaper[0] + width4/xyPaper[0], lrCorner[1]+0.5*xyTitle[1]/xyPaper[1])
            fig.text(anchor6[0] + txtPadInch/xyPaper[0], anchor6[1] - txtPadInch/xyPaper[1] -txtHeightInch/xyPaper[1] , 'PERSPECTIVE',transform = fig.transFigure,
                                 fontsize=12, horizontalalignment='left', verticalalignment='baseline')
            fig.text(anchor6[0] + txtPadInch/xyPaper[0], anchor6[1] - txtPadInch/xyPaper[1] - 2.0*txtHeightInch/xyPaper[1] , self.perspective, transform = fig.transFigure,
                                 fontsize=12, horizontalalignment='left', verticalalignment='baseline')
            #column split
            lineLeft4 = lines.Line2D((anchor5[0], anchor5[0]), (anchor5[1], lrCorner[1]), transform = fig.transFigure, color = tc)
            ax.add_artist(lineLeft4)
            #column3
            width5 = 1.5
            anchor6 = (lrCorner[0] - xyTitle[0]/xyPaper[0] + width3/xyPaper[0] + width4/xyPaper[0] + width5/xyPaper[0],  lrCorner[1]+xyTitle[1]/xyPaper[1])
            fig.text(anchor6[0] + txtPadInch/xyPaper[0], anchor6[1] - txtPadInch/xyPaper[1] -txtHeightInch/xyPaper[1] , 'TITLE',transform = fig.transFigure,
                                 fontsize=12, horizontalalignment='left', verticalalignment='baseline')
            fig.text(anchor6[0] + txtPadInch/xyPaper[0], anchor6[1] - txtPadInch/xyPaper[1] - 2.0*txtHeightInch/xyPaper[1] , self.title ,transform = fig.transFigure,
                                 fontsize=12, horizontalalignment='left', verticalalignment='baseline')
            anchor7 = (lrCorner[0] - xyTitle[0]/xyPaper[0] + width3/xyPaper[0] + width4/xyPaper[0] + width5/xyPaper[0], lrCorner[1]+0.5*xyTitle[1]/xyPaper[1])
            fig.text(anchor7[0] + txtPadInch/xyPaper[0], anchor7[1] - txtPadInch/xyPaper[1] -txtHeightInch/xyPaper[1] , 'COMPANY',transform = fig.transFigure,
                                 fontsize=12, horizontalalignment='left', verticalalignment='baseline')
            fig.text(anchor7[0] + txtPadInch/xyPaper[0], anchor7[1] - txtPadInch/xyPaper[1] - 2.0*txtHeightInch/xyPaper[1] , 'OneSolver LLC', transform = fig.transFigure,
                                 fontsize=12, horizontalalignment='left', verticalalignment='baseline')
            #column split
            lineLeft5 = lines.Line2D((anchor6[0], anchor6[0]), (anchor6[1], lrCorner[1]), transform = fig.transFigure, color = tc)
            ax.add_artist(lineLeft5)
        else:
            ax.set_axis_off()
    def clear(self):
        self.shapes = list()
        self.fig.clear()
    def get_cmd(self, content, values):
        from StringIO import StringIO
        from re import sub, compile
        self.__init__() # reset
        if isinstance(content, str):
            lines = StringIO(content)
        elif isinstance(content, file):
            lines = content.readlines()
        subLines = list()
        code = ''
        for line in lines:
            subLine = line
            for desig, value in values.items():
                pattern = compile(r'(\(| |,|\+|\-|\*)(\b%s\b)'%desig)
                subLine = sub(pattern, r'\g<1>%s'%float(value), subLine)
            code += subLine
            subLines.append(subLine.strip())
        return code    
    def load(self, content, values, fmt = 'png'):
        code = self.get_cmd(content, values)
        exec(code)
        self.draw()
    def draw(self):
        self._draw() 
    def save(self, fmt = 'png'):
        savePath = os.path.join(self.path, self.name + '.' + fmt) 
        self.fig.savefig(savePath)
        return savePath
    def _draw(self):
        fig = self.fig
        self.drawSpace = DrawDraftSpace(self)
        self.drawSpace.draw(self)
        ax = fig.gca()
        if self.showGrid:
            ax.grid('on')
        else:
            ax.grid('off')
        if not self.showTick:
            ax.set_axis_off()
            ax.tick_params(axis='both', which='both', left = 'off', right = 'off', bottom='off', top='off',
                            labelbottom='off', labeltop='off', labelleft='off', labelright='off')
        ax.set_aspect('equal')
    def draw_assert(self, msg):
        print msg + ' [y]/n: '
        self.draw()
        imgFile = self.save('jpg')
        imgPath = os.path.join(os.getcwd(), imgFile)    
        import webbrowser
        webbrowser.open(imgPath)
        assert raw_input() in ('y', 'yes', '')
        self.clear()
    def append_shape(self, shape):
        self.shapes.append(shape)
        return self.shapes[-1]
    def tranform(self, cmd, shape, *args):
        shape.transform(cmd, shape, args)