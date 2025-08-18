"""
/***************************************************************************
 WfsClientDialog
                                 A QGIS plugin
 WFS 2.0 Client
                             -------------------
        begin                : 2012-05-17
        copyright            : (C) 2012 by Juergen Weichand
        email                : juergen@weichand.de
        website              : http://www.weichand.de
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

from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import *

import os.path

from .ui_metadataclient import Ui_MetadataClient

class MetadataClientDialog(QDialog, Ui_MetadataClient):

    def __init__(self):
        super(MetadataClientDialog, self).__init__(None)
        self.setupUi(self)

        #QtGui.QDialog.__init__(self)
        # Set up the user interface from Designer.
        #self.ui = Ui_MetadataClient()
        #self.ui.setupUi(self)
