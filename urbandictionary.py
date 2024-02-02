#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright © 2020 Saeed Rasooli <saeed.gnu@gmail.com> (ilius)
#
# This program is a free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program. Or on Debian systems, from /usr/share/common-licenses/GPL
# If not, see <http://www.gnu.org/licenses/gpl.txt>.


import gzip
import html
import os
import re
from hashlib import sha1
from os import listdir, makedirs
from os.path import dirname, isdir, isfile, join
from queue import Queue
from threading import Thread
from time import sleep, strftime

import requests


def print_tm(msg):
	print(f"{strftime('%F %T')} {msg}")


useAPI = False

host = "urbandictionary.com"
apiHost = "api.urbandictionary.com"

# host = socket.gethostbyname(host)
print_tm(f"Using host {host}")


homeDir = os.getenv("HOME")

if os.sep == "/":
	cacheDir = "/media/D/urbandictionary"
elif os.sep == "\\":
	cacheDir = "D:\\urbandictionary"
else:
	raise OSError("could not detect OS")


browseDir = join(cacheDir, "browse")
dictDir = join(cacheDir, "dict.crawler")

if not isdir(browseDir):
	makedirs(browseDir)
if not isdir(dictDir):
	makedirs(dictDir)


def fetchURL(url: str):
	while True:
		try:
			res = requests.get(url)
		except requests.exceptions.ConnectionError as e:
			print_tm(f"failed: {e} for {url}")
			sleep(0.5)
			continue
		if res.ok:
			return res.text
		print_tm(f"failed: {res} for {url}")
		sc = res.status_code
		if sc == 403:
			sleep(5)
			continue
		if sc >= 400 and sc < 500:
			return f"status_code={sc}"
		return None
		# sleep(0.1)


def nextWordFromBrowseText(text: str) -> str:
	i = text.find('<a rel="next"')
	if i == -1:
		return None
	j = text.find('href="', i)
	if j == -1:
		return None
	k = text.find("word=", j + 6)
	if k == -1:
		return None
	end = text.find('"', k + 5)
	if end == -1:
		return None
	return text[k + 5 : end]


def fetchBrowse(word: str) -> "(str, str)":
	"""
	returns (text, nextWord)
	"""
	fpath = join(browseDir, word.encode("utf-8").hex())
	if isfile(fpath):
		with open(fpath, encoding="utf-8") as _file:
			text = _file.read()
		print_tm(f"loaded: {fpath} for word {word}")
	else:
		text = fetchURL(
			f"https://{host}/browse.php?word={word}",
		)
		with open(fpath, "w", encoding="utf-8") as _file:
			_file.write(text)
		print_tm(f"saved: {fpath} for word {word}")
	nextWord = nextWordFromBrowseText(text)
	return text, nextWord


def fetchBrowseAll(firstWord: str):
	word = firstWord
	while word:
		text, word = fetchBrowse(word)


def filePathFromWord(b_word: bytes) -> str:
	bw = b_word.lower()
	if len(bw) <= 2:
		return bw.hex()
	if len(bw) <= 4:
		return join(
			bw[:2].hex() + ".d",
			bw[2:].hex(),
		)
	return join(
		bw[:2].hex() + ".d",
		bw[2:4].hex() + ".d",
		bw[4:8].hex() + "-" + sha1(b_word).hexdigest()[:8],
	)


def downloadWord(word: str):
	fpath = join(dictDir, filePathFromWord(word.encode("utf-8")))
	if isfile(fpath + ".gz") or isfile(fpath):
		# print_tm(f"file exists: {fpath}")
		return 0
	text = fetchURL(
		f"http://{apiHost}/v0/define?term={word}"
		if useAPI
		else f"https://{host}/define.php?term={word}",
	)
	if text is None:
		return 0
	parent = dirname(fpath)
	if not isdir(parent):
		makedirs(parent)
	with gzip.open(fpath + ".gz", mode="wt", encoding="utf-8") as _file:
		_file.write(text)
	# print_tm(f"file saved: {fpath}")
	return 1


re_define = re.compile(
	r'<a href="/define.php\?term=(.*?)">',
)


def fetchWordsOfBrowseFile(fname, workerI):
	with open(join(browseDir, fname), encoding="utf-8") as _file:
		text = _file.read()
	count = 0
	for word in re_define.findall(text):
		count += downloadWord(html.unescape(word))
	if count > 0:
		print_tm(
			f'worker{workerI}: downloaded {count} words'
			f' from "{bytes.fromhex(fname).decode("utf-8")}"',
		)


def workerLoop(workerI, q):
	"""
	This is the worker thread function.
	It processes items in the queue one after
	another.  These daemon threads go into an
	infinite loop, and only exit when
	the main thread ends.
	"""
	while True:
		try:
			browseFname = q.get()
			fetchWordsOfBrowseFile(browseFname, workerI)
			q.task_done()
		except Exception as e:
			print_tm(e)


num_workers = 8
max_queue_size = num_workers * 2
queue = Queue(maxsize=max_queue_size)

if __name__ == "__main__":
	# Set up some threads to fetch the enclosures
	for workerI in range(num_workers):
		worker = Thread(
			target=workerLoop,
			args=(
				workerI,
				queue,
			),
		)
		worker.setDaemon(True)
		worker.start()
	for fname in listdir(browseDir):
		queue.put(fname)
		# print_tm(f"queue size: {queue.qsize()}")
