#! /usr/bin/env python
#
#	synctool_aggr.py	WJ109
#
#	group together output that is the same
#

import sys
import string


def aggregate(f):
	lines = f.readlines()
	if not lines:
		return

	lines = map(string.strip, lines)

	output_per_node = {}

	for line in lines:
		arr = string.split(line, ':')

		if len(arr) <= 1:
			print line
			continue

		node = arr[0]
		output = string.join(arr[1:], ':')

		if not output_per_node.has_key(node):
			output_per_node[node] = [output]
		else:
			output_per_node[node].append(output)

	nodes = output_per_node.keys()
	if not nodes:
		return

	nodes.sort()

	while len(nodes) > 0:
		node = nodes.pop(0)

		out = output_per_node[node]

		nodelist = [node]

		for node2 in nodes[:]:
			if out == output_per_node[node2]:
				nodelist.append(node2)
				del output_per_node[node2]
				nodes.remove(node2)

		print '%s:' % string.join(nodelist, ',')
		for line in out:
			print line


if __name__ == '__main__':
	aggregate(sys.stdin)


# EOB

