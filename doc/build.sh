#! /bin/sh

FILES="toc chapter1 chapter2 chapter3 chapter4 chapter5 thank_you single"

for file in $FILES
do
	echo "${file}.m4 -> ${file}.html"
	m4 ${file}.m4 >${file}.html
done

