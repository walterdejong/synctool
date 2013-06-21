#
#	synctool.aggr.py	WJ109
#
#   synctool Copyright 2013 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#
#	- aggregate: group together output that is the same
#

import os
import sys
import subprocess
import getopt

from synctool.lib import stderr


def aggregate(f):
	lines = f.readlines()
	if not lines:
		return

	lines = [x.strip() for x in lines]

	output_per_node = {}

	for line in lines:
		arr = line.split(':')

		if len(arr) <= 1:
			print line
			continue

		node = arr[0]
		output = ':'.join(arr[1:])

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

		print '%s:' % ','.join(nodelist)
		for line in out:
			print line


def run(cmd_arr):
	'''pipe the output through the aggregator
	Returns False on error, else True'''

	# simply re-run this command, but with a pipe

	if '-a' in cmd_arr:
		cmd_arr.remove('-a')

	if '--aggregate' in cmd_arr:
		cmd_arr.remove('--aggregate')

	try:
		f = subprocess.Popen(cmd_arr, shell=False, bufsize=4096,
				stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
	except OSError, reason:
		stderr('failed to run command %s: %s' % (cmd_arr[0], reason))
		return False

	with f:
		aggregate(f)

	return True


# EOB
