#!/usr/bin/env python
from __future__ import division
import sys
import json
import time

from bs4 import BeautifulSoup
import requests
import threading

class Scraper(object):
	extension_map = {
		'audio/mpeg' : 'mp3',
	}

	def __init__(self, path='popular/'):
		self.path = path
		self.get_songs()

	def get_page(self):
		headers = {'User-Agent':'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.15 (KHTML, like Gecko) Chrome/24.0.1295.0 Safari/537.15'}
		self.session = requests.session()
		req = self.session.get('http://www.hypem.com/'+self.path, headers=headers)
		return req.text

	def get_songs(self):
		results = BeautifulSoup(self.get_page())
		song_map = {}
		page_data = json.loads(results.find('script', id='displayList-data').get_text())['tracks']
		self.song_list = []
		for i, track in enumerate(page_data):
			song = {}
			atts_we_want = ['artist', 'key', 'id', 'song']
			song = {att: track[att] for att in atts_we_want}
			song['rank'] = i + 1
			self.song_list.append(song)

	def request_song_url(self, song):
		host = 'http://hypem.com/serve/source/'
		sid = song['id']
		key = song['key']
		t = str(int(time.time()*1000))
		request = host + sid + '/' + key + '?_=' + t
		headers = {
			'X-Requested-With':'XMLHttpRequest',
			'Referer':'http://hypem.com/popular',
			'Host':'hypem.com',
		}
		response = self.session.get(request, headers=headers)
		if response.status_code == 404:
			time.sleep(1)
			if self.session.get(request, headers=headers).status_code == 404:
				raise requests.HTTPError
		return response.json['url']

	#filer
	def get_song_file(self, song):
		return self.session.get(self.request_song_url(song), prefetch=False), song['song']

	#saver
	def save_file(self, resp, filename, updater=None):
		ext = self.extension_map[resp.headers['content-type']]
		size = int(resp.headers['content-length'])
		f = open(filename + '.' + ext, 'w')
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
	# 	print 'Downloading ' + scraper.song_list[selected]['artist'] + ' - ' +scraper.song_list[selected]['song']
	# 	scraper.save_file(*scraper.get_song_file(scraper.song_list[selected]))

	threads = []
	for selected in parsed:
		newth = Downloader(scraper.get_song_file, scraper.save_file, scraper.song_list[selected])
		threads.append(newth)
		newth.start()

	Downloader.printer()

if __name__ == '__main__':
	CLI()
