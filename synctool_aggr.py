#! /usr/bin/env python
#
#	aggregate.py	WJ109
#
#	- condense synctool output
#

import os
import sys
import string


def list_to_string(list):
	if not list:
		return ''

	list.sort()

	str = list[0]
	for elem in list[1:]:
		str = str + ' ' + elem

	return str


def sort_by_len(a, b):
	if len(a) < len(b):
		return -1

	if len(a) > len(b):
		return 1

	return 0


def aggregate(f):
	lines = f.readlines()
	if not lines:
		return

	lines = map(string.strip, lines)

	condensed = {}
	condensed_per_hostlist = {}

	for line in lines:
		arr = string.split(line, ':')
		if len(arr) <= 1:
			print line
			continue

		host = arr[0]
		comment = string.join(arr[1:], ':')
		comment = string.strip(comment)

		if not condensed.has_key(comment):
			condensed[comment] = []

		if not host in condensed[comment]:
			hostlist = list_to_string(condensed[comment])
			if condensed_per_hostlist.has_key(hostlist):
				del condensed_per_hostlist[hostlist]

			condensed[comment].append(host)

			hostlist = list_to_string(condensed[comment])
			if not condensed_per_hostlist.has_key(hostlist):
				condensed_per_hostlist[hostlist] = []

			condensed_per_hostlist[hostlist].append(comment)
#
#	print condensed output
#
	keys = condensed_per_hostlist.keys()
	keys.sort(sort_by_len)
	for hostlist in keys:
		print '%s:' % hostlist

		for comment in condensed_per_hostlist[hostlist]:
			print ' ', comment


if __name__ == '__main__':
	aggregate(sys.stdin)


# EOB
