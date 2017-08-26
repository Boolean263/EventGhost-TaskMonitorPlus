#!/bin/bash

PLUGNAME="iTunes"
SRCFILE="$PLUGNAME/__init__.py"
sed -n -E \
    -e '1,/^eg\.RegisterPlugin/d' \
    -e '200q' \
    -e 's/^ *//' \
    -e "s/ \"/ u'/" \
    -e "s/ '/ u'/" \
    -e "s/[\"'],/'/" \
    -e '/^(name|author|version|url|guid|description)/p' \
    $SRCFILE > info.py
VERSION=`grep ^version info.py | cut -d\' -f2`

zip -r $PLUGNAME-$VERSION.egplugin info.py $PLUGNAME \
    -x '*.pyc' -x '.*.sw*'
