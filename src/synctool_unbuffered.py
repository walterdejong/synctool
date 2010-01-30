#
#	unbuffered output
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

