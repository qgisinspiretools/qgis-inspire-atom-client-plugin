# -*- coding: utf-8 -*-
"""
/***************************************************************************
 MetadataClientDialog
 A simple metadata viewer that uses QWebEngineView if available,
 otherwise falls back to QTextBrowser (no JS).
 ***************************************************************************/
"""
import os
from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtCore import QUrl

WEBENGINE_AVAILABLE = False
try:
    from qgis.PyQt.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except Exception:
    from qgis.PyQt.QtWidgets import QTextBrowser

UI_PATH = os.path.join(os.path.dirname(__file__), 'ui_metadataclient.ui')

class MetadataClientDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi(UI_PATH, self)

        holder = self.findChild(QtWidgets.QWidget, "webHolder")
        if holder is None:
            holder = QtWidgets.QWidget(self)
            lay = QtWidgets.QVBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(holder)

        if WEBENGINE_AVAILABLE:
            self.viewer = QWebEngineView(self)
        else:
            self.viewer = QTextBrowser(self)

        layout = holder.layout() or QtWidgets.QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.viewer)

    def set_html(self, html: str):
        if WEBENGINE_AVAILABLE:
            self.viewer.setHtml(html, QUrl("about:blank"))
        else:
            self.viewer.setHtml(html)
