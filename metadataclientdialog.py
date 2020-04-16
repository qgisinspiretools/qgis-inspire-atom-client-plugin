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

from PyQt5 import uic
from PyQt5.QtWidgets import *

import os.path

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'ui_metadataclient.ui'))

class MetadataClientDialog(QDialog, FORM_CLASS):

    def __init__(self):
        super(MetadataClientDialog, self).__init__(None)
        self.setupUi(self)

        #QtGui.QDialog.__init__(self)
        # Set up the user interface from Designer.
        #self.ui = Ui_MetadataClient()
        #self.ui.setupUi(self)
