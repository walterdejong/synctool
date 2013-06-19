#! /usr/bin/env python
#
#	synctool_template	WJ113
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2013
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

#	- auto replace "@VAR@" in the input text
#	- You can do the same thing with m4 or sed, but this one is nice and easy

import os
import sys
import string
import re
import getopt

PROGNAM = None

SPELLCHECK = re.compile(r'[A-Z_][A-Z0-9_]*')
PATTERN = re.compile(r'\@([A-Z_][A-Z0-9_]*)\@')


def spellcheck(name):
	'''Check for valid spelling of name
	Returns True if OK, False if not OK'''

	m = SPELLCHECK.match(name)
	if not m:
		return False

	if m.group(0) != name:
		return False

	return True


def subst(line):
	'''replace all occurrences of "@VAR@" with the value,
	where VAR is any environment variable
	Returns the resulting line of text'''

	for var in PATTERN.findall(line):
		if os.environ.has_key(var):
			line = line.replace('@' + var + '@', os.environ[var])

	return line


def template(filename):
	if not filename:
		print '%s: error: invalid filename' % PROGNAM
		sys.exit(-1)

	if filename == '-':
		f = sys.stdin
	else:
		try:
			f = open(filename)
		except IOError, reason:
			print "%s: failed to open '%s': %s" % (PROGNAM, filename, reason)
			sys.exit(-1)

	with f:
		for line in f:
			sys.stdout.write(subst(line))


def usage():
	print '''%s [-v VAR=VALUE] <input filename>
options:
  -h, --help               Display this information
  -v, --var VAR=VALUE      Set variable VAR to VALUE

synctool-template replaces all occurrences of "@VAR@" in the input
with "VALUE" prints the result to stdout. VAR may be given on the
command-line, but may also be an existing environment variable.

synctool-template by Walter de Jong <walter@heiho.net> (c) 2013
''' % PROGNAM


def get_options():
	if len(sys.argv) <= 1:
		usage()
		sys.exit(1)

	try:
		opts, args = getopt.getopt(sys.argv[1:], 'hv:',
			['help', 'var='])
	except getopt.error, (reason):
		print '%s: %s' % (PROGNAM, reason)
		usage()
		sys.exit(1)

	except getopt.GetoptError, (reason):
		print '%s: %s' % (PROGNAM, reason)
		usage()
		sys.exit(1)

	except:
		usage()
		sys.exit(1)

	if not args:
		print '%s: missing input filename' % PROGNAM
		sys.exit(1)

	if len(args) > 1:
		print '%s: too many arguments' % PROGNAM
		sys.exit(1)

	for opt, arg in opts:
		if opt in ('-h', '--help', '-?'):
			usage()
			sys.exit(1)

		if opt in ('-v', '--var'):
			try:
				(key, value) = string.split(arg, '=', 1)
			except ValueError:
				print '%s: syntax error in command-line' % PROGNAM
				sys.exit(1)

			else:
				if not spellcheck(key):
					print ('%s: syntax error: variables must be an '
							'uppercase word' % PROGNAM)
					sys.exit(1)

				# put it in the environment
				os.environ[key] = value

	if not args:
		print '%s: missing input file' % PROGNAM
		sys.exit(1)
	
	if len(args) > 1:
		print '%s: too many arguments' % PROGNAM
		sys.exit(1)

	# return the input filename
	return args[0]


if __name__ == '__main__':
	PROGNAM = os.path.basename(sys.argv[0])

	INPUT_FILE = get_options()

	template(INPUT_FILE)


# EOB
