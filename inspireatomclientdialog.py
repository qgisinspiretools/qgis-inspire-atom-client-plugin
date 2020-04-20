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
from PyQt5 import uic
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtNetwork import *
from PyQt5 import QtXmlPatterns
from qgis.core import *
from xml.etree import ElementTree
from urllib.parse import urljoin
from urllib.parse import urlparse
import urllib.request as urllib2
import string
import random
import tempfile
import os
import os.path

from .inspireatomlib import DatasetRepresentation, Dataset
from .metadataclientdialog import MetadataClientDialog

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'ui_inspireatomclient.ui'))

plugin_path = os.path.abspath(os.path.dirname(__file__))

class InspireAtomClientDialog(QDialog, FORM_CLASS):
    def __init__(self, parent):
        super(InspireAtomClientDialog, self).__init__(None)
        self.setupUi(self)
        self.parent = parent
        self.iface = self.parent.iface
        self.root = QgsProject.instance().layerTreeRoot()

        self.qnam = QNetworkAccessManager()
        self.qnam.authenticationRequired.connect(self.authenticationRequired)
        self.qnam.sslErrors.connect(self.sslErrors)
        self.settings = QSettings()
        self.init_variables()

        self.txtPassword.setEchoMode(QLineEdit.Password)

        # Connect signals
        self.cmdGetFeed.clicked.connect(self.get_service_feed)

        self.cmdSelectDataset.clicked.connect(self.select_dataset_feed_byclick)

        self.cmdDownload.clicked.connect(self.download_files)

        self.cmdMetadata.clicked.connect(self.show_metadata)

        self.cmbDatasets.currentIndexChanged.connect(self.select_dataset_feed_bylist)

        self.cmbDatasetRepresentations.currentIndexChanged.connect(self.update_lw_files)

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

        self.onlineresource = self.txtUrl.text().strip()
        request = str(self.onlineresource)

        self.reply = None
        self.httpGetId = 0
        self.url = QUrl(request)

        self.startAtomFeedMetadataRequest(self.url)

    def startAtomFeedMetadataRequest(self, url):
        self.reply = self.qnam.get(QNetworkRequest(url))
        self.log_message("Fetching atom feed " + url.toDisplayString())
        self.reply.finished.connect(self.atomFeedMetadataFinished)
        self.reply.error.connect(self.errorOcurred)

    def atomFeedMetadataFinished(self):
        self.log_message('Atom feed request finished')
        if self.checkForHTTPErrors():
            return

        buf = self.reply.readAll().data()
        layername = "INSPIRE_DLS#{0}".format(
            ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(6)))
        tmpfile = self.save_tempfile("{0}.xml".format(layername), buf)
        vlayer = QgsVectorLayer(tmpfile, layername, "ogr")
        vlayer.setProviderEncoding("UTF-8")  # Ignore System Encoding --> TODO: Use XML-Header
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
            self.txtUrl.setEnabled(False)

        QApplication.restoreOverrideCursor()

    def checkForHTTPErrors(self):
        http_code = self.reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        if http_code is not None:
            self.log_message('Request finished with HTTP code {0}'.format(http_code))
        else:
            self.log_message('Request finished with no HTTP code (aborted?)')

        if http_code == 401:
            QMessageBox.critical(
                self,
                "HTTP 401 Unauthorized",
                "Authentication is required for this request"
            )
            return True

        if http_code == 403:
            QMessageBox.critical(
                self,
                "HTTP 403 Forbidden",
                "Your authentication is insufficient for this request"
            )
            return True

        if http_code == 404:
            QMessageBox.critical(
                self,
                "HTTP 404 Not Found",
                "The specified resource was not found - is the URL correct?"
            )
            return True

        error = self.reply.error()
        if error != QNetworkReply.NoError:
            if not self.httpRequestAborted:
                QMessageBox.critical(self, "HTTP Error",
                                     "Request failed: %s." % self.reply.errorString())
            return True

        return False

    def errorOcurred(self, error_code):
        if self.reply is None:
            self.log_message('HTTP error occurred: {0}'.format(error_code), Qgis.Warning)
        else:
            self.log_message('HTTP error occurred: {0}'.format(self.reply.errorString(), Qgis.Warning))

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
                self.cmbDatasets.addItem(str(feature.attribute("title")), str(feature.attribute("title")))
                self.datasetindexes[str(feature.attribute("title"))] = dataset_index
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
                if len(str(feature.attribute("inspire_dls_spatial_dataset_identifier_code"))):
                    # Dataset Title
                    if provider.fieldNameIndex("title") > -1:
                        if len(str(feature.attribute("title"))) > 0:
                            # Datasetfeed Link
                            key = 0
                            for value in feature.attributes():
                                if value == "alternate":
                                    fieldname = provider.fields()[key].name().replace("rel", "href")
                                    if provider.fieldNameIndex(fieldname) > -1:
                                        return True
                                key += 1
            return False
        except KeyError:
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
                    if str(feature.attribute("title")) == str(self.cmbDatasets.currentText()):
                        self.handle_dataset_selection(feature, provider)
                        selectList.append(feature.id())
                except KeyError:
                    self.lblMessage.setText("")  # TODO: exception handling
        # make the actual selection
        cLayer.selectByIds(selectList)

    # select "Dataset Feed" | cmdSelectDataset Signal
    def select_dataset_feed_byclick(self):
        self.clear_frame()
        self.lblMessage.setText("")
        # http://www.qgisworkshop.org/html/workshop/plugins_tutorial.html
        result = self.parent.clickTool.canvasClicked.connect(self.select_dataset_feed_byclick_procedure)
        self.iface.mapCanvas().setMapTool(self.parent.clickTool)


    # select "Dataset Feed" | Signal ("Click")
    def select_dataset_feed_byclick_procedure(self, point, button):
        self.clear_frame()
        # setup the provider select to filter results based on a rectangle
        pntGeom = QgsGeometry.fromPointXY(point)
        # scale-dependent buffer of 2 pixels-worth of map units
        pntBuff = pntGeom.buffer((self.iface.mapCanvas().mapUnitsPerPixel() * 2), 0)
        rect = pntBuff.boundingBox()
        # get currentLayer and dataProvider
        cLayer = self.iface.mapCanvas().currentLayer()
        if not cLayer.name() == self.layername:
            QMessageBox.critical(self, "QGIS-Layer Error", "Selected Layer isn't the INSPIRE Service Feed!")
            result = self.parent.clickTool.canvasClicked.disconnect(self.select_dataset_feed_byclick_procedure)
            self.iface.mapCanvas().unsetMapTool(self.parent.clickTool)
            return
        if cLayer.type() != QgsMapLayer.VectorLayer:
            return
        selectList = []
        provider = cLayer.dataProvider()

        request = QgsFeatureRequest()
        request.setFilterRect(rect)

        iter = cLayer.getFeatures(request)
        for feature in iter:
            if feature.geometry().intersects(pntGeom):
                selectList.append(feature.id())
                self.handle_dataset_selection(feature, provider)
                break

        # make the actual selection
        cLayer.selectByIds(selectList)
        result = self.parent.clickTool.canvasClicked.disconnect(self.select_dataset_feed_byclick_procedure)
        self.iface.mapCanvas().unsetMapTool(self.parent.clickTool)

    # handle selection | selected by list or by click
    def handle_dataset_selection(self, feature, provider):
        if not self.validate_feature(provider, feature):
            QMessageBox.critical(self, "INSPIRE Service Feed Entry Error",
                                 "Unable to process selected INSPIRE Service Feed Entry!")
            return
        dataset = Dataset(str(feature.attribute("inspire_dls_spatial_dataset_identifier_code")))
        dataset.setTitle(str(feature.attribute("title")))
        if provider.fieldNameIndex("summary") > -1:
            dataset.setSummary(str(feature.attribute("summary")))
        if provider.fieldNameIndex("rights") > -1:
            dataset.setRights(str(feature.attribute("rights")))

        key = 0
        for value in feature.attributes():
            if value == "alternate":
                fieldname = provider.fields()[key].name().replace("rel", "href")
                if provider.fieldNameIndex(fieldname) > -1:
                    linksubfeed = str(feature.attribute(fieldname))
                    dataset.setLinkSubfeed(self.buildurl(linksubfeed))
            if value == "describedby":
                fieldname = provider.fields()[key].name().replace("rel", "href")
                if provider.fieldNameIndex(fieldname) > -1:
                    linkmetadata = str(feature.attribute(fieldname))
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
        self.url = QUrl(subfeedurl)
        self.reply = self.qnam.get(QNetworkRequest(self.url))
        self.log_message("Fetching dataset feed " + self.url.toDisplayString())
        self.reply.finished.connect(self.datasetRepReceived)
        self.reply.error.connect(self.errorOcurred)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.httpGetId = 0

    def datasetRepReceived(self):
        self.log_message ("Dataset feed request finished")
        QApplication.restoreOverrideCursor()
        if self.checkForHTTPErrors():
            return

        buf = self.reply.readAll().data()

        self.datasetrepresentations = {}
        try:
            root = ElementTree.fromstring(buf)
        except ElementTree.ParseError as err:
            QMessageBox.critical(
                self,
                "XML Parsing error",
                "The dataset feed could not be read:\n{0}".format(err.msg)
            )
            return

        # ATOM Namespace
        namespace = "{http://www.w3.org/2005/Atom}"
        # check correct Rootelement
        if root.tag == "{0}feed".format(namespace):
            for target in root.findall("{0}entry".format(namespace)):
                idvalue = ""
                for id in target.findall("{0}id".format(namespace)):
                    idvalue = id.text
                if (idvalue):
                    datasetrepresentation = DatasetRepresentation(idvalue)
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
                    self.cmbDatasetRepresentations.addItem(datasetrepresentation.getTitle(),
                                                           datasetrepresentation.getTitle())
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
        # self.groupBoxDataset.setEnabled(False) # probably not yet 'perfect'...
        self.groupBoxSelectedDataset.setEnabled(False)

    def show_metadata(self):
        if len(self.currentmetadata) > 0:
            self.reply = self.qnam.get(QNetworkRequest(QUrl(self.currentmetadata)))
            self.log_message("Fetching metadata " + self.currentmetadata)
            self.reply.finished.connect(self.metadata_request_finished)
            self.reply.error.connect(self.errorOcurred)

    def metadata_request_finished(self):
        self.log_message ("Metadata request finished")
        if self.checkForHTTPErrors():
            return

        response = self.reply
        xslfilename = os.path.join(plugin_path, "iso19139jw.xsl")

        response_content = response.readAll()
        encoding = 'utf_8'
        for header in response.rawHeaderPairs():
            if header[0].toLower() == 'content-type':
                charset_index = header[1].indexOf('charset=')
                if charset_index > -1:
                    encoding = str(header[1][charset_index + 8:], 'ascii')
                    self.log_message('Got encoding from Content-Type header: {0}'.format(encoding))

        encoding = encoding.lower().translate(encoding.maketrans('-', '_'))
        self.log_message('Using encoding {0} for metadata'.format(encoding))

        try:
            xml_source = str(response_content, encoding)
        except LookupError:
            self.log_message('Could not use encoding {0}, trying again with utf_8'.format(encoding), Qgis.Warning)
            xml_source = str(response_content, 'utf_8')

        qry = QtXmlPatterns.QXmlQuery(QtXmlPatterns.QXmlQuery.XSLT20)
        qry.setMessageHandler(MessageHandler())
        qry.setFocus(xml_source)
        qry.setQuery(QUrl('file:///' + xslfilename))

        html = qry.evaluateToString()

        if html:
            # create and show the dialog
            dlg = MetadataClientDialog()
            dlg.wvMetadata.setHtml(html)
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
        self.reset_ui_download()
        self.lblMessage.setText("")

        self.httpGetId = 0
        self.httpRequestAborted = False
        self.downloadedfiles = []
        self.download_next()

    # download next file (after finishing the last one)
    def download_next(self):
        self.currentdownload += 1
        datasetrepresentation = self.datasetrepresentations[self.cmbDatasetRepresentations.currentText()]
        num_selected = len(self.lwFiles.selectedItems())
        if num_selected > 0:
            num_downloads = num_selected
        else:
            num_downloads = len(datasetrepresentation.getFiles())

        if num_selected > 0 and self.currentdownload < num_downloads:
            # skip files not selected for download
            while not self.lwFiles.item(self.currentfile).isSelected() and self.currentfile < num_downloads:
                self.currentfile += 1

        if self.currentdownload <= num_downloads:
            self.cmdGetFeed.setEnabled(False)
            self.cmdDownload.setEnabled(False)
            self.cmdSelectDataset.setEnabled(False)
            self.cmdMetadata.setEnabled(False)
            self.cmbDatasets.setEnabled(False)
            self.cmbDatasetRepresentations.setEnabled(False)

            self.cmdDownload.setText(
                "Downloading {0}/{1}".format(self.currentdownload, num_downloads))
            next_file = datasetrepresentation.getFiles()[self.currentfile]
            filename = self.buildfilename(next_file)
            self.downloadFile(next_file, self.get_temppath(filename))
            self.currentfile += 1
        else:
            self.load_downloaded_files()
            self.reset_ui_download()

    # try to load downloaded files as QGIS-Layer(s)
    def load_downloaded_files(self):
        failed = []
        successful = []
        for downloaded_file in self.downloadedfiles:
            is_ogr = False
            try_ogr = True
            # avoid trying to open using OGR for file-types which are not handled by OGR
            # TODO inspect MIME-type of file
            if downloaded_file.endswith('.bmp') \
                    or downloaded_file.endswith('.gif') \
                    or downloaded_file.endswith('.jpeg') \
                    or downloaded_file.endswith('.jpg') \
                    or downloaded_file.endswith('.png') \
                    or downloaded_file.endswith('.tif') \
                    or downloaded_file.endswith('.tiff'):
                try_ogr = False
            if try_ogr:
                self.log_message('Trying to load {0} as vector layer'.format(downloaded_file))
                vlayer = QgsVectorLayer(downloaded_file, downloaded_file, "ogr")
                is_ogr = vlayer.isValid()
                if is_ogr:
                    self.log_message('Successfully loaded {0} as vector layer'.format(downloaded_file))
                else:
                    self.log_message('{0} could not be loaded as a vector layer'.format(downloaded_file))
            if not is_ogr:
                self.log_message('Trying to load {0} as raster layer'.format(downloaded_file))
                rlayer = QgsRasterLayer(downloaded_file, downloaded_file)
                if not rlayer.isValid():
                    self.log_message('{0} could not be loaded as a raster layer'.format(downloaded_file))
                    failed.append(downloaded_file)
                    self.lblMessage.setText("")
                else:
                    self.log_message('Successfully loaded {0} as raster layer'.format(downloaded_file))
                    self.add_layer(rlayer)
                    self.iface.zoomToActiveLayer()
                    successful.append(downloaded_file)
            else:
                self.lblMessage.setText("")
                self.add_layer(vlayer)
                self.iface.zoomToActiveLayer()
                successful.append(downloaded_file)

        message = ""
        if len(successful) > 0:
            message += "<p><b>Successfully loaded:</b><br />"
            for successful_file in successful:
                message += successful_file + "<br />"
            message += "</p>"
        if len(failed) > 0:
            message += "<p><b>Failed to load:</b><br />"
            for failed_file in failed:
                message += failed_file + "<br />"
            message += "</p>"
        QMessageBox.information(self, "Import Status", message)


    def reset_ui_download(self):
        self.cmdDownload.setText("Download")
        self.cmdDownload.setEnabled(True)
        self.cmdSelectDataset.setEnabled(True)
        self.cmbDatasets.setEnabled(True)
        self.cmbDatasetRepresentations.setEnabled(True)
        self.currentfile = 0
        self.currentdownload = 0
        if len(self.currentmetadata) > 0:
            self.cmdMetadata.setEnabled(True)


    def add_layer(self, layer):
        QgsProject.instance().addMapLayer(layer, False)
        layerNode = self.root.insertLayer(0, layer)
        layerNode.setExpanded(False)
        # layerNode.setVisible(Qt.Checked)

    """
    ############################################################################################################################
    # UTIL
    ############################################################################################################################
    """

    # QHttp Slot
    def authenticationRequired(self, reply, authenticator):
        use_authentication = self.chkAuthentication.isChecked()
        username = self.txtUsername.text().strip()
        password = self.txtPassword.text().strip()
        previousUsername = authenticator.user()
        previousPassword = authenticator.password()

        terminate_request = False

        if not(use_authentication):
            QMessageBox.critical(
                self,
                "Authentication required",
                "Authentication is required for this request"
            )
            self.chkAuthentication.setChecked(True)
            self.txtUsername.setFocus()
            terminate_request = True

        if username == '' and not terminate_request:
            QMessageBox.critical(
                self,
                "Authentication required",
                "Please enter your username for this request"
            )
            self.txtUsername.setFocus()
            terminate_request = True

        if username == previousUsername and password == previousPassword and not terminate_request:
            QMessageBox.critical(
                self,
                "Authentication failed",
                "Authentication with username/password failed - please check and try again"
            )
            self.txtUsername.setFocus()
            terminate_request = True

        if terminate_request:
            self.httpRequestAborted = True
            reply.abort()
            return

        authenticator.setUser(username)
        authenticator.setPassword(password)
        self.log_message("Using username {0} / password ***".format(username))

    def sslErrors(self, reply, errors):
        errorString = ""
        for error in errors:
            errorString += " * " + error.errorString() + "\n"

        ret = QMessageBox.question(
            self,
            "Certificate validation error",
            "The following SSL validation errors have been reported:\n\n%s\n" \
            "This may indicate a problem with the server and/or its certificate.\n\n" \
            "Do you wish to continue anyway?" % errorString,
            QMessageBox.Yes | QMessageBox.No
        )

        if ret == QMessageBox.Yes:
            self.log_message("Ignoring SSL errors", Qgis.Warning)
            reply.ignoreSslErrors()
        else:
            self.httpRequestAborted = True

    def log_message(self, message, level=Qgis.Info):
        if 'QgsMessageLog' in globals():
            QgsMessageLog.logMessage(message, "INSPIRE Atom Client", level)

    def get_temppath(self, filename):
        tmpdir = os.path.join(tempfile.gettempdir(), 'inspireatomclient')
        if not os.path.exists(tmpdir):
            os.makedirs(tmpdir)
        tmpfile = os.path.join(tmpdir, filename)
        return tmpfile


    def save_tempfile(self, filename, content):
        tmpdir = os.path.join(tempfile.gettempdir(), 'inspireatomclient')
        if not os.path.exists(tmpdir):
            os.makedirs(tmpdir)
        tmpfile = os.path.join(tmpdir, filename)
        fobj = open(tmpfile, 'wb')
        fobj.write(content)
        fobj.close()
        return tmpfile


    # Receive Proxy from QGIS-Settings
    def getProxy(self):
        if self.settings.value("/proxy/proxyEnabled") == True:
            proxy = "{0}:{1}".format(self.settings.value("/proxy/proxyHost"), self.settings.value("/proxy/proxyPort"))
            if proxy.startswith("http://"):
                return proxy
            else:
                return "http://" + proxy
        else:
            return ""

    # Convert relative links to absolute link
    def buildurl(self, urlfragment):
        if not urlfragment.startswith("http"):
            return urljoin(str(self.onlineresource), urlfragment)
        return urlfragment


    # Build filename for downloaded file
    def buildfilename(self, url):
        parseresult = urlparse(url)
        if len(parseresult.query) == 0:
            path = parseresult.path
            filename = path[path.rfind("/") + 1:]
        else:
            # TODO: use Mime-Type
            extension = "ext"
            if url.lower().find("zip") > -1:
                extension = "zip"
            elif url.lower().find("tif") > -1:
                extension = "tiff"
            elif url.lower().find("png") > -1:
                extension = "png"
            elif url.lower().find("jpg") > -1:
                extension = "jpeg"
            elif url.lower().find("jpeg") > -1:
                extension = "jpeg"
            elif url.lower().find("gif") > -1:
                extension = "gif"
            elif url.lower().find("bmp") > -1:
                extension = "bmp"
            elif url.lower().find("gml") > -1:
                extension = "gml"
            elif url.lower().find("kml") > -1:
                extension = "kml"

            elif url.lower().find("wfs") > -1:
                extension = "gml"
            elif url.lower().find("wms") > -1:
                extension = "tiff"
            elif url.lower().find("wcs") > -1:
                extension = "tiff"
            filename = "{0}.{1}".format(
                ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(6)), extension)
        return filename

    #############################################################################################################
    # QHttp GetFeature-Request - http://stackoverflow.com/questions/6852038/threading-in-pyqt4
    #############################################################################################################

    def downloadFile(self, httplink, fileName):
        # self.lock_ui()
        url = QUrl(httplink)

        if QFile.exists(fileName):
            QFile.remove(fileName)

        self.outFile = QFile(fileName)
        if not self.outFile.open(QIODevice.WriteOnly):
            QMessageBox.critical(self, "Error",
                                 "Unable to save the file %s: %s." % (fileName, self.outFile.errorString()))
            self.outFile = None
            return

        self.httpRequestAborted = False
        self.progressBar.setVisible(True)

        self.startRequest(url, fileName)

    def startRequest(self, url, file_name):
        self.reply = self.qnam.get(QNetworkRequest(url))
        self.log_message('Downloading {0} to {1}'.format(url.toDisplayString(), str(file_name)))
        self.reply.finished.connect(self.httpRequestFinished)
        self.reply.readyRead.connect(self.httpReadyRead)
        self.reply.error.connect(self.errorOcurred)
        self.reply.downloadProgress.connect(self.updateDataReadProgress)

    def httpReadyRead(self):
        if self.outFile is not None:
            self.outFile.write(self.reply.readAll())

    # currently unused
    def cancelDownload(self):
        self.httpRequestAborted = True
        self.qnam.abort()
        self.close()

        self.progressBar.setMaximum(1)
        self.progressBar.setValue(0)
        self.reset_ui_download()

    def httpRequestFinished(self):
        self.log_message('Download finished')
        if self.checkForHTTPErrors():
            self.httpRequestAborted = True

        if self.httpRequestAborted:
            if self.outFile is not None:
                self.outFile.close()
                self.outFile.remove()
                self.outFile = None
            self.reply.deleteLater()
            self.reply = None
            self.progressBar.hide()
            self.reset_ui_download()
            return

        self.outFile.flush()
        self.outFile.close()

        self.progressBar.setMaximum(1)
        self.progressBar.setValue(1)

        self.lblMessage.setText("")
        self.downloadedfiles.append(str(self.outFile.fileName()))
        self.download_next()
        self.progressBar.setMaximum(1)
        self.progressBar.setValue(0)


    def readResponseHeader(self, responseHeader):
        # Check for genuine error conditions.
        if responseHeader.statusCode() not in (200, 300, 301, 302, 303, 307):
            QMessageBox.critical(self, "Error", "Download failed: %s." % responseHeader.reasonPhrase())
            self.httpRequestAborted = True
            self.qnam.abort()


    def updateDataReadProgress(self, bytesRead, totalBytes):
        if self.httpRequestAborted:
            return
        self.progressBar.setMaximum(totalBytes)
        self.progressBar.setValue(bytesRead)
        self.lblMessage.setText("Please wait while downloading - {0} Bytes downloaded!".format(str(bytesRead)))


class MessageHandler(QtXmlPatterns.QAbstractMessageHandler):
    def handleMessage(self, msg_type, description, identifier, source_location):
        if 'QgsMessageLog' in globals():
            QgsMessageLog.logMessage(str(msg_type) + description, "Wfs20Client", Qgis.Info)
