"""
/***************************************************************************
 WFS 2.0 Library
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



class Dataset(object):

    def __init__(self, id):
        self.__id__ = id;
        self.__title = ""
        self.__summary = ""
        self.__link_metadata = ""
        self.__link_subfeed = ""
        self.__rights = ""
 

    def getId(self):
        return self.__id__

    def getTitle(self):
        return self.__title

    def getSummary(self):
        return self.__summary

    def getLinkMetadata(self):
        return self.__link_metadata

    def getLinkSubfeed(self):
        return self.__link_subfeed

    def getRights(self):
        return self.__rights

    def setTitle(self, title):
        self.__title = title

    def setSummary(self, summary):
        self.__summary = summary

    def setLinkMetadata(self, link_metadata):
        self.__link_metadata = link_metadata

    def setLinkSubfeed(self, link_subfeed):
        self.__link_subfeed = link_subfeed

    def setRights(self, rights):
        self.__rights = rights


class DatasetRepresentation(object):

    def __init__(self, id):
        self.__id__ = id
        self.__title = ""
        self.__epsg = ""
        self.__language = ""
        self.__files = []

    def getId(self):
        return self.__id__

    def getTitle(self):
        return self.__title

    def getEpsg(self):
        return self.__epsg

    def getLanguage(self):
        return self.__language

    def getFiles(self):
        return self.__files

    def setTitle(self, title):
        self.__title = title

    def setEpsg(self, epsg):
        self.__epsg = epsg

    def setLanguage(self, language):
        self.__language = language

    def setFiles(self, files):
        self.__files = files

