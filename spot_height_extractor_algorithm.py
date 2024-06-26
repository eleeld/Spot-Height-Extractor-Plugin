# -*- coding: utf-8 -*-

"""
/***************************************************************************
 SpotHeightExtractor
                                 A QGIS plugin
 This plugin extracts spot heights from an elevation model.
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2024-05-16
        copyright            : (C) 2024 by Elena Field/British Antarctic Survey
        email                : eleeld@bas.ac.uk
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = 'Elena Field/British Antarctic Survey'
__date__ = '2024-05-16'
__copyright__ = '(C) 2024 by Elena Field/British Antarctic Survey'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterVectorLayer,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterNumber,
                       QgsProcessingMultiStepFeedback,
                       QgsProcessingUtils)
import processing


import os
import inspect
from qgis.PyQt.QtGui import QIcon, QKeySequence
from qgis.utils import iface



class SpotHeightExtractor_Algorithm(QgsProcessingAlgorithm):

    def initAlgorithm(self, config):
        self.addParameter(QgsProcessingParameterVectorLayer('coastline_polygon', 'Coastline Polygon', types=[QgsProcessing.TypeVectorPolygon], defaultValue=None))
        # Input of neighbourhood size (circular radius around the centre cell).  
        # Default is 3 (3x3 gridsize)
        # 
        # Please assess cell size and select the radius of the area of interest.  
        self.addParameter(QgsProcessingParameterNumber(
            'neighbour_size',
            'Neighbour Size',
            type=QgsProcessingParameterNumber.Integer,
            minValue=1,
            maxValue=999,
            defaultValue=None))
        
        self.addParameter(QgsProcessingParameterFeatureSink(
            'Spot_heights_extract',
            'spot_heights_extract',
            type=QgsProcessing.TypeVectorAnyGeometry, 
            createByDefault=True,
            defaultValue=None))
        
        self.addParameter(QgsProcessingParameterRasterLayer(
            'dem',
            'DEM',
            defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(5, model_feedback)
        results = {}
        outputs = {}

        # r.neighbors
        alg_params = {
            '-a': False,
            '-c': True,
            'GRASS_RASTER_FORMAT_META': '',
            'GRASS_RASTER_FORMAT_OPT': '',
            'GRASS_REGION_CELLSIZE_PARAMETER': 0,
            'GRASS_REGION_PARAMETER': None,
            'gauss': None,
            'input': parameters['dem'],
            'method': 4,  # maximum
            'quantile': '',
            'selection': None,
            'size': parameters['neighbour_size'],
            'weight': '',
            'output': QgsProcessingUtils.generateTempFilename('rneighbor_result.tif')
        }
        outputs['Rneighbors'] = processing.run('grass7:r.neighbors', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(1)
        
        if feedback.isCanceled():
            return {}
        print("this is the output", outputs['Rneighbors'])


        # Raster Calculator 
        alg_params = {
            'BAND_A': 1,
            'BAND_B': 1,
            'BAND_C': None,
            'BAND_D': None,
            'BAND_E': None,
            'BAND_F': None,
            'EXTENT_OPT': 0,  # Ignore
            'EXTRA': '',
            'FORMULA': 'numpy.where(A==B, A, 0)',
            'INPUT_A': parameters['dem'],
            'INPUT_B': outputs['Rneighbors']['output'],
            'INPUT_C': None,
            'INPUT_D': None,
            'INPUT_E': None,
            'INPUT_F': None,
            'NO_DATA': 0,
            'OPTIONS': '',
            'PROJWIN': None,
            'RTYPE': 5,  # Float32
            'OUTPUT': QgsProcessingUtils.generateTempFilename('rcalc_result.tif')
        }
        outputs['RasterCalculator'] = processing.run('gdal:rastercalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        # r.null
        alg_params = {
            '-c': False,
            '-f': False,
            '-i': False,
            '-n': False,
            '-r': False,
            'GRASS_RASTER_FORMAT_META': '',
            'GRASS_RASTER_FORMAT_OPT': '',
            'GRASS_REGION_CELLSIZE_PARAMETER': 0,
            'GRASS_REGION_PARAMETER': None,
            'map': outputs['RasterCalculator']['OUTPUT'],
            'null': None,
            'setnull': '0',
            'output': QgsProcessingUtils.generateTempFilename('rnull_result.tif')
        }
        outputs['Rnull'] = processing.run('grass7:r.null', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}

        # Raster pixels to points
        alg_params = {
            'FIELD_NAME': 'VALUE',
            'INPUT_RASTER': outputs['Rnull']['output'],
            'RASTER_BAND': 1,
            'OUTPUT': QgsProcessingUtils.generateTempFilename('pixels_to_points_result.gpkg')
        }
        outputs['RasterPixelsToPoints'] = processing.run('native:pixelstopoints', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(4)
        if feedback.isCanceled():
            return {}

        # Extract by location
        alg_params = {
            'INPUT': outputs['RasterPixelsToPoints']['OUTPUT'],
            'INTERSECT': parameters['coastline_polygon'],
            'PREDICATE': [0],  # intersect
            'OUTPUT': parameters['Spot_heights_extract']
        }
        outputs['ExtractByLocation'] = processing.run('native:extractbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Spot_heights_extract'] = outputs['ExtractByLocation']['OUTPUT']
        return results

    def name(self):      
        return 'Spot Height Extractor'

    def displayName(self):        
        return self.tr(self.name())
    
    def shortHelpString(self):
        return self.tr(
            "Derives spot heights from a DEM based on a neighboured size."
            "<h2>Coastline Polygon</h2>"
            "<p>Please select the coastline polygon to mask the output.  This ensures the output contains onland values only."
            "<h2>Neighbour Size</h2>"
            "<h3>r.neighbors</h3>"
            "<p>The GRASS algorithm <a href='https://grass.osgeo.org/grass83/manuals/r.neighbors.html'>r.neighbors</a> looks at each cell in a raster input map and examines the values assigned to the cells in some user-defined ""neighborhood"" around it. It outputs a new raster map layer in which each cell is assigned a value that is some (user-specified) function of the values in that cell's neighborhood. For example, each cell in the output layer might be assigned a value equal to the average of the values appearing in its 3 x 3 cell ""neighborhood"" in the input layer. Note that the centre cell is also included in the calculation.</p>"
            "<h4>Choosing the right Neighbourhood size</h4>"
            "<p>This algorithm uses circular neighbourhoods and determines the cell containing the highest value within each one across the elevation model" 
            "Tool Tip: The size must be an odd integer and represent the length of one of moving window edges in cells. The larger the neighbourhood size, the longer the process will run. It is recommended to start with a low number, e.g. 25 or less.</p>"
            "<br></br>"
            "<div class='code'><pre>"
            "3x3     . X .		5x5	. . X . .	7x7	. . . X . . ."
            "<br></br>"
            "        X O X			. X X X .		. X X X X X ."
            "<br></br>"
            "        . X .			X X O X X		. X X X X X ."
            "<br></br>"
		    "                		            . X X X .		X X X O X X X"
            "<br></br>"
 			"	                                    . . X . .		. X X X X X ."
            "<br></br>"
			"				                        . X X X X X ."
            "<br></br>"
        	"					            . . . X . . ."
            "</div></pre>"
            "<br></br>")


    def group(self):
        return ''

    def groupId(self):
        return ''

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)
    
    def icon(self):
        cmd_folder = os.path.split(inspect.getfile(inspect.currentframe()))[0]
        icon = QIcon(os.path.join(os.path.join(cmd_folder, 'images/icon.png')))
        return icon

    def createInstance(self):
        return SpotHeightExtractor_Algorithm()
