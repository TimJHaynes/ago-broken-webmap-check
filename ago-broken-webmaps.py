"""
Script: AGO Broken Item Check
Version: 1.0
Created: 180322
Created By: Paul R. Sesink Clee
Updated:
Updated By:
Summary:
"""

# region Import Libraries
from datetime import date, datetime, timedelta
import csv
import logging
import operator
import requests
import sys
import time
import traceback
import os
#import win32com.client as win32
# endregion

startingTime = datetime.now()

# Request token from ArcGIS Online
def tokengenerator():
    tokenrequest = requests.post(urlOrg + '/sharing/rest/generateToken?', data={'username': user, 'password': password, 'referer': 'https://www.arcgis.com', 'f': 'json', 'expiration': 20160})
    return tokenrequest.json()['token']

# Simple class for attributing items as they are read
class Items:
    def __init__(self, json):
        self.type = json['type']
        self.id = json['id']
        self.title = json['title']
        self.name = json['name']
        self.access = json['access']
        self.url = urlOrg + '/home/item.html?id={0}'.format(self.id)
        self.created = time.strftime('%m/%d/%Y', time.localtime(int(json['created'])/1000))
        self.modified = time.strftime('%m/%d/%Y', time.localtime(int(json['modified'])/1000))
        self.size = round((int(json['size']) / 1024 ** 2.0), 2)

endTime = int(time.time()) * 1000
startTime = endTime - 5184000000
period = '1d'

# setting parameters for AGO login, report generation, and tokens
urlOrg = 'https://XXXXXXXX.arcgis.com'
user = 'username'
password = 'password'
directory = 'filepath to output directory'
reportCSV = directory + 'reportname.csv'
archiveCSV = directory + 'reportname_' + str(date.today().strftime('%Y%m%d')) + '.csv'
token = tokengenerator()
print('token is: ' + token)

# archiving old report if one exists
if os.path.isfile(reportCSV) == True:
    print('Archiving previous report...')
    if os.path.isfile(archiveCSV):
        os.remove(archiveCSV)
    os.rename(reportCSV, archiveCSV)

# creating list of AGO users
listAGOUsers = []
r = requests.get('{0}/sharing/rest/portals/self/users?start=1&num=10&sortField=fullname&sortOrder=asc&f=json&token={1}'.format(urlOrg, token))
numusers = r.json()['total']
if numusers % 100 > 0:
    _range = (round(numusers / 100)) + 1
else:
    _range = (round(numusers / 100))
start = 1
for iterUsers in range(_range):
    r = requests.get('{0}/sharing/rest/portals/self/users?start={1}&num=100&sortField=fullname&sortOrder=asc&f=json&token={2}'.format(urlOrg, start, token))
    jsonusers = r.json()['users']
    start += 100
    for user in jsonusers:
        if user['lastLogin'] != -1:
            listAGOUsers.append(user['username'])
print('List of all {0} AGO Users in the org:'.format(len(listAGOUsers)))
print(listAGOUsers)
#listAGOUsers =
#print(listAGOUsers)

