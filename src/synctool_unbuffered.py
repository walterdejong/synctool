#
#   synctool_unbuffered.py     WJ110
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2010
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#
#   - wrapper class for making stdout/stderr unbuffered
#	* the reason why: synctool-aggregate was suffering from duplicate output issues
#	  due to stdio buffering problems
#

class Unbuffered:
	def __init__(self, stream):
		self.stream = stream

	def write(self, data):
		self.stream.write(data)
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

