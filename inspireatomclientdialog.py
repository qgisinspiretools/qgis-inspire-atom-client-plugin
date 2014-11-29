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
    def __init__(self, parent):
        super(InspireAtomClientDialog, self).__init__(None)
        self.setupUi(self)
        self.parent = parent
        self.iface = self.parent.iface
        self.root = QgsProject.instance().layerTreeRoot()

        
        self.settings = QSettings()
        self.init_variables()

        # Connect signals
        QObject.connect(self.cmdGetFeed, SIGNAL("clicked()"), self.get_service_feed)
        QObject.connect(self.cmdSelectDataset, SIGNAL("clicked()"), self.select_dataset_feed_byclick)
        QObject.connect(self.cmdDownload, SIGNAL("clicked()"), self.download_files)
        QObject.connect(self.cmdMetadata, SIGNAL("clicked()"), self.show_metadata)
        QObject.connect(self.cmbDatasets, SIGNAL("currentIndexChanged(int)"), self.select_dataset_feed_bylist)
        QObject.connect(self.cmbDatasetRepresentations, SIGNAL("currentIndexChanged(int)"), self.update_lw_files)

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
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.onlineresource = self.txtUrl.text().strip()
            request = unicode(self.onlineresource)
            if self.chkAuthentication.isChecked():
                self.setup_urllib2(request, self.txtUsername.text().strip(), self.txtPassword.text().strip())
            else:
                self.setup_urllib2(request, "", "")
            response = urllib2.urlopen(request, None, 10)
            buf = response.read()
            #QMessageBox.information(self, "Debug", buf)
        except urllib2.HTTPError, e:  
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "HTTP Error", "HTTP Error: {0}".format(e.code))
            if e.code == 401:
                self.chkAuthentication.setChecked(True)
        except urllib2.URLError, e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "URL Error", "URL Error: {0}".format(e.reason))
        else:
            layername="INSPIRE_DLS#{0}".format(''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(6)))
            tmpfile = self.save_tempfile("{0}.xml".format(layername), buf)
            vlayer = QgsVectorLayer(tmpfile, layername, "ogr")
            vlayer.setProviderEncoding("UTF-8") #Ignore System Encoding --> TODO: Use XML-Header
            if not vlayer.isValid():
                QMessageBox.critical(self, "QGIS-Layer Error", "Response is not a valid QGIS-Layer!")
            else: 
                self.add_layer(vlayer)
                self.iface.mapCanvas().setCurrentLayer(vlayer)
                self.layername = vlayer.name()
                self.iface.zoomToActiveLayer()
                self.clear_frame()
                self.update_cmbDatasets()
                
                # Lock
                self.cmdGetFeed.setEnabled(False)
                self.chkAuthentication.setEnabled(False)
                self.txtUrl.setEnabled(False)
                self.txtUsername.setEnabled(False)
                self.txtPassword.setEnabled(False)
        QApplication.restoreOverrideCursor()   

    # update cmbDatasets
    def update_cmbDatasets(self):
        self.is_cmbDatasets_locked = True
        self.cmbDatasets.clear()
        self.cmdSelectDataset.setEnabled(False)
        # get currentLayer and dataProvider
        cLayer = self.iface.mapCanvas().currentLayer()
        if cLayer.type() != QgsMapLayer.VectorLayer:
            return 
        selectList = []
        provider = cLayer.dataProvider()
        feat = QgsFeature()
        num_features_validated = 0
        num_features_not_validated = 0
        dataset_index = 0
        
        iter = cLayer.getFeatures()
        for feature in iter:
            if self.validate_feature(provider, feature):
                num_features_validated += 1
                self.cmbDatasets.addItem(unicode(feature.attribute("title")), unicode(feature.attribute("title")))
                self.datasetindexes[unicode(feature.attribute("title"))] = dataset_index
                dataset_index += 1
            else:
                 num_features_not_validated += 1

        if num_features_validated == 0:
            QMessageBox.critical(self, "INSPIRE Service Feed Error", "Unable to process INSPIRE Service Feed!")
        else:        
            self.cmdSelectDataset.setEnabled(True)
            self.is_cmbDatasets_locked = False
            self.select_dataset_feed_bylist()
 

    # check "Service Feed Entry" for Identifier, Title, Dataset Feed Link
    def validate_feature(self, provider, feature):
        try:
            # Dataset Identifier             
            if provider.fieldNameIndex("inspire_dls_spatial_dataset_identifier_code") > -1:
                if len(unicode(feature.attribute("inspire_dls_spatial_dataset_identifier_code"))):
                    # Dataset Title
                    if provider.fieldNameIndex("title") > -1:
                         if len(unicode(feature.attribute("title"))) > 0:
                             # Datasetfeed Link
                             key = 0
                             for value in feature.attributes():
                                if value == "alternate":
                                    fieldname = provider.fields()[key].name().replace("rel", "href")
                                    if provider.fieldNameIndex(fieldname) > -1:
                                        return True 
                                key += 1
            return False
        except KeyError, e:
            return False

    # select "Dataset Feed" | cmbDatasets "currentIndexChanged(int)" Signal
    def select_dataset_feed_bylist(self):
        if self.is_cmbDatasets_locked:
            return
        self.clear_frame()
        self.lblMessage.setText("")
        cLayer = self.iface.mapCanvas().currentLayer()
        if not cLayer.name() == self.layername:
            QMessageBox.critical(self, "QGIS-Layer Error", "Selected Layer isn't the INSPIRE Service Feed!")
            return 
        if cLayer.type() != QgsMapLayer.VectorLayer:
            return 
        selectList = []
        provider = cLayer.dataProvider()

        iter = cLayer.getFeatures()
        for feature in iter:
            if len(self.cmbDatasets.currentText()) > 0:
                try:
                    if unicode(feature.attribute("title")) == unicode(self.cmbDatasets.currentText()):
                        self.handle_dataset_selection(feature, provider)
                        selectList.append(feature.id())
                except KeyError, e:
                    self.lblMessage.setText("") # TODO: exception handling
        # make the actual selection
        cLayer.setSelectedFeatures(selectList)


    # select "Dataset Feed" | cmdSelectDataset Signal
    def select_dataset_feed_byclick(self):
        self.clear_frame()
        self.lblMessage.setText("")
        # http://www.qgisworkshop.org/html/workshop/plugins_tutorial.html
        result = QObject.connect(self.parent.clickTool, SIGNAL("canvasClicked(const QgsPoint &, Qt::MouseButton)"), self.select_dataset_feed_byclick_procedure)
        self.iface.mapCanvas().setMapTool(self.parent.clickTool)


    # select "Dataset Feed" | Signal ("Click")
    def select_dataset_feed_byclick_procedure(self, point, button):
        self.clear_frame()
        # setup the provider select to filter results based on a rectangle
        pntGeom = QgsGeometry.fromPoint(point)  
        # scale-dependent buffer of 2 pixels-worth of map units
        pntBuff = pntGeom.buffer( (self.iface.mapCanvas().mapUnitsPerPixel() * 2), 0) 
        rect = pntBuff.boundingBox()
        # get currentLayer and dataProvider
        cLayer = self.iface.mapCanvas().currentLayer()
        if not cLayer.name() == self.layername:
            QMessageBox.critical(self, "QGIS-Layer Error", "Selected Layer isn't the INSPIRE Service Feed!")
            result = QObject.disconnect(self.parent.clickTool, SIGNAL("canvasClicked(const QgsPoint &, Qt::MouseButton)"), self.select_dataset_feed_byclick_procedure)
            self.iface.mapCanvas().unsetMapTool(self.parent.clickTool)
            return 
        if cLayer.type() != QgsMapLayer.VectorLayer:
            return 
        selectList = []
        provider = cLayer.dataProvider()

        request=QgsFeatureRequest()
        request.setFilterRect(rect)
        
        iter = cLayer.getFeatures(request)
        for feature in iter:
            if feature.geometry().intersects(pntGeom):
                selectList.append(feature.id())
                self.handle_dataset_selection(feature, provider)
                break

        # make the actual selection
        cLayer.setSelectedFeatures(selectList)
        result = QObject.disconnect(self.parent.clickTool, SIGNAL("canvasClicked(const QgsPoint &, Qt::MouseButton)"), self.select_dataset_feed_byclick_procedure)
        self.iface.mapCanvas().unsetMapTool(self.parent.clickTool)


    # handle selection | selected by list or by click
    def handle_dataset_selection(self, feature, provider):
        if not self.validate_feature(provider, feature):
            QMessageBox.critical(self, "INSPIRE Service Feed Entry Error", "Unable to process selected INSPIRE Service Feed Entry!")
            return

        dataset = inspireatomlib.Dataset(unicode(feature.attribute("inspire_dls_spatial_dataset_identifier_code")))
        dataset.setTitle(unicode(feature.attribute("title")))

        if provider.fieldNameIndex("summary") > -1:
            dataset.setSummary(unicode(feature.attribute("summary")))                    
        if provider.fieldNameIndex("rights") > -1:
            dataset.setRights(unicode(feature.attribute("rights")))

        key = 0
        for value in feature.attributes():
            if value == "alternate":
                fieldname = provider.fields()[key].name().replace("rel", "href")
                if provider.fieldNameIndex(fieldname) > -1:
                    linksubfeed = unicode(feature.attribute(fieldname))
                    dataset.setLinkSubfeed(self.buildurl(linksubfeed))
            if value == "describedby":
                fieldname = provider.fields()[key].name().replace("rel", "href")
                if provider.fieldNameIndex(fieldname) > -1:
                    linkmetadata = unicode(feature.attribute(fieldname))
                    dataset.setLinkMetadata(self.buildurl(linkmetadata))
            key += 1

        self.cmbDatasets.setCurrentIndex(self.datasetindexes[dataset.getTitle()])
        self.cmbDatasetRepresentations.clear()
        self.groupBoxDataset.setEnabled(True)
        self.groupBoxSelectedDataset.setEnabled(True)
        self.lblTitle.setText(dataset.getTitle())
        self.txtSummary.setPlainText(dataset.getSummary())
        self.txtId.setText(dataset.getId())
        self.txtRights.setPlainText(dataset.getRights())                    

        if dataset.getLinkMetadata():
            if len(dataset.getLinkMetadata()) > 0:
                self.cmdMetadata.setEnabled(True)
                self.currentmetadata = dataset.getLinkMetadata()
            else: 
                self.cmdMetadata.setEnabled(False)
                self.currentmetadata = ""
        else:
            self.cmdMetadata.setEnabled(False)
            self.currentmetadata = ""

        self.receive_dataset_representations(dataset.getLinkSubfeed())

    # request and handle "Dataset Feed" (dataset representations)
    def receive_dataset_representations(self, subfeedurl): 
        try:
            if self.chkAuthentication.isChecked():
                self.setup_urllib2(subfeedurl, self.txtUsername.text().strip(), self.txtPassword.text().strip())
            else:
                self.setup_urllib2(subfeedurl, "", "")
            response = urllib2.urlopen(subfeedurl, None, 10)
            buf = response.read()
        except urllib2.HTTPError, e:  
            QMessageBox.critical(self, "HTTP Error", "HTTP Error: {0}".format(e.code))
        except urllib2.URLError, e:
            QMessageBox.critical(self, "URL Error", "URL Error: {0}".format(e.reason))
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
                        self.datasetrepresentations[(datasetrepresentation.getTitle())] = datasetrepresentation
                        self.cmbDatasetRepresentations.addItem(datasetrepresentation.getTitle(), datasetrepresentation.getTitle())
                        self.cmdDownload.setEnabled(True)
            
            else:
                QMessageBox.critical(self, "INSPIRE Dataset Feed Error", "Unable to process INSPIRE Dataset Feed!") 

    # update ListWidget | cmbDatasetRepresentations "currentIndexChanged(int)" Signal
    def update_lw_files(self):
        self.lwFiles.clear()
        if len(self.cmbDatasetRepresentations.currentText()) > 0:
            datasetrepresentation = self.datasetrepresentations[self.cmbDatasetRepresentations.currentText()]
            for file in datasetrepresentation.getFiles():                
                self.lwFiles.addItem(file)

    def clear_frame(self):
        self.lblTitle.setText("Title")
        self.txtSummary.setPlainText("")
        self.txtId.setText("")
        self.txtRights.setPlainText("")
        self.cmbDatasetRepresentations.clear()
        self.lwFiles.clear()
        self.cmdDownload.setEnabled(False)
        self.cmdMetadata.setEnabled(False)
        #self.groupBoxDataset.setEnabled(False) # probably not yet 'perfect'...
        self.groupBoxSelectedDataset.setEnabled(False)

    def show_metadata(self):
        if len(self.currentmetadata) > 0:
            xslfilename = os.path.join(plugin_path, "iso19139jw.xsl")
            html = self.xsl_transform(self.currentmetadata, xslfilename)
       
            if html:
                # create and show the dialog
                dlg = MetadataClientDialog()
                dlg.wvMetadata.setContent(str(html)) # setHtml does not work with "Umlaute". Some modifications were also needed when doing the urlib2 and xslt stuff.
                dlg.setWindowFlags(Qt.WindowStaysOnTopHint)
                # show the dialog
                dlg.show()
                result = dlg.exec_()
                # See if OK was pressed
                if result == 1:
                    # do something useful (delete the line containing pass and
                    # substitute with your code
                    pass
            else:
                QMessageBox.critical(self, "Metadata Error", "Unable to read the Metadata")

    """
    ############################################################################################################################
    # Download
    ############################################################################################################################
    """
   
    # execute download procedure | cmdDownload Signal
    def download_files(self):
        self.lblMessage.setText("")

        self.httpGetId = 0
        self.httpRequestAborted = False
        self.downloadedfiles = []

        self.setup_qhttp()
        self.http.requestFinished.connect(self.httpRequestFinished)
        self.http.dataReadProgress.connect(self.updateDataReadProgress)
        self.http.responseHeaderReceived.connect(self.readResponseHeader)
        if self.chkAuthentication.isChecked():
            self.http.authenticationRequired.connect(self.authenticationRequired)

        self.download_next()

    # download next file (after finishing the last one)
    def download_next(self):
       datasetrepresentation = self.datasetrepresentations[self.cmbDatasetRepresentations.currentText()]
       if self.currentfile < len(datasetrepresentation.getFiles()):
           self.cmdGetFeed.setEnabled(False)
           self.cmdDownload.setEnabled(False)
           self.cmdSelectDataset.setEnabled(False)
           self.cmdMetadata.setEnabled(False)
           self.cmbDatasets.setEnabled(False)
           self.cmbDatasetRepresentations.setEnabled(False)
           self.lwFiles.setItemSelected(self.lwFiles.item(self.currentfile), True)
           self.cmdDownload.setText("Downloading {0}/{1}".format(self.currentfile + 1, len(datasetrepresentation.getFiles())))
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
                #fileInfo = QFileInfo(file)
                #baseName = fileInfo.baseName()
                rlayer = QgsRasterLayer(file, file)   
                if not rlayer.isValid():
                    failed.append(file)
                    self.lblMessage.setText("")
                else:
                    self.add_layer(rlayer)
                    self.iface.zoomToActiveLayer()
                    successful.append(file)
            else: 
                self.lblMessage.setText("")
                self.add_layer(vlayer)
                self.iface.zoomToActiveLayer()
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
        QMessageBox.information(self, "Import Status", message)

    
    def reset_ui_download(self):
        self.cmdDownload.setText("Download")
        self.cmdDownload.setEnabled(True)
        self.cmdSelectDataset.setEnabled(True)
        self.cmbDatasets.setEnabled(True)
        self.cmbDatasetRepresentations.setEnabled(True)
        self.currentfile = 0
        if len(self.currentmetadata) > 0:
            self.cmdMetadata.setEnabled(True)


    def add_layer(self, layer):
        QgsMapLayerRegistry.instance().addMapLayer(layer, False)
        layerNode = self.root.insertLayer(0, layer)
        layerNode.setExpanded(False)    
        layerNode.setVisible(Qt.Checked)
        
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
        if self.settings.value("/proxy/proxyEnabled") == "true":
           proxy = "{0}:{1}".format(self.settings.value("/proxy/proxyHost"), self.settings.value("/proxy/proxyPort"))
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
            buf = response.read().decode('utf-8') 
        except urllib2.HTTPError, e:  
            QMessageBox.critical(self, "HTTP Error", "HTTP Error: {0}".format(e.code))
        except urllib2.URLError, e:
            QMessageBox.critical(self, "URL Error", "URL Error: {0}".format(e.reason))
        else:
           # load xslt
           xslt_file = QFile(xslfilename)
           xslt_file.open(QIODevice.ReadOnly)
           xslt = str(xslt_file.readAll())
           xslt_file.close()
 
           # load xml
           xml_source = unicode(buf)

           # xslt
           qry = QtXmlPatterns.QXmlQuery(QtXmlPatterns.QXmlQuery.XSLT20)
           qry.setFocus(xml_source)
           qry.setQuery(xslt)

           array = QByteArray()
           buf = QBuffer(array)
           buf.open(QIODevice.WriteOnly)
           qry.evaluateTo(buf)
           xml_target = str(array)
           return xml_target


    #############################################################################################################
    # QHttp GetFeature-Request - http://stackoverflow.com/questions/6852038/threading-in-pyqt4
    #############################################################################################################

    def downloadFile(self, httplink, fileName):
        #self.lock_ui()
        url = QUrl(httplink)

        if QFile.exists(fileName):
            QFile.remove(fileName)

        self.outFile = QFile(fileName)
        if not self.outFile.open(QIODevice.WriteOnly):
            QMessageBox.critical(self, "Error", "Unable to save the file %s: %s." % (fileName, self.outFile.errorString()))
            self.outFile = None
            return

        mode = QHttp.ConnectionModeHttp
        port = url.port()
        if port == -1:
            port = 0
        self.http.setHost(url.host(), mode, port)
        self.httpRequestAborted = False
        # Download the file.
        self.progressBar.setVisible(True)
    
        self.httpGetId = self.http.get(url.toString(), self.outFile)


    # currently unused
    def cancelDownload(self):
        self.httpRequestAborted = True
        self.http.abort()
        self.close()

        self.progressBar.setMaximum(1)
        self.progressBar.setValue(0)
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

        self.progressBar.setMaximum(1)
        self.progressBar.setValue(1)

        if error:
            self.outFile.remove()
            QMessageBox.critical(self, "Error", "Download failed: %s." % self.http.errorString())
            self.reset_ui_download()
        else:      
            self.lblMessage.setText("")
            self.downloadedfiles.append(unicode(self.outFile.fileName()))
            self.download_next()

        self.progressBar.setMaximum(1)
        self.progressBar.setValue(0)


    def readResponseHeader(self, responseHeader):
        # Check for genuine error conditions.
        if responseHeader.statusCode() not in (200, 300, 301, 302, 303, 307):
            QMessageBox.critical(self, "Error", "Download failed: %s." % responseHeader.reasonPhrase())
            self.httpRequestAborted = True
            self.http.abort()


    def updateDataReadProgress(self, bytesRead, totalBytes):
        if self.httpRequestAborted:
            return
        self.progressBar.setMaximum(totalBytes)
        self.progressBar.setValue(bytesRead)
        self.lblMessage.setText("Please wait while downloading - {0} Bytes downloaded!".format(str(bytesRead)))


    def authenticationRequired(self, hostName, _, authenticator):
        self.http.authenticationRequired.disconnect(self.authenticationRequired)
        authenticator.setUser(self.txtUsername.text().strip())
        authenticator.setPassword(self.txtPassword.text().strip())
