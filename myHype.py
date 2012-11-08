#!/usr/bin/env python
from __future__ import division
import sys, json, time, threading, urlparse

import requests
from bs4 import BeautifulSoup

class Scraper(object):
    """Gets list of songs that could be downloaded"""
    extension_map = {'audio/mpeg' : 'mp3'}

    def __init__(self, path='popular/'):
        self.get_songs(path)

    def get_page(self, path):
        headers = {'User-Agent':'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.15 (KHTML, like Gecko) Chrome/24.0.1295.0 Safari/537.15'}
        self.session = requests.session()
        req = self.session.get(urlparse.urljoin('http://www.hypem.com/', path), headers=headers)
        return req.text

    def get_songs(self, path):
        results = BeautifulSoup(self.get_page(path))
        self.song_list = json.loads(results.find('script', id='displayList-data').get_text())['tracks']
        [track.__setitem__('rank', i + 1) for i, track in enumerate(self.song_list)]

    def request_song_url(self, song):
        host = 'http://hypem.com/serve/source/'
        sid, key = song['id'], song['key']
        request = urlparse.urljoin(host, sid + '/' +  key + '?_=' + str(int(time.time()*1000)))
        headers = {
            'X-Requested-With':'XMLHttpRequest',
            'Referer':'http://hypem.com/popular',
            'Host':'hypem.com',
        }
        for i in range(3):
            response = self.session.get(request, headers=headers)
            if response.status_code != 404:
                break
            time.sleep(1)
        else:
            raise requests.HTTPError
        return response.json['url']

    def get_song_file(self, song):
        """Returns song file object, used as 'filer' in thread"""
        return self.session.get(self.request_song_url(song), prefetch=False), song['song']

    def save_file(self, resp, filename, updater=None):
        """Returns song file object, used as 'saver' """
        size = int(resp.headers['content-length'])
        f = open(filename + '.' + self.extension_map[resp.headers['content-type']], 'w')
        bytes_read = 0
        while bytes_read < size:
            data = resp.raw.read(min(1024*64, size-bytes_read))
            bytes_read += len(data)
            f.write(data)
            if updater:
                updater(bytes_read/size)
            else:
                sys.stdout.write('%.f%%' % (bytes_read/size*100) + ' done\r')
                sys.stdout.flush()
        print
        f.close()

class Downloader(threading.Thread):
    tracker = {}

    def __init__(self, filer, saver, song):
        threading.Thread.__init__(self)
        self.song = song
        self.filer = filer
        self.saver = saver
        self.tracker[self.song['song']] = 0

    def update(self, percent):
        self.tracker[self.song['song']] = percent

    def run(self):
        try:
            response, filename = self.filer(self.song)
        except requests.HTTPError:
            print 'Sorry dude. ' + self.song['song'] + ' is not available.'
            self.tracker[self.song['song']] = -1
            print self.tracker
        else:
            self.saver(response, filename, self.update)

    @classmethod
    def printer(kls):
        while any([abs(v) != 1 for v in kls.tracker.values()]):
            for k,v in kls.tracker.items():
                if abs(v) != 1:
                    print k + ': ' + '%.f%%' % (v*100) + ' done\r'
                    time.sleep(.1)

def CLI():
    path = None
    if len(sys.argv) > 1:
        path = '/search/%s/' % sys.argv[1]
        scraper = Scraper(path)
    else:
        scraper = Scraper()
    for song in scraper.song_list:
        print str(song['rank']) + ') ' + song['artist']+ ' - ' +song['song']

    selections = raw_input('What numbers would you like to download? ')
    parsed = [int(x.strip())-1 for x in selections.split(',')]

    # for selected in parsed:
    #     print 'Downloading ' + scraper.song_list[selected]['artist'] + ' - ' +scraper.song_list[selected]['song']
    #     scraper.save_file(*scraper.get_song_file(scraper.song_list[selected]))

    threads = []
    for selected in parsed:
        newth = Downloader(scraper.get_song_file, scraper.save_file, scraper.song_list[selected])
        threads.append(newth)
        newth.start()

    Downloader.printer()

if __name__ == '__main__':
    CLI()
