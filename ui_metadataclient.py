# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui_metadataclient.ui'
#
# Created: Thu Nov 13 16:27:35 2014
#      by: PyQt4 UI code generator 4.10.4
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)

class Ui_MetadataClient(object):
    def setupUi(self, MetadataClient):
        MetadataClient.setObjectName(_fromUtf8("MetadataClient"))
        MetadataClient.resize(1029, 571)
        self.wvMetadata = QtWebKit.QWebView(MetadataClient)
        self.wvMetadata.setGeometry(QtCore.QRect(10, 10, 1011, 551))
        self.wvMetadata.setUrl(QtCore.QUrl(_fromUtf8("about:blank")))
        self.wvMetadata.setObjectName(_fromUtf8("wvMetadata"))

        self.retranslateUi(MetadataClient)
        QtCore.QMetaObject.connectSlotsByName(MetadataClient)

    def retranslateUi(self, MetadataClient):
        MetadataClient.setWindowTitle(_translate("MetadataClient", "INSPIRE Atom Client - Metadata Viewer", None))

from PyQt4 import QtWebKit
