#
#	synctool.aggr.py	WJ109
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2013
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#
#	- aggregate: group together output that is the same
#

import os
import sys
import string
import getopt

import synctool.lib


# popen() calls stderr()
def stderr(msg):
	print msg


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


def run(cmd_args):
	'''pipe the output through the aggregator
	Returns False on error, else True'''

	# simply re-run this command, but with a pipe

	if '-a' in cmd_args:
		cmd_args.remove('-a')

	if '--aggregate' in cmd_args:
		cmd_args.remove('--aggregate')

	with synctool.lib.popen(cmd_args) as f:
		if not f:
			stderr('failed to run %s' % cmd_args[0])
			return False

		aggregate(f)

	return True


# EOB
