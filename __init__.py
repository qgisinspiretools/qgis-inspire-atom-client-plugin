"""
/***************************************************************************
 InspireAtomClient
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
 This script initializes the plugin, making it known to QGIS.
"""
def name():
    return "INSPIRE Atom Client"
def description():
    return "Client for INSPIRE Downloadservices based on ATOM-Feeds"
def category():
    return "Web"
def version():
    return "Version 0.6.0"
def icon():
    return "icon.png"
def qgisMinimumVersion():
    return "1.7.4"
def author():
    return "Juergen Weichand"
def email():
    return "juergen@weichand.de"
def classFactory(iface):
    # load InspireAtomClient class from file InspireAtomClient
    from inspireatomclient import InspireAtomClient
    return InspireAtomClient(iface)
