"""

Crawl listener for saving JSON files from crawl nodes

"""

import bcrypt
import os
import urllib
import requests
import json
import sys
import time
import re

URL_GET_CRAWL_DATA = 'http://crawl-server/get_crawl_data/?token=%s'
URL_FETCH_COMMAND = 'wget --header="Content-Encoding: gzip/deflate" %s -O %s/%s --output-file wget.log --rejected-log wget_error.log'
ROOT_FOLDER = 'crawldata'

REMOTE_PORT=8990

def get_crawl_token(token=None):
    """ Get token for the crawl """

    # Shared token
    if token == None:
        token = '0c437e9ba6ca7948362d4624b7bdc303'

    return bcrypt.hashpw(token, bcrypt.gensalt())

def listener():
    """ Listener routine """

    session_json = requests.get('http://crawl-server/handshake/?token=%s' % urllib.quote(get_crawl_token())).content.strip()

    try:
        session = json.loads(session_json)
        session_token = str(session.get('session_token', ''))
    except Exception, e:
        print 'Error parsing handshake response =>',e
        sys.exit(1)

    print 'SESSION TOKEN=>',session_token
    # First register and get session key
    # Goes in an endless loop - gets crawl config from HTTP
    # and starts crawlers.
    while True:
        fileinfo_json = requests.get(URL_GET_CRAWL_DATA % urllib.quote(get_crawl_token(session_token))).content.strip()
        
        if fileinfo_json != "{}":
            file_config = {}

            try:
                file_config = json.loads(fileinfo_json)
            except ValueError, e:
                print 'Error decoding JSON=>',e

            print 'Got JSON',file_config
            
            if len(file_config):
                paths = file_config['path']
                node_ip = file_config['node_ip']
                print 'Got',len(paths),'file paths.'
                # Fetch the files
                for fpath in paths:
                    url = 'http://%s:%d/%s' % (node_ip, REMOTE_PORT, fpath)
                    # Find local folder
                    if '_' in fpath:
                        idx1 = fpath.rindex('_')
                        match = re.search('(\.)\d+', fpath)
                        if match != None:
                            idx2 = match.start()
                        else:
                            idx2 = fpath.index('-', idx1)

                        folder = fpath[idx1+1:idx2]
                    else:
                        folder = 'generic'

                    folder = os.path.join(ROOT_FOLDER, folder)
                    if not os.path.exists(folder):
                        os.makedirs(folder)
                        
                    cmd = URL_FETCH_COMMAND % (url, folder, fpath)
                    print 'Saving URL',url
                    if os.system(cmd) == 0:
                        print '\tSaved URL',url

            time.sleep(5)

if __name__ == "__main__":
    print 'Listening'
    listener()
                    
                
