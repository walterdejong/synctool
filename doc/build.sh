#! /bin/bash

FILES="toc.m4 chapter1.m4 chapter2.m4 chapter3.m4 chapter4.m4 chapter5.m4 single.m4"

for file in $FILES
do
	html="${file%%.m4}.html"
	echo "$file -> $html"
	m4 $file >$html
done

