#! /usr/bin/env python
#
#	aggregate.py	WJ109
#
#	- condense synctool output
#

import os
import sys
import string


def aggregate(f):
	lines = f.readlines()
	if not lines:
		return

	lines = map(string.strip, lines)

	condensed = {}

	for line in lines:
		arr = string.split(line, ':')
		if len(arr) <= 1:
			print line
			continue

		host = arr[0]
		comment = string.join(arr[1:], ':')

		if not condensed.has_key(comment):
			condensed[comment] = []

		if not host in condensed[comment]:
			condensed[comment].append(host)
#
#	print condensed output
#
	for comment in condensed.keys():
		for host in condensed[comment]:
			print host,

		print ':', string.strip(comment)


if __name__ == '__main__':
	aggregate(sys.stdin)


# EOB
