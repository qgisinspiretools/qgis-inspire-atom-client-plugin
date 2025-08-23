# -*- coding: utf-8 -*-
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
"""
import os
from qgis.PyQt import QtWidgets, uic

UI_PATH = os.path.join(os.path.dirname(__file__), 'ui_metadataclient.ui')

class MetadataClientDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi(UI_PATH, self)
