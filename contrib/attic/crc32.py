#! /usr/bin/env python
#
#	CRC32	WJ103
#

import zlib


def crc32(filename):
	'''calculate CRC-32 checksum of file'''

	f = open(filename, 'r')
	if not f:
		return ''

	crc = 0
	while 1:
		buf = f.read(16384)
		if not buf:
			break

		crc = zlib.crc32(buf, crc)

	f.close()

	str_crc = '%x' % crc
#	print 'TD: CRC32 : %s' % str_crc
	return str_crc


if __name__ == '__main__':
	import sys

	for file in sys.argv[1:]:
		print '%s %s' % (crc32(file), file)

# EOB