# creating report csv
with open(reportCSV, 'w', newline = '') as openCSV:
    writeCSV = csv.writer(openCSV, delimiter=',', quoting=csv.QUOTE_ALL)
    writeCSV.writerow(['Owner', 'Folder', 'WebmapID', 'WebmapURL', 'BrokenItemNAME', 'BrokenItemID', 'BrokenItemURL', 'Access', 'Comment'])

    # getting list of items in users content root
    for user in listAGOUsers:
        print(user + ' - home')
        r = requests.get('{0}/sharing/rest/content/users/{1}?f=json&token={2}'.format(urlOrg, user, token))
        listfolders = r.json()['folders']
        items = r.json()['items']


        # identifying webmaps in user root folders
        for _item in items:
            token = token
            j = Items(_item)
            _webmapURL = urlOrg + '/home/item.html?id=' + j.id

            # finding web map contents
            if j.type == 'Web Map':
                webmap = requests.get('{0}/sharing/rest/content/items/{1}/data?f=json&token={2}'.format(urlOrg, j.id, token))
                listLayers = webmap.json()['operationalLayers']
                listBasemaps = webmap.json()['baseMap']['baseMapLayers']
                sharing = _item['access']

                # checking to see if operational layer items exist
                for _layer in listLayers:
                    try:
                        l = _layer['itemId']
                        if 'itemId' in _layer:
                            layer = requests.get('{0}/sharing/rest/content/items/{1}?f=json&token={2}'.format(urlOrg, l, token))
                            # adding bad links to report
                            if 'error' in layer.json():
                                try:
                                    layer = requests.get(_layer['url'] + '?f=pjson')
                                    if 'error' in layer.json():
                                        print('Found bad link...')
                                        _layerURL = urlOrg + '/home/item.html?id=' + l
                                        writeCSV.writerow([user, 'home', j.id, _webmapURL, _layer['title'], l, _layerURL, sharing, 'Failed Second JSON check', '1'])
                                        print(_layer['url'] + '?f=pjson')
                                    else:
                                        pass
                                except:
                                    print('Found bad link...')
                                    _layerURL = urlOrg + '/home/item.html?id=' + l
                                    writeCSV.writerow([user, 'home', j.id, _webmapURL, _layer['title'], l, _layerURL, sharing, '', '2'])
                            else:
                               pass
                    except:
                        l = None
                        try:
                            e = requests.get(_layer['url'] + '?f=pjson')
                            if 'error' in e.json():
                                if e.json()['error']['code'] == 499:
                                    try:
                                        e = requests.get(_layer['url'] + '?f=pjson&token=' + token)
                                        if 'error' in e.json():
                                            writeCSV.writerow([user, 'home', j.id, _webmapURL, _layer['title'], '', _layer['url'], sharing, 'External link - Inaccessible', '3'])
                                        else:
                                            pass
                                    except:
                                        _webmapURL = urlOrg + '/home/item.html?id=' + j.id
                                        writeCSV.writerow([user, 'home', j.id, _webmapURL, _layer['title'], '', '', sharing, 'External link - Inaccessible - Error 499', '4'])
                                elif e.json()['error']['code'] == 403:
                                    print('Found inaccessible external link...')
                                    _layerURL = _layer['url']
                                    writeCSV.writerow([user, 'home', j.id, _webmapURL, _layer['title'], 'INACCESSIBLE', _layerURL, sharing, 'External link - Inaccessible - Error 403', '5'])
                                else:
                                    print('Found bad EXTERNAL link...')
                                    _layerURL = _layer['url']
                                    writeCSV.writerow([user, 'home', j.id, _webmapURL, _layer['title'], l, _layerURL, sharing, 'External link - Inaccessible', '6'])
                            else:
                                pass
                        except:
                            try:
                                z = _layer['featureCollection']
                            except:
                                try:
                                    e_url = _layer['url']
                                    writeCSV.writerow([user, 'home', j.id, _webmapURL, _layer['title'], '', e_url, sharing, 'External link - Inaccessible', '7'])
                                except:
                                    e_url = 'URL UNAVAILABLE'
                                    writeCSV.writerow([user, 'home', j.id, _webmapURL, _layer['title'], '', '', sharing, 'URL Unavailable', '8'])

                for _basemap in listBasemaps:
                    try:
                        basemap = requests.get(_basemap['url'] + '?f=pjson&token=' + token)
                        #basemap = requests.get(_basemap['url'])
                        if 'error' in basemap.json():
                            print('Found bad Basemap...')
                            writeCSV.writerow([user, 'home', j.id, _webmapURL, _basemap['title'], '', _basemap['url'], sharing, 'Missing Basemap', '9.1'])
                        else:
                            pass
                    except:
                        try:
                            basemap = requests.get(_basemap['url'] + '?f=pjson')
                            if 'error' in basemap.json():
                                print('Found bad Basemap...')
                                try:
                                    basemap = requests.get(_basemap['url'])
                                    writeCSV.writerow([user, 'home', j.id, _webmapURL, _basemap['title'], '', _basemap['url'], sharing, 'Missing Basemap', '9.2'])
                                except:
                                    # some externally hosted basemaps do not have a 'title' in jsons
                                    writeCSV.writerow([user, 'home', j.id, _webmapURL, 'title missing', '', _basemap['url'], sharing, 'Missing Basemap', '9.3'])
                        except:
                            try:
                                #basemap = requests.get(_basemap['url'] + '?f=pjson&token=' + token)
                                basemap = requests.get(_basemap['url'])
                                if 'error' in basemap.json():
                                    print('Found bad Basemap...')
                                    writeCSV.writerow([user, 'home', j.id, _webmapURL, _basemap['title'], '', _basemap['url'], sharing, 'Missing Basemap', '9.4'])
                                else:
                                    pass
                            except:
                                try:
                                    basemap = requests.get(_basemap['styleUrl'])
                                    if 'error' in basemap.json():
                                        print('Found bad Basemap...')
                                        writeCSV.writerow([user, 'home', j.id, _webmapURL, _basemap['title'], '', _basemap['styleUrl'], sharing, 'Missing Basemap', '9.5'])
                                    else:
                                        pass
                                except:
                                    writeCSV.writerow([user, 'home', j.id, _webmapURL, 'bad basemap', '', 'no url', sharing, 'Basemap - missing url and styleUrl', '9.6'])

        # looking through webmaps in user content folders
        for folder in listfolders:
            print(user + ' - ' + folder['title'])
            folderName = folder['title']
            r = requests.get('{0}/sharing/rest/content/users/{1}/{2}?f=json&token={3}'.format(urlOrg, user, folder['id'], token))
            folderItems = r.json()['items']
            try:
                for _item in folderItems:
                    token = token
                    f = Items(_item)
                    _webmapURL = urlOrg + '/home/item.html?id=' + f.id

                    # finding web map contents
                    if f.type == 'Web Map':
                        webmap = requests.get('{0}/sharing/rest/content/items/{1}/data?f=json&token={2}'.format(urlOrg, f.id, token))
                        listLayers = webmap.json()['operationalLayers']
                        listBasemaps = webmap.json()['baseMap']['baseMapLayers']
                        sharing = _item['access']

                        # checking to see if operational layer items exist
                        for _layer in listLayers:
                            try:
                                l = _layer['itemId']
                                if 'itemId' in _layer:
                                    layer = requests.get('{0}/sharing/rest/content/items/{1}?f=json&token={2}'.format(urlOrg, l, token))

                                    # adding bad links to report
                                    if 'error' in layer.json():
                                        try:
                                            layer = requests.get(_layer['url'] + '?f=pjson')
                                            if 'error' in layer.json():
                                                print('Found bad link...')
                                                _layerURL = urlOrg + '/home/item.html?id=' + l
                                                writeCSV.writerow([user, folderName, f.id, _webmapURL, _layer['title'], l, _layerURL, sharing, 'Failed Second JSON check', '13'])
                                                print(_layer['url'] + '?f=pjson')
                                            else:
                                                pass
                                        except:
                                            print('Found bad link...')
                                            _layerURL = urlOrg + '/home/item.html?id=' + l
                                            writeCSV.writerow([user, folderName, f.id, _webmapURL, _layer['title'], l, _layerURL, sharing, '', '14'])
                                    else:
                                        pass
                            except:
                                l = None
                                try:
                                    e = requests.get(_layer['url'] + '?f=pjson')
                                    if 'error' in e.json():
                                        if e.json()['error']['code'] == 499:
                                            try:
                                                e = requests.get(_layer['url'] + '?f=pjson&token=' + token)
                                                if 'error' in e.json():
                                                    writeCSV.writerow([user, folderName, f.id, _webmapURL, _layer['title'], '', _layer['url'], sharing, 'External link - Inaccessible', '15'])
                                                else:
                                                    pass
                                            except:
                                                writeCSV.writerow([user, folderName, f.id, _webmapURL, _layer['title'], '', '', sharing, 'External link - Inaccessible - Error 499', '16'])
                                        elif e.json()['error']['code'] == 403:
                                            print('Found inaccessible external link...')
                                            _layerURL = _layer['url']
                                            writeCSV.writerow([user, folderName, f.id, _webmapURL, _layer['title'], '', _layerURL, sharing, 'External link - Inaccessible - Error 403', '17'])
                                        else:
                                            print('Found bad EXTERNAL link...')
                                            _layerURL = _layer['url']
                                            writeCSV.writerow([user, folderName, f.id, _webmapURL, _layer['title'], l, _layerURL, sharing, 'External link - Inaccessible', '18'])
                                    else:
                                        pass
                                except:
                                    try:
                                        z = _layer['featureCollection']
                                    except:
                                        try:
                                            e_url = _layer['url']
                                            writeCSV.writerow([user, folderName, f.id, _webmapURL, _layer['title'], '', e_url, sharing, 'External link - Inaccessible', '19'])
                                        except:
                                            e_url = 'URL UNAVAILABLE'
                                            writeCSV.writerow( [user, folderName, f.id, _webmapURL, _layer['title'], '', '', sharing, 'URL Unavailable', '20'])

                        for _basemap in listBasemaps:
                            try:
                                basemap = requests.get(_basemap['url'] + '?f=pjson&token=' + token)
                                if 'error' in basemap.json():
                                    print('Found bad Basemap...')
                                    writeCSV.writerow([user, 'home', f.id, _webmapURL, _basemap['title'], '', _basemap['url'], sharing, 'Missing Basemap', '20.1'])
                                else:
                                    pass
                            except:
                                try:
                                    basemap = requests.get(_basemap['url'] + '?f=pjson')
                                    if 'error' in basemap.json():
                                        print('Found bad Basemap...')
                                        try:
                                            basemap = requests.get(_basemap['url'])
                                            writeCSV.writerow([user, 'home', f.id, _webmapURL, _basemap['title'], '', _basemap['url'], sharing, 'Missing Basemap', '20.2'])
                                        except:
                                            # some externally hosted basemaps do not have a 'title' in jsons
                                            writeCSV.writerow([user, 'home', f.id, _webmapURL, 'title missing', '', _basemap['url'], sharing, 'Missing Basemap', '20.3'])
                                except:
                                    try:
                                        # basemap = requests.get(_basemap['url'] + '?f=pjson&token=' + token)
                                        basemap = requests.get(_basemap['url'])
                                        if 'error' in basemap.json():
                                            print('Found bad Basemap...')
                                            writeCSV.writerow([user, 'home', f.id, _webmapURL, _basemap['title'], '', _basemap['url'], sharing, 'Missing Basemap', '20.4'])
                                        else:
                                            pass
                                    except:
                                        try:
                                            basemap = requests.get(_basemap['styleUrl'])
                                            if 'error' in basemap.json():
                                                print('Found bad Basemap...')
                                                writeCSV.writerow([user, 'home', f.id, _webmapURL, _basemap['title'], '', _basemap['styleUrl'], sharing, 'Missing Basemap', '20.5'])
                                            else:
                                                pass
                                        except:
                                            writeCSV.writerow([user, 'home', f.id, _webmapURL, 'bad basemap', '', 'no url', sharing, 'Basemap - missing url and styleUrl', '20.6'])
            except:
                print('oops..')
                print(traceback.format_exc())
                sys.exit(1)

runTime = datetime.now() - startingTime
print('Total runtime: ' + str(runTime))
