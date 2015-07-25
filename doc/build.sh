#! /bin/sh
#
#	build.sh    WJ113
#
#	- build HTML documentation from markdown
#

FILES="toc chapter1 chapter2 chapter3 chapter4 chapter5 chapter6 thank_you"

for file in $FILES
do
	echo "${file}.md -> ${file}.html"
	( cat header.html ;
	cat ${file}.md | markdown | smartypants ;
	cat footer.html ) > ${file}.html
done

# generate single page document
echo "writing single.html"

( cat header.html ;
for file in $FILES ;
do
	cat ${file}.md | markdown | smartypants ;
	cat line.html ;
done ;
cat footer.html ) > single.html

# EOB
