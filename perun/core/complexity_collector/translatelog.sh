#!/bin/sh
if test ! -f "$1"
then
 echo "Error: executable $1 does not exist."
 exit 1
fi
if test ! -f "$2"
then
 echo "Error: trace log $2 does not exist."
 exit 1
fi
EXECUTABLE="$1"
TRACELOG="$2"
while read LINETYPE FADDR CTIME; do
 FNAME="$(addr2line -f -e ${EXECUTABLE} ${FADDR}|head -1|c++filt)"
 if test "${LINETYPE}" = "i"
 then
 echo "Enter ${FNAME} ${CTIME}"
 fi
 if test "${LINETYPE}" = "o"
 then
 echo "Exit ${FNAME} ${CTIME}"
 fi
done < "${TRACELOG}"
