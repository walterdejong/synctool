#! /usr/bin/env python
#
#	md5sum.py
#

import md5


#
#	note: in Python version 1, the md5.hexdigest() method did not yet exist
#
def hexdigest(digest):
	hex = ''
	for i in range(0, 16):
		digit = int(digest[i])
		hex = '%s%02x' % (hex, digest[i])

	return hex


def md5sum(filename):
	'''calculate MD5 digest of file'''

	f = open(filename, 'r')
	if not f:
		return ''

	digest = md5.new()
	while 1:
		buf = f.read(16384)
		if not buf:
			break

		digest.update(buf)

	f.close()
#	print 'TD: md5 digest: %s' % digest.hexdigest()
	return digest.digest()


if __name__ == '__main__':
	import sys

	for file in sys.argv[1:]:
		print '%s %s' % (md5sum(file), file)

# EOB

