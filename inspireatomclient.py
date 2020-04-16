"""
/***************************************************************************
 InspireAtomClient
                                 A QGIS plugin
 Client for INSPIRE Downloadservices based on ATOM-Feeds
                              -------------------
        begin                : 2012-05-28
        copyright            : (C) 2012 by Juergen Weichand
        email                : juergen@weichand.de
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
# Import the PyQt and QGIS libraries
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from qgis.core import *
from qgis.gui import *

# Initialize Qt resources from file resources.py
from .resources import *
from .inspireatomclientdialog import InspireAtomClientDialog

class InspireAtomClient:

    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface
        self.clickTool = QgsMapToolEmitPoint(self.iface.mapCanvas())

    def initGui(self):
        # Create action that will start plugin configuration
        self.action = QAction(QIcon(":/plugins/inspireatomclient/icon.png"), \
            "INSPIRE Atom Client", self.iface.mainWindow())
        # connect the action to the run method
        self.action.triggered.connect(self.run)

        self.aboutAction=QAction(QIcon(":/plugins/wfsclient/icon.png"), \
            "About", self.iface.mainWindow())
        self.aboutAction.triggered.connect(self.about)

        # Add toolbar button and menu item
        if hasattr( self.iface, "addPluginToWebMenu" ):
            self.iface.addWebToolBarIcon(self.action)
            self.iface.addPluginToWebMenu("&INSPIRE Atom Client", self.action)
            self.iface.addPluginToWebMenu("&INSPIRE Atom Client", self.aboutAction)
        else:
            self.iface.addToolBarIcon(self.action)
            self.iface.addPluginToMenu("&INSPIRE Atom Client", self.action)
            self.iface.addPluginToMenu("&INSPIRE Atom Client", self.aboutAction)


    def unload(self):
        # Remove the plugin menu item and icon
        if hasattr( self.iface, "addPluginToWebMenu" ):
            self.iface.removePluginWebMenu("&INSPIRE Atom Client",self.action)
            self.iface.removePluginWebMenu("&INSPIRE Atom Client",self.aboutAction)
            self.iface.removeWebToolBarIcon(self.action)
        else:
            self.iface.removePluginMenu("&INSPIRE Atom Client",self.action)
            self.iface.removePluginMenu("&INSPIRE Atom Client",self.aboutAction)
            self.iface.removeToolBarIcon(self.action)


    def about(self):
        infoString = "<table><tr><td colspan=\"2\"><b>INSPIRE Atom Client 0.7.0</b></td></tr><tr><td colspan=\"2\">Experimental Plugin</td></tr><tr><td colspan=\"2\"></td></tr><tr><td>Author:</td><td>J&uuml;rgen Weichand</td></tr><tr><td>Mail:</td><td><a href=\"mailto:juergen@weichand.de\">juergen@weichand.de</a></td></tr><tr><td>Website:</td><td><a href=\"http://www.weichand.de\">http://www.weichand.de</a></td></tr><tr></tr><tr><td colspan=\"2\"><b>QGIS 2.x Migration</b></td></tr></tr><tr><td>Author:</td><td>Stefan Ziegler</td></tr></table>"
        QMessageBox.information(self.iface.mainWindow(), "About INSPIRE Atom Client", infoString)

    # run method that performs all the real work
    def run(self):

        # create and show the dialog
        dlg = InspireAtomClientDialog(self)
        # show the dialog
		# Dialog is placed in a corner?
        #dlg.setWindowFlags(Qt.WindowStaysOnTopHint)
        dlg.show()
        result = dlg.exec_()
        # See if OK was pressed
        if result == 1:
            # do something useful (delete the line containing pass and
            # substitute with your code
            pass
