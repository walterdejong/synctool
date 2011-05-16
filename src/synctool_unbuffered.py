#
#	synctool_unbuffered.py	WJ110
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2011
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#
#	- unbuffered output, needed for synctool_master
#

class Unbuffered:
	def __init__(self, stream):
		self.stream = stream

	def write(self, data):
		self.stream.write(data)

		if len(data) >= 1 and (data[-1] == '\n' or data[-1] == '\r'):
			self.stream.flush()

	def flush(self):
		self.stream.flush()

	def fileno(self):
		return self.stream.fileno()

	def close(self):
		self.stream.close()

	def __getattr__(self, attr):
		return getattr(self.stream, attr)


if __name__ == '__main__':
	import sys

	sys.stdout = Unbuffered(sys.stdout)

	print 'hello, unbuffered world'

# EOB

