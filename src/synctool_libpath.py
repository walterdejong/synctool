#
#	synctool_libpath.py		WJ111
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2011
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#
#	- initializes sys.path so that synctool can find its libraries
#	- This module MUST be imported as FIRST module !!
#

import os
import sys
import string

# set the synctool libdir (without knowing the actual prefix)
arr = string.split(os.path.abspath(sys.argv[0]), '/')
arr.pop()					# strip command name
arr.pop()					# strip bindir
arr.append('lib')			# this will be the libdir
sys.path.insert(0, string.join(arr, '/'))
del arr


if __name__ == '__main__':
	print 'sys.path =', sys.path

# EOB
