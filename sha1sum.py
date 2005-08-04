#! /usr/bin/env python
#
#	sha1sum.py
#

import sha


def hexdigest(digest):
	hex = ''
	for i in range(0, 16):
		digit = int(digest[i])
		hex = '%s%02x' % (hex, digest[i])

	return hex


def sha1sum(filename):
	'''calculate SHA1 digest of file'''

	f = open(filename, 'r')
	if not f:
		return ''

	digest = sha.new()
	while 1:
		buf = f.read(16384)
		if not buf:
			break

		digest.update(buf)

	f.close()
	return digest.hexdigest()


if __name__ == '__main__':
	import sys

	for file in sys.argv[1:]:
		print '%s %s' % (sha1sum(file), file)

# EOB

