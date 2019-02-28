# -*- coding: utf-8 -*-
"""
/***************************************************************************
 BathCreator
                                 A QGIS plugin
 Helps to create CE-QUAL-W2 Bathymetric file 
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2019-02-04
        git sha              : $Format:%H$
        copyright            : (C) 2019 by Create_Bathymetry Bornstein
        email                : Create_Bathymetryborenst@gmail.com
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

import csv

from PyQt5.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, QVariant
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .create_bathymetry_dialog import BathCreatorDialog
import os.path

#from qgis.core import QgsProject
from qgis.core import (QgsMessageLog, QgsDistanceArea, QgsGeometry,QgsVectorLayer,QgsFeature, QgsProject, QgsField)
from qgis.utils import iface
import processing


class BathCreator:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'BathCreator_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&CE-QUAL-W2_Bathymetry ')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('BathCreator', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/create_bathymetry/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'CE-QUAL-W2 Bathymetry '),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&CE-QUAL-W2_Bathymetry '),
                action)
            self.iface.removeToolBarIcon(action)

    def _calculateAangle(self, feature):
        """Calculates the angle in radians between the start and end point of the vector line"""
        multilinestring = feature.geometry().constGet()
        first_part = multilinestring.geometryN(0)
        first_vertex = first_part.pointN(0)
        last_vertex = first_part.pointN(first_part.numPoints()-1)
        az = first_vertex.azimuth(last_vertex)
        if az < 0:
            az = 360 + az
        pi=22/7
        rad = round(az*(pi/180),2)
        return rad

    def _writeExcel(self, data, width_data, delta, file_name):
        """Write the csv file in the CE-QUAL-W2 format """
        sorted_data = sorted(data, key=lambda k: k['SEGMENT'])
        # populate lists for the first lines of the csv
        segments = [x['SEGMENT'] for x in sorted_data]
        segments.insert(0,'')
        dlx = [x['DLX'] for x in sorted_data]
        dlx.insert(0,'DLX')
        elws = [x['ELWS'] for x in sorted_data]
        elws.insert(0,'ELWS')
        phi = [x['PHI0'] for x in sorted_data]
        phi.insert(0,'PHI0')
        fric = [x['FRIC'] for x in sorted_data]
        fric.insert(0,'FRIC')
        l = ['LAYERH']
        for i in sorted_data: # Add the empty cells as number of segments
            l.append('')
        l.append('K')
        l.append('ELEV')
        for e in width_data: #Insert the first and last rows of "0"
            e.insert(0,0)
            e.append(0)
        with open(file_name, 'w') as csvfile:
            f = csv.writer(csvfile, delimiter=',')
            f.writerow(["$"])
            f.writerow(segments)
            f.writerow(dlx)
            f.writerow(elws)
            f.writerow(phi)
            f.writerow(fric)
            f.writerow(l)
            i = 1
            for row in zip(*width_data):
                r = row[ : 0] + (delta,) + row[0: ] # add the delta value column A
                r += (i,)  # add the K value
                f.writerow(r)
                i += 1

    def _calcVolumes(self, histograms, delta, cell_size):
        """Calculate the volume of each delta for each segment"""
        fields_list = histograms['OUTPUT'].fields().names()
        fields_list.pop(0) # remove "SEGMENT" field.
        heights_list = [float(i) for i in fields_list] # from string to float
        min_h = min(heights_list)
        QgsMessageLog.logMessage( 'Starting to calculate volumes\nMin height is: ' + str(min_h), tag="Create_Bathymetry")
        QgsMessageLog.logMessage( 'Delta is: ' + str(delta), tag="Create_Bathymetry")
        volumes = []
        features = histograms['OUTPUT'].getFeatures()
        for feat in features: # iterate over the segments
            QgsMessageLog.logMessage( 'starting segment: ' + str(feat['SEGMENT']), tag="Create_Bathymetry")
            volume = []
            up_limit = min_h + delta
            tmp_len = 0
            num_of_cells = 0
            for h in heights_list: # This list is already sorted
                h_string = str(h)
                if h == int(h):  # The table represent 15.0 as 15
                    h_string = str(int(h))
                num_of_cells += feat[h_string] # Calculate number of cells for populating the next delta 
                if h < up_limit:
                    tmp_len += (up_limit - h)*feat[h_string] # This is the overall height
                else:
                    volume.insert(0,tmp_len*cell_size) # finished with previous delta
                    up_limit += delta  # setup the next delta
                    while up_limit <= h : # if the next delta has no data in it, still add the volume of the one before
                        volume.insert(0,tmp_len*cell_size)
                        up_limit += delta
                    tmp_len = (num_of_cells - feat[h_string])*delta # add the cells from the previous deltas
                    tmp_len += (up_limit - h)*feat[h_string] # populate the current pixel value
            volume.insert(0,tmp_len*cell_size) # append the last volume clculations
            volumes.append({'SEGMENT' : int(feat['SEGMENT']), 'data' : volume}) # append to all features list
        QgsMessageLog.logMessage( 'Volume clculation summary: ' + str(volumes), tag="Create_Bathymetry")
        return(volumes)    

    def _calcWidth(self, data, volume_data, delta):
        """According to delta and length get segment width from the volume """
        k = len(volume_data[0]['data'])
        for i in range(len(data)):
            for x in range(k):
                length = data[i]['DLX']
                volume_data[i]['data'][x] = round((volume_data[i]['data'][x]/length)/delta,2)
        QgsMessageLog.logMessage( 'Calculated width summary: ' + str(volume_data), tag="Create_Bathymetry")
        return volume_data

    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            self.dlg = BathCreatorDialog()

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            BUFFER_DISTANCE = 15     #TBD replace with GUI
            BUFFER_SEGMENTS = 2      #TBD replace with GUI with default
            LAYER_CRS = 'Polygon?crs=epsg:2039'       #TBD replace with GUI
            POLYGON_LAYER_NAME = 'foo'        #TBD replace with GUI
            DEM_LAYER_NAME = 'LIDAR'        #TBD replace with GUI
            DEM_BAND = '1'        #TBD replace with GUI with default
            DELTA = 0.5         #TBD replace with GUI with default
            OUTPUT_FILE_NAME = '/home/yoav/out.csv'
            layer = iface.activeLayer()    #TBD replace with GUI
            features = layer.getFeatures()
            d = QgsDistanceArea()
            data = []
            #buffer_layer = []
            for feat in features:
                data_dic = {}
                
                # Read fields from the vector line
                data_dic['SEGMENT']=feat["SEGMENT"]
                data_dic['ELWS']=feat["ELWS"]
                data_dic['FRIC']=feat["FRIC"]
                
                # Get vector line length
                data_dic['DLX']=round(d.measureLength(feat.geometry()),2)
                
                # Calculate line angle
                data_dic['PHI0'] = self._calculateAangle(feat)
                
                data.append(data_dic)
            QgsMessageLog.logMessage( 'Data collected from features: ' + str(data), tag="Create_Bathymetry")
            
            # Calculate volume by the cells value in each buffer
            histograms = processing.run("native:zonalhistogram", {'INPUT_RASTER' : DEM_LAYER_NAME, 'RASTER_BAND' : DEM_BAND, 'INPUT_VECTOR' : POLYGON_LAYER_NAME, 'COLUMN_PREFIX': '', 'OUTPUT' : 'memory:'})
            dem = QgsProject.instance().mapLayersByName(DEM_LAYER_NAME)
            cell_size = dem[0].rasterUnitsPerPixelX()*dem[0].rasterUnitsPerPixelY() # get cell size m^2
            volume_data = self._calcVolumes(histograms, DELTA, cell_size) # output is list of dic
            
            # Calculate width
            width_data = self._calcWidth(data, volume_data, DELTA)

            # Get the border segments into the data
            sorted_width = sorted(width_data, key=lambda k: k['SEGMENT']) 
            n = len(sorted_width[0]['data']) # number of layers 
            sorted_width.insert(0,{'SEGMENT': 1, 'data':[0]*n}) # insert first empty segment
            data.append({'SEGMENT': 1, 'ELWS': '', 'FRIC' : '', 'DLX':'', 'PHI0':''})
            seq = [x['SEGMENT'] for x in sorted_width]    
            for i in range(max(seq)): #Iterate over all segments and add the missing border empty segments
                if i+1 != sorted_width[i]['SEGMENT']:
                    sorted_width.insert(i,{'SEGMENT': i+1, 'data':[0]*n})
                    data.append({'SEGMENT': i+1, 'ELWS': '', 'FRIC' : '', 'DLX':'', 'PHI0':''})
                    sorted_width.insert(i+1,{'SEGMENT': i+2, 'data':[0]*n})
                    data.append({'SEGMENT': i+2, 'ELWS': '', 'FRIC' : '', 'DLX':'', 'PHI0':''})
            sorted_width.insert(i+1,{'SEGMENT': i+2, 'data':[0]*n})
            data.append({'SEGMENT': i+2, 'ELWS': '', 'FRIC' : '', 'DLX':'', 'PHI0':''}) # insert last empty segment
            
            regular_list = [] # simplify the data structure before writing the csv
            for d in range(len(sorted_width)):
                regular_list.append(sorted_width[d]['data'])
            self._writeExcel(data, regular_list, DELTA, OUTPUT_FILE_NAME)
            QgsMessageLog.logMessage( message='Execution finished ', tag="Create_Bathymetry")

