#!/bin/sh
#
# Copyright (C) 2008-2015 CEA/DAM
#
# This file is part of ClusterShell.
#
# ClusterShell is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# ClusterShell is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with ClusterShell; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

if [ -z "$2" ]; then
    echo "usage: $0 <version> <dist>"
    echo "example: $0 1.2.3 el6"
    exit 1
fi

VERS=$1
DIST=".$2"

PKGNAME=clustershell-$VERS
TMPROOT=/tmp/clustershell-mkrpm
TMPDIR=$TMPROOT/build/$PKGNAME

rm -rf $TMPROOT

echo "Building tarball..."

install -d $TMPDIR/lib/ClusterShell || exit 1
install -d $TMPDIR/lib/ClusterShell/CLI
install -d $TMPDIR/lib/ClusterShell/Engine
install -d $TMPDIR/lib/ClusterShell/Worker
install -d $TMPDIR/conf
install -d $TMPDIR/conf/groups.conf.d
install -d $TMPDIR/conf/groups.d
install -d $TMPDIR/doc/epydoc
install -d $TMPDIR/doc/examples
install -d $TMPDIR/doc/extras/vim/{ftdetect,syntax}
install -d $TMPDIR/doc/man/{man1,man5}
install -d $TMPDIR/doc/sphinx
install -d $TMPDIR/doc/sphinx/_static
install -d $TMPDIR/doc/sphinx/api
install -d $TMPDIR/doc/sphinx/api/workers
install -d $TMPDIR/doc/sphinx/guide
install -d $TMPDIR/doc/sphinx/tools
install -d $TMPDIR/doc/txt
install -d $TMPDIR/tests

install -p -m 0644 setup.cfg setup.py $TMPDIR/
install -p -m 0644 ChangeLog COPYING.LGPLv2.1 README.md $TMPDIR/
install -p -m 0644 lib/ClusterShell/*.py $TMPDIR/lib/ClusterShell
install -p -m 0644 lib/ClusterShell/CLI/*.py $TMPDIR/lib/ClusterShell/CLI/
install -p -m 0644 lib/ClusterShell/Engine/*.py $TMPDIR/lib/ClusterShell/Engine/
install -p -m 0644 lib/ClusterShell/Worker/*.py $TMPDIR/lib/ClusterShell/Worker/
install -p -m 0644 conf/clush.conf $TMPDIR/conf/
install -p -m 0644 conf/groups.conf $TMPDIR/conf/
install -p -m 0644 conf/groups.conf.d/README $TMPDIR/conf/groups.conf.d/
install -p -m 0644 conf/groups.conf.d/*.example $TMPDIR/conf/groups.conf.d/
install -p -m 0644 conf/groups.d/README $TMPDIR/conf/groups.d/
install -p -m 0644 conf/groups.d/local.cfg $TMPDIR/conf/groups.d/
install -p -m 0644 conf/groups.d/*.yaml.example $TMPDIR/conf/groups.d/
install -p -m 0644 conf/topology.conf.example $TMPDIR/conf/
install -p -m 0644 doc/epydoc/clustershell_epydoc.conf $TMPDIR/doc/epydoc/
install -p -m 0644 doc/examples/defaults.conf-rsh $TMPDIR/doc/examples/
install -p -m 0755 doc/examples/*.py $TMPDIR/doc/examples/
install -p -m 0644 doc/extras/vim/ftdetect/clustershell.vim $TMPDIR/doc/extras/vim/ftdetect/
install -p -m 0644 doc/extras/vim/syntax/clushconf.vim $TMPDIR/doc/extras/vim/syntax/
install -p -m 0644 doc/extras/vim/syntax/groupsconf.vim $TMPDIR/doc/extras/vim/syntax/
install -p -m 0644 doc/man/man1/clubak.1 $TMPDIR/doc/man/man1/
install -p -m 0644 doc/man/man1/clush.1 $TMPDIR/doc/man/man1/
install -p -m 0644 doc/man/man1/nodeset.1 $TMPDIR/doc/man/man1/
install -p -m 0644 doc/man/man5/clush.conf.5 $TMPDIR/doc/man/man5/
install -p -m 0644 doc/man/man5/groups.conf.5 $TMPDIR/doc/man/man5/
install -p -m 0644 doc/sphinx/conf.py $TMPDIR/doc/sphinx/
install -p -m 0644 doc/sphinx/Makefile $TMPDIR/doc/sphinx/
install -p -m 0644 doc/sphinx/*.rst $TMPDIR/doc/sphinx/
install -p -m 0644 doc/sphinx/_static/*.css $TMPDIR/doc/sphinx/_static/
install -p -m 0644 doc/sphinx/_static/*.png $TMPDIR/doc/sphinx/_static/
# symlink png as a workaround to make both html and sphinx_rtd_html themes work
ln -s _static/clustershell-nautilus-logo200.png $TMPDIR/doc/sphinx/
install -p -m 0644 doc/sphinx/api/*.rst $TMPDIR/doc/sphinx/api
install -p -m 0644 doc/sphinx/api/workers/*.rst $TMPDIR/doc/sphinx/api/workers/
install -p -m 0644 doc/sphinx/guide/*.rst $TMPDIR/doc/sphinx/guide/
install -p -m 0644 doc/sphinx/tools/*.rst $TMPDIR/doc/sphinx/tools/
install -p -m 0644 doc/txt/*.{rst,txt} $TMPDIR/doc/txt/
install -p -m 0644 doc/txt/README $TMPDIR/doc/txt/
install -p -m 0644 tests/*.py $TMPDIR/tests/

sed -e "s/^Version:       %{version}$/Version:       $VERS/" <clustershell.spec.in >$TMPDIR/clustershell.spec

tar -cvzf $TMPROOT/$PKGNAME.tar.gz -C $TMPROOT/build $PKGNAME || exit 1

sleep 1

echo "Building RPMS..."

rpmbuild -ta --define "dist $DIST" $TMPROOT/$PKGNAME.tar.gz

echo "Wrote: $TMPROOT/$PKGNAME.tar.gz"
md5sum $TMPROOT/$PKGNAME.tar.gz
