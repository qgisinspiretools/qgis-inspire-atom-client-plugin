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

from PyQt4 import QtCore, QtGui
from PyQt4.QtNetwork import QHttp
from PyQt4 import QtXml, QtXmlPatterns
from ui_inspireatomclient import Ui_InspireAtomClient
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

plugin_path = os.path.abspath(os.path.dirname(__file__))

class InspireAtomClientDialog(QtGui.QDialog):
    
    def __init__(self, parent):
        QtGui.QDialog.__init__(self)
        # Set up the user interface from Designer.
        self.parent = parent
        self.ui = Ui_InspireAtomClient()
        self.ui.setupUi(self)

        self.settings = QtCore.QSettings()
        self.init_variables()

        self.ui.txtUsername.setVisible(False)
        self.ui.txtPassword.setVisible(False)
        self.ui.lblUsername.setVisible(False)
        self.ui.lblPassword.setVisible(False)

        # Connect signals
        QtCore.QObject.connect(self.ui.cmdGetFeed, QtCore.SIGNAL("clicked()"), self.get_service_feed)
        QtCore.QObject.connect(self.ui.cmdSelectDataset, QtCore.SIGNAL("clicked()"), self.select_dataset_feed_byclick)
        QtCore.QObject.connect(self.ui.cmdDownload, QtCore.SIGNAL("clicked()"), self.download_files)
        QtCore.QObject.connect(self.ui.cmdMetadata, QtCore.SIGNAL("clicked()"), self.show_metadata)
        QtCore.QObject.connect(self.ui.chkAuthentication, QtCore.SIGNAL("clicked()"), self.update_authentication)
        QtCore.QObject.connect(self.ui.cmbDatasets, QtCore.SIGNAL("currentIndexChanged(int)"), self.select_dataset_feed_bylist)
        QtCore.QObject.connect(self.ui.cmbDatasetRepresentations, QtCore.SIGNAL("currentIndexChanged(int)"), self.update_lw_files)

    def init_variables(self):
        self.onlineresource = ""
        self.layername = ""
        self.datasetindexes = {}       
        self.datasetrepresentations = {}
        self.currentfile = 0
        self.currentmetadata = ""
        
    
    """
    ############################################################################################################################
    # ATOM Feed
    ############################################################################################################################
    """

    # request and handle "Service Feed" - Get Metadata | cmdGetFeed Signal
    def get_service_feed(self):
        self.init_variables()
        try:
            self.onlineresource = self.ui.txtUrl.text().trimmed()
            request = unicode(self.onlineresource)
            if self.ui.chkAuthentication.isChecked():
                self.setup_urllib2(request, self.ui.txtUsername.text().trimmed(), self.ui.txtPassword.text().trimmed())
            else:
                self.setup_urllib2(request, "", "")
            response = urllib2.urlopen(request, None, 10)
            buf = response.read()
            #QtGui.QMessageBox.information(self, "Debug", buf)
        except urllib2.HTTPError, e:  
            QtGui.QMessageBox.critical(self, "HTTP Error", "HTTP Error: {0}".format(e.code))
            if e.code == 401:
                self.ui.chkAuthentication.setChecked(True)
                self.update_authentication()
        except urllib2.URLError, e:
            QtGui.QMessageBox.critical(self, "URL Error", "URL Error: {0}".format(e.reason))
        else:
            layername="INSPIRE_DLS#{0}".format(''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(6)))
            tmpfile = self.save_tempfile("{0}.xml".format(layername), buf)
            vlayer = QgsVectorLayer(tmpfile, layername, "ogr")
            vlayer.setProviderEncoding("UTF-8") #Ignore System Encoding --> TODO: Use XML-Header
            if not vlayer.isValid():
                QtGui.QMessageBox.critical(self, "QGIS-Layer Error", "Response is not a valid QGIS-Layer!")
            else: 
                self.add_layer(vlayer)
                self.layername = vlayer.name()
                self.parent.iface.zoomToActiveLayer()
                self.clear_frame()
                self.update_cmbDatasets()
                
                # Lock
                self.ui.cmdGetFeed.setEnabled(False)
                self.ui.chkAuthentication.setEnabled(False)
                self.ui.txtUrl.setEnabled(False)
                self.ui.txtUsername.setEnabled(False)
                self.ui.txtPassword.setEnabled(False)


    # update cmbDatasets
    def update_cmbDatasets(self):
        self.is_cmbDatasets_locked = True
        self.ui.cmbDatasets.clear()
        self.ui.cmdSelectDataset.setEnabled(False)
        # get currentLayer and dataProvider
        cLayer = self.parent.iface.mapCanvas().currentLayer()
        if cLayer.type() != QgsMapLayer.VectorLayer:
            return 
        selectList = []
        provider = cLayer.dataProvider()
        feat = QgsFeature()
        # create the select statement
        provider.select(provider.attributeIndexes())
        num_features_validated = 0
        num_features_not_validated = 0
        dataset_index = 0
        while provider.nextFeature(feat):
            map = feat.attributeMap()                
            if self.validate_feature(map, provider):
                num_features_validated += 1
                self.ui.cmbDatasets.addItem(unicode(map[provider.fieldNameIndex("title")].toString()), unicode(map[provider.fieldNameIndex("title")].toString()))                
                self.datasetindexes[unicode(map[provider.fieldNameIndex("title")].toString())] = dataset_index
                dataset_index += 1
            else:
                num_features_not_validated += 1

        if num_features_validated == 0:
            QtGui.QMessageBox.critical(self, "INSPIRE Service Feed Error", "Unable to process INSPIRE Service Feed!")
        else:        
            self.ui.cmdSelectDataset.setEnabled(True)
            self.is_cmbDatasets_locked = False
            self.select_dataset_feed_bylist()
 

    # check "Service Feed Entry" for Identifier, Title, Dataset Feed Link
    def validate_feature(self, map, provider):
        try:
            # Dataset Identifier 
            if provider.fieldNameIndex("inspire_dls_spatial_dataset_identifier_code") > -1:
                if len(unicode(map[provider.fieldNameIndex("inspire_dls_spatial_dataset_identifier_code")].toString())) > 0:                
                    # Dataset Title
                    if provider.fieldNameIndex("title") > -1:
                       if len(unicode(map[provider.fieldNameIndex("title")].toString())) > 0:
                           # Datasetfeed Link
                           for key, value in map.items():                        
                               if value.toString() == "alternate":
                                   fieldname = provider.fields()[key].name().replace("rel", "href")
                                   if provider.fieldNameIndex(fieldname) > -1:                                       
                                       return True 
            return False 
        except KeyError, e:
            return False


    # select "Dataset Feed" | cmbDatasets "currentIndexChanged(int)" Signal
    def select_dataset_feed_bylist(self):
        if self.is_cmbDatasets_locked:
            return
        self.clear_frame()
        self.ui.lblMessage.setText("")
        cLayer = self.parent.iface.mapCanvas().currentLayer()
        if not cLayer.name() == self.layername:
            QtGui.QMessageBox.critical(self, "QGIS-Layer Error", "Selected Layer isn't the INSPIRE Service Feed!")
            return 
        if cLayer.type() != QgsMapLayer.VectorLayer:
            return 
        selectList = []
        provider = cLayer.dataProvider()
        feat = QgsFeature()
        # create the select statement
        provider.select(provider.attributeIndexes())
        while provider.nextFeature(feat):            
            map = feat.attributeMap()               
            if len(self.ui.cmbDatasets.currentText()) > 0:
                try:
                    if unicode(map[provider.fieldNameIndex("title")].toString()) == unicode(self.ui.cmbDatasets.currentText()):
                        self.handle_dataset_selection(map, provider)
                        selectList.append(feat.id())
                except KeyError, e:
                    self.ui.lblMessage.setText("") # TODO: exception handling

        # make the actual selection
        cLayer.setSelectedFeatures(selectList)


    # select "Dataset Feed" | cmdSelectDataset Signal
    def select_dataset_feed_byclick(self):
        self.clear_frame()
        self.ui.lblMessage.setText("")
        # http://www.qgisworkshop.org/html/workshop/plugins_tutorial.html
        result = QtCore.QObject.connect(self.parent.clickTool, QtCore.SIGNAL("canvasClicked(const QgsPoint &, Qt::MouseButton)"), self.select_dataset_feed_byclick_procedure)
        self.parent.iface.mapCanvas().setMapTool(self.parent.clickTool)


    # select "Dataset Feed" | Signal ("Click")
    def select_dataset_feed_byclick_procedure(self, point, button):
        self.clear_frame()
        # setup the provider select to filter results based on a rectangle
        pntGeom = QgsGeometry.fromPoint(point)  
        # scale-dependent buffer of 2 pixels-worth of map units
        pntBuff = pntGeom.buffer( (self.parent.iface.mapCanvas().mapUnitsPerPixel() * 2), 0) 
        rect = pntBuff.boundingBox()
        # get currentLayer and dataProvider
        cLayer = self.parent.iface.mapCanvas().currentLayer()
        if not cLayer.name() == self.layername:
            QtGui.QMessageBox.critical(self, "QGIS-Layer Error", "Selected Layer isn't the INSPIRE Service Feed!")
            result = QtCore.QObject.disconnect(self.parent.clickTool, QtCore.SIGNAL("canvasClicked(const QgsPoint &, Qt::MouseButton)"), self.select_dataset_feed_byclick_procedure)
            self.parent.iface.mapCanvas().unsetMapTool(self.parent.clickTool)
            return 
        if cLayer.type() != QgsMapLayer.VectorLayer:
            return 
        selectList = []
        provider = cLayer.dataProvider()
        feat = QgsFeature()
        # create the select statement
        provider.select(provider.attributeIndexes(), rect)
        while provider.nextFeature(feat):
            # if the feat geom returned from the selection intersects our point then put it in a list
            if feat.geometry().intersects(pntGeom):
                selectList.append(feat.id())
                map = feat.attributeMap() 
                self.handle_dataset_selection(map, provider)
                break 
                    
        # make the actual selection
        cLayer.setSelectedFeatures(selectList)
        result = QtCore.QObject.disconnect(self.parent.clickTool, QtCore.SIGNAL("canvasClicked(const QgsPoint &, Qt::MouseButton)"), self.select_dataset_feed_byclick_procedure)
        self.parent.iface.mapCanvas().unsetMapTool(self.parent.clickTool)


    # handle selection | selected by list or by click
    def handle_dataset_selection(self, map, provider):
        if not self.validate_feature(map, provider):
            QtGui.QMessageBox.critical(self, "INSPIRE Service Feed Entry Error", "Unable to process selected INSPIRE Service Feed Entry!")
            return

        dataset = inspireatomlib.Dataset(unicode(map[provider.fieldNameIndex("inspire_dls_spatial_dataset_identifier_code")].toString()))
        dataset.setTitle(unicode(map[provider.fieldNameIndex("title")].toString()))

        if provider.fieldNameIndex("summary") > -1:
            dataset.setSummary(unicode(map[provider.fieldNameIndex("summary")].toString()))                    
        if provider.fieldNameIndex("rights") > -1:
            dataset.setRights(unicode(map[provider.fieldNameIndex("rights")].toString()))
        
        for key, value in map.items():                        
            if value.toString() == "alternate":
                fieldname = provider.fields()[key].name().replace("rel", "href")
                if provider.fieldNameIndex(fieldname) > -1:
                    linksubfeed = unicode(map[provider.fieldNameIndex(fieldname)].toString())
                    dataset.setLinkSubfeed(self.buildurl(linksubfeed))
            if value.toString() == "describedby":
                fieldname = provider.fields()[key].name().replace("rel", "href")
                if provider.fieldNameIndex(fieldname) > -1:
                    linkmetadata = unicode(map[provider.fieldNameIndex(fieldname)].toString())
                    dataset.setLinkMetadata(self.buildurl(linkmetadata))
        
        self.ui.cmbDatasets.setCurrentIndex(self.datasetindexes[dataset.getTitle()])
        self.ui.cmbDatasetRepresentations.clear()
        self.ui.frmDataset.setEnabled(True)
        self.ui.lblTitle.setText(dataset.getTitle())
        self.ui.txtSummary.setPlainText(dataset.getSummary())
        self.ui.txtId.setPlainText(dataset.getId())
        self.ui.txtRights.setPlainText(dataset.getRights())                    
        
        if dataset.getLinkMetadata():
            if len(dataset.getLinkMetadata()) > 0:
                self.ui.cmdMetadata.setEnabled(True)
                self.currentmetadata = dataset.getLinkMetadata()
            else: 
                self.ui.cmdMetadata.setEnabled(False)
                self.currentmetadata = ""
        else:
            self.ui.cmdMetadata.setEnabled(False)
            self.currentmetadata = ""

        self.receive_dataset_representations(dataset.getLinkSubfeed())


    # request and handle "Dataset Feed" (dataset representations)
    def receive_dataset_representations(self, subfeedurl): 
        try:
            if self.ui.chkAuthentication.isChecked():
                self.setup_urllib2(subfeedurl, self.ui.txtUsername.text().trimmed(), self.ui.txtPassword.text().trimmed())
            else:
                self.setup_urllib2(subfeedurl, "", "")
            response = urllib2.urlopen(subfeedurl, None, 10)
            buf = response.read()
        except urllib2.HTTPError, e:  
            QtGui.QMessageBox.critical(self, "HTTP Error", "HTTP Error: {0}".format(e.code))
        except urllib2.URLError, e:
            QtGui.QMessageBox.critical(self, "URL Error", "URL Error: {0}".format(e.reason))
        else:
            self.datasetrepresentations = {}
            root = ElementTree.fromstring(buf)
            # ATOM Namespace
            namespace = "{http://www.w3.org/2005/Atom}"
            # check correct Rootelement 
            if root.tag == "{0}feed".format(namespace):       
                for target in root.findall("{0}entry".format(namespace)):
                    idvalue = ""
                    for id in target.findall("{0}id".format(namespace)):
                        idvalue = id.text
                    if (idvalue):
                        datasetrepresentation = inspireatomlib.DatasetRepresentation(idvalue)
                        for title in target.findall("{0}title".format(namespace)):
                            datasetrepresentation.setTitle(title.text)
                        files = []
                        for link in target.findall("{0}link".format(namespace)):
                            if link.get("rel") == "alternate":
                                files.append(self.buildurl(link.get("href")))                           
                            if link.get("rel") == "section":
                                files.append(self.buildurl(link.get("href")))
                        datasetrepresentation.setFiles(files)
                        self.datasetrepresentations[QtCore.QString(datasetrepresentation.getTitle())] = datasetrepresentation
                        self.ui.cmbDatasetRepresentations.addItem(datasetrepresentation.getTitle(), datasetrepresentation.getTitle())
                        self.ui.cmdDownload.setEnabled(True)
            
            else:
                QtGui.QMessageBox.critical(self, "INSPIRE Dataset Feed Error", "Unable to process INSPIRE Dataset Feed!") 

    # update ListWidget | cmbDatasetRepresentations "currentIndexChanged(int)" Signal
    def update_lw_files(self):
        self.ui.lwFiles.clear()
        if len(self.ui.cmbDatasetRepresentations.currentText()) > 0:
            datasetrepresentation = self.datasetrepresentations[self.ui.cmbDatasetRepresentations.currentText()]
            for file in datasetrepresentation.getFiles():                
                self.ui.lwFiles.addItem(file)

    def clear_frame(self):
        self.ui.lblTitle.setText("Title")
        self.ui.txtSummary.setPlainText("")
        self.ui.txtId.setPlainText("")
        self.ui.txtRights.setPlainText("")
        self.ui.cmbDatasetRepresentations.clear()
        self.ui.lwFiles.clear()
        self.ui.cmdDownload.setEnabled(False)
        self.ui.cmdMetadata.setEnabled(False)
        self.ui.frmDataset.setEnabled(False)

    def show_metadata(self):
        if len(self.currentmetadata) > 0:
            xslfilename = os.path.join(plugin_path, "iso19139jw.xsl")
            html = self.xsl_transform(self.currentmetadata, xslfilename)
       
            if html:
                # create and show the dialog
                dlg = MetadataClientDialog()
                dlg.ui.wvMetadata.setHtml(html)
                dlg.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
                # show the dialog
                dlg.show()
                result = dlg.exec_()
                # See if OK was pressed
                if result == 1:
                    # do something useful (delete the line containing pass and
                    # substitute with your code
                    pass
            else:
                QtGui.QMessageBox.critical(self, "Metadata Error", "Unable to read the Metadata")


    # UI: Update Main-Frame / Enable|Disable Authentication
    def update_authentication(self):
        if not self.ui.chkAuthentication.isChecked():
            self.ui.frmMain.setGeometry(QtCore.QRect(0,90,511,631))
            self.ui.txtUsername.setVisible(False)
            self.ui.txtPassword.setVisible(False)
            self.ui.lblUsername.setVisible(False)
            self.ui.lblPassword.setVisible(False)
            self.resize(520, 725)
        else:
            self.ui.frmMain.setGeometry(QtCore.QRect(0,150,511,631))
            self.ui.txtUsername.setVisible(True)
            self.ui.txtPassword.setVisible(True)
            self.ui.lblUsername.setVisible(True)
            self.ui.lblPassword.setVisible(True)
            self.resize(520, 781)

    """
    ############################################################################################################################
    # Download
    ############################################################################################################################
    """
   
    # execute download procedure | cmdDownload Signal
    def download_files(self):
        self.ui.lblMessage.setText("")

        self.httpGetId = 0
        self.httpRequestAborted = False
        self.downloadedfiles = []

        self.setup_qhttp()
        self.http.requestFinished.connect(self.httpRequestFinished)
        self.http.dataReadProgress.connect(self.updateDataReadProgress)
        self.http.responseHeaderReceived.connect(self.readResponseHeader)
        if self.ui.chkAuthentication.isChecked():
            self.http.authenticationRequired.connect(self.authenticationRequired)

        self.download_next()

    # download next file (after finishing the last one)
    def download_next(self):
       datasetrepresentation = self.datasetrepresentations[self.ui.cmbDatasetRepresentations.currentText()]
       if self.currentfile < len(datasetrepresentation.getFiles()):
           self.ui.cmdGetFeed.setEnabled(False)
           self.ui.cmdDownload.setEnabled(False)
           self.ui.cmdSelectDataset.setEnabled(False)
           self.ui.cmdMetadata.setEnabled(False)
           self.ui.cmbDatasets.setEnabled(False)
           self.ui.cmbDatasetRepresentations.setEnabled(False)
           self.ui.lwFiles.setItemSelected(self.ui.lwFiles.item(self.currentfile), True)
           self.ui.cmdDownload.setText("Downloading {0}/{1}".format(self.currentfile + 1, len(datasetrepresentation.getFiles())))
           file = datasetrepresentation.getFiles()[self.currentfile]
           filename=self.buildfilename(file)
           self.downloadFile(file, self.get_temppath(filename))
           self.currentfile += 1
       else:
           self.load_downloaded_files()
           self.reset_ui_download()

    # try to load downloaded files as QGIS-Layer(s)
    def load_downloaded_files(self):
        failed = []
        successful = []
        for file in self.downloadedfiles:
            vlayer = QgsVectorLayer(file, file, "ogr")            
            if not vlayer.isValid():
                #fileInfo = QtCore.QFileInfo(file)
                #baseName = fileInfo.baseName()
                rlayer = QgsRasterLayer(file, file)   
                if not rlayer.isValid():
                    failed.append(file)
                    self.ui.lblMessage.setText("")
                else:
                    self.add_layer(rlayer)
                    self.parent.iface.zoomToActiveLayer()
                    successful.append(file)
            else: 
                self.ui.lblMessage.setText("")
                self.add_layer(vlayer)
                self.parent.iface.zoomToActiveLayer()
                successful.append(file)
        
        message = ""
        if len(successful) > 0:
            message += "<p><b>Successfully loaded:</b><br />"
            for file in successful:
                message += file + "<br />"
            message += "</p>"        
        if len(failed) > 0:
            message += "<p><b>Failed to load:</b><br />"
            for file in failed:
                message += file + "<br />"
            message += "</p>"
        QtGui.QMessageBox.information(self, "Import Status", message)

    
    def reset_ui_download(self):
        self.ui.cmdDownload.setText("Download")
        self.ui.cmdDownload.setEnabled(True)
        self.ui.cmdSelectDataset.setEnabled(True)
        self.ui.cmbDatasets.setEnabled(True)
        self.ui.cmbDatasetRepresentations.setEnabled(True)
        self.currentfile = 0
        if len(self.currentmetadata) > 0:
            self.ui.cmdMetadata.setEnabled(True)


    def add_layer(self, layer):
        # QGIS 1.8, 1.9
        if hasattr(QgsMapLayerRegistry.instance(), "addMapLayers"):
            QgsMapLayerRegistry.instance().addMapLayers([layer])
        # QGIS 1.7
        else:
            QgsMapLayerRegistry.instance().addMapLayer(layer)

    """
    ############################################################################################################################
    # UTIL
    ############################################################################################################################
    """

    def get_temppath(self, filename):
        tmpdir = os.path.join(tempfile.gettempdir(),'inspireatomclient')
        if not os.path.exists(tmpdir):
            os.makedirs(tmpdir)
        tmpfile= os.path.join(tmpdir, filename)
        return tmpfile


    def save_tempfile(self, filename, content):
        tmpdir = os.path.join(tempfile.gettempdir(),'inspireatomclient')
        if not os.path.exists(tmpdir):
            os.makedirs(tmpdir)
        tmpfile= os.path.join(tmpdir, filename)
        fobj=open(tmpfile,'wb')
        fobj.write(content)
        fobj.close()  
        return tmpfile


    # Receive Proxy from QGIS-Settings
    def getProxy(self):
        if self.settings.value("/proxy/proxyEnabled").toString() == "true":
           proxy = "{0}:{1}".format(self.settings.value("/proxy/proxyHost").toString(), self.settings.value("/proxy/proxyPort").toString())
           if proxy.startswith("http://"):
               return proxy
           else:
               return "http://" + proxy
        else: 
            return ""


    # Setup urllib2 (Proxy)
    def setup_urllib2(self, request, username, password):
        # with Authentication
        if username and len(username) > 0:
            if password and len(password) > 0:
                password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
                password_mgr.add_password(None, request, username, password)
                auth_handler = urllib2.HTTPBasicAuthHandler(password_mgr)

                if not self.getProxy() == "":
                    proxy_handler = urllib2.ProxyHandler({"http" : self.getProxy()})
                else:
                    proxy_handler = urllib2.ProxyHandler({})
                opener = urllib2.build_opener(proxy_handler, auth_handler)
                urllib2.install_opener(opener)

        # without Authentication
        else:
            if not self.getProxy() == "":
                proxy_handler = urllib2.ProxyHandler({"http" : self.getProxy()})
            else:
                proxy_handler = urllib2.ProxyHandler({})
            opener = urllib2.build_opener(proxy_handler)
            urllib2.install_opener(opener)


    # Setup Qhttp (Proxy)
    def setup_qhttp(self):
        self.http = QHttp(self)
        if not self.getProxy() == "":
            self.http.setProxy(QgsNetworkAccessManager.instance().fallbackProxy()) # Proxy       


    # Convert relative links to absolute link
    def buildurl(self, urlfragment):
        if not urlfragment.startswith("http"):
            return urljoin(unicode(self.onlineresource), urlfragment)
        return urlfragment


    # Build filename for downloaded file
    def buildfilename(self, url):
        parseresult = urlparse(url)
        if len(parseresult.query) == 0:
            path = parseresult.path
            filename = path[path.rfind("/") + 1:]
        else:
            # TODO: use Mime-Type
            extension="ext"
            if url.lower().find("tif") > -1:
                extension="tiff"
            elif url.lower().find("gml") > -1:
                extension="gml"
            elif url.lower().find("kml") > -1:
                extension="kml"

            elif url.lower().find("wfs") > -1:
                extension="gml"
            elif url.lower().find("wms") > -1:
                extension="tiff"
            elif url.lower().find("wcs") > -1:
                extension="tiff"
            filename="{0}.{1}".format(''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(6)), extension)
        return filename


    # XSL Transformation
    def xsl_transform(self, url, xslfilename):
        try:
            self.setup_urllib2(url, "", "")
            response = urllib2.urlopen(url, None, 10)
            buf = response.read()
        except urllib2.HTTPError, e:  
            QtGui.QMessageBox.critical(self, "HTTP Error", "HTTP Error: {0}".format(e.code))
        except urllib2.URLError, e:
            QtGui.QMessageBox.critical(self, "URL Error", "URL Error: {0}".format(e.reason))
        else:
           # load xslt
           xslt_file = QtCore.QFile(xslfilename)
           xslt_file.open(QtCore.QIODevice.ReadOnly)
           xslt = QtCore.QString(xslt_file.readAll())
           xslt_file.close()
 
           # load xml
           xml_source = QtCore.QString.fromUtf8(buf)

           # xslt
           qry = QtXmlPatterns.QXmlQuery(QtXmlPatterns.QXmlQuery.XSLT20)
           qry.setFocus(xml_source)
           qry.setQuery(xslt)

           array = QtCore.QByteArray()
           buf = QtCore.QBuffer(array)
           buf.open(QtCore.QIODevice.WriteOnly)
           qry.evaluateTo(buf)
           xml_target = QtCore.QString.fromUtf8(array)
           return xml_target


    #############################################################################################################
    # QHttp GetFeature-Request - http://stackoverflow.com/questions/6852038/threading-in-pyqt4
    #############################################################################################################

    def downloadFile(self, httplink, fileName):
        #self.lock_ui()
        url = QtCore.QUrl(httplink)

        if QtCore.QFile.exists(fileName):
            QtCore.QFile.remove(fileName)

        self.outFile = QtCore.QFile(fileName)
        if not self.outFile.open(QtCore .QIODevice.WriteOnly):
            QtGui.QMessageBox.critical(self, "Error", "Unable to save the file %s: %s." % (fileName, self.outFile.errorString()))
            self.outFile = None
            return

        mode = QHttp.ConnectionModeHttp
        port = url.port()
        if port == -1:
            port = 0
        self.http.setHost(url.host(), mode, port)
        self.httpRequestAborted = False
        # Download the file.
        self.ui.progressBar.setVisible(True)
        self.httpGetId = self.http.get(url.toString(), self.outFile)


    # currently unused
    def cancelDownload(self):
        self.httpRequestAborted = True
        self.http.abort()
        self.close()

        self.ui.progressBar.setMaximum(1)
        self.ui.progressBar.setValue(0)
        self.unlock_ui()


    def httpRequestFinished(self, requestId, error):
        if requestId != self.httpGetId:
            return

        if self.httpRequestAborted:
            if self.outFile is not None:
                self.outFile.close()
                self.outFile.remove()
                self.outFile = None
            return

        self.outFile.close()

        self.ui.progressBar.setMaximum(1)
        self.ui.progressBar.setValue(1)

        if error:
            self.outFile.remove()
            QtGui.QMessageBox.critical(self, "Error", "Download failed: %s." % self.http.errorString())
            self.reset_ui_download()
        else:      
            self.ui.lblMessage.setText("")
            self.downloadedfiles.append(unicode(self.outFile.fileName()))
            self.download_next()

        self.ui.progressBar.setMaximum(1)
        self.ui.progressBar.setValue(0)


    def readResponseHeader(self, responseHeader):
        # Check for genuine error conditions.
        if responseHeader.statusCode() not in (200, 300, 301, 302, 303, 307):
            QMessageBox.critical(self, "Error", "Download failed: %s." % responseHeader.reasonPhrase())
            self.httpRequestAborted = True
            self.http.abort()


    def updateDataReadProgress(self, bytesRead, totalBytes):
        if self.httpRequestAborted:
            return
        self.ui.progressBar.setMaximum(totalBytes)
        self.ui.progressBar.setValue(bytesRead)
        self.ui.lblMessage.setText("Please wait while downloading - {0} Bytes downloaded!".format(str(bytesRead)))


    def authenticationRequired(self, hostName, _, authenticator):
        self.http.authenticationRequired.disconnect(self.authenticationRequired)
        authenticator.setUser(self.ui.txtUsername.text().trimmed())
        authenticator.setPassword(self.ui.txtPassword.text().trimmed())

    