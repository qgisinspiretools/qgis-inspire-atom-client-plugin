"""
/***************************************************************************
 InspireAtomClientDialog
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
from PyQt4 import uic
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtNetwork import QHttp
from PyQt4 import QtXml, QtXmlPatterns
from qgis.core import *
from xml.etree import ElementTree
from urlparse import urljoin
from urlparse import urlparse
import urllib2 
import string
import random
import tempfile
import os
import os.path
import inspireatomlib
from metadataclientdialog import MetadataClientDialog

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'ui_inspireatomclient.ui'))

plugin_path = os.path.abspath(os.path.dirname(__file__))

class InspireAtomClientDialog(QDialog, FORM_CLASS):
    def __init__(self, iface, parent=None):
        #QDialog.__init__(self)
        super(InspireAtomClientDialog, self).__init__(parent)
        #self.parent = parent
        #self = Ui_InspireAtomClient()
        self.setupUi(self)

        self.settings = QSettings()
