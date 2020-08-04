#!/usr/bin/env python3

import os
from os import makedirs, listdir
from os.path import join, isdir, isfile, dirname
import requests
import html
import re
from hashlib import sha1
from time import sleep
from queue import Queue
from threading import Thread

homeDir = os.getenv("HOME")
cacheDir = join(homeDir, ".cache", "urbandictionary")

browseDir = join(cacheDir, "browse")
dictDir = join(cacheDir, "dict")

if not isdir(browseDir):
	makedirs(browseDir)
if not isdir(dictDir):
	makedirs(dictDir)

browseFirstWord = "https://www.urbandictionary.com/browse.php?word=a"

def fetchURL(url: str):
	while True:
		try:
			res = requests.get(url)
		except requests.exceptions.ConnectionError as e:
			print(f"failed: {e} for {url}")
			sleep(0.5)
			continue
		if res.ok:
			return res.text
		print(f"failed: {res} for {url}")
		# sc = res.status_code
		#if sc >= 400 and sc < 500:
		return
		#sleep(0.1)


def nextWordFromBrowseText(text: str) -> str:
	i = text.find('<a rel="next"')
	if i == -1:
		return None
	j = text.find('href="', i)
	if j == -1:
		return None
	k = text.find('word=', j + 6)
	if k == -1:
		return None
	end = text.find('"', k + 5)
	if end == -1:
		return None
	return text[k + 5:end]


def fetchBrowse(word: str) -> "Tuple[str, str]":
	"""
		returns (text, nextWord)
	"""
	fpath = join(browseDir, word.encode("utf-8").hex())
	if isfile(fpath):
		with open(fpath, "r", encoding="utf-8") as _file:
			text = _file.read()
		print(f"loaded: {fpath} for word {word}")
	else:
		text = fetchURL(
			f"https://www.urbandictionary.com/browse.php?word={word}",
		)
		with open(fpath, "w", encoding="utf-8") as _file:
			_file.write(text)
		print(f"saved: {fpath} for word {word}")
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
	if isfile(fpath):
		#print(f"file exists: {fpath}")
		return
	text = fetchURL(
		f"https://www.urbandictionary.com/define.php?term={word}",
	)
	if text is None:
		return
	parent = dirname(fpath)
	if not isdir(parent):
		makedirs(parent)
	with open(fpath, mode="w", encoding="utf-8") as _file:
		_file.write(text)
	#print(f"file saved: {fpath}")


re_define = re.compile(
	'<a href="/define.php\?term=(.*?)">',
)

def fetchWordsOfBrowseFile(fname, workerI):
	with open(join(browseDir, fname), "r", encoding="utf-8") as _file:
		text = _file.read()
	count = 0
	for word in re_define.findall(text):
		downloadWord(html.unescape(word))
		count += 1
	print(
		f'worker{workerI}: downloaded {count} words'
		f' from "{bytes.fromhex(fname).decode("utf-8")}"'
	)


def workerLoop(workerI, q):
    """This is the worker thread function.
    It processes items in the queue one after
    another.  These daemon threads go into an
    infinite loop, and only exit when
    the main thread ends.
    """
    while True:
        #print(f'{workerI}: Looking for the next enclosure')
        browseFname = q.get()
        #print(f'{workerI}: Downloading: {browseFname}')
        fetchWordsOfBrowseFile(browseFname, workerI)
        q.task_done()


num_workers = 64
max_queue_size = num_workers * 2
queue = Queue(maxsize=max_queue_size)

if __name__ == "__main__":
	# Set up some threads to fetch the enclosures
	for workerI in range(num_workers):
		worker = Thread(target=workerLoop, args=(workerI, queue,))
		worker.setDaemon(True)
		worker.start()
	for fname in listdir(browseDir):
		queue.put(fname)
		#print(f"queue size: {queue.qsize()}")		


