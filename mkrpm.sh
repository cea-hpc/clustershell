#!/bin/sh
# $Id$

if [ -z "$2" ]; then
    echo "usage: $0 <version> <el5|fc11>"
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
install -d $TMPDIR/lib/ClusterShell/Engine
install -d $TMPDIR/lib/ClusterShell/Worker
install -d $TMPDIR/scripts
install -d $TMPDIR/conf
install -d $TMPDIR/doc/man/{man1,man5}
install -d $TMPDIR/doc/extras/vim/{ftdetect,syntax}
install -d $TMPDIR/doc/epydoc
install -d $TMPDIR/tests

install -p -m 0644 setup.cfg setup.py $TMPDIR/
install -p -m 0644 README ChangeLog Licence_CeCILL-C_V1-en.txt Licence_CeCILL-C_V1-fr.txt $TMPDIR/
install -p -m 0644 lib/ClusterShell/*.py $TMPDIR/lib/ClusterShell
install -p -m 0644 lib/ClusterShell/Engine/*.py $TMPDIR/lib/ClusterShell/Engine/
install -p -m 0644 lib/ClusterShell/Worker/*.py $TMPDIR/lib/ClusterShell/Worker/
install -p -m 0755 scripts/clubak.py $TMPDIR/scripts/
install -p -m 0755 scripts/clush.py $TMPDIR/scripts/
install -p -m 0755 scripts/nodeset.py $TMPDIR/scripts/
install -p -m 0644 conf/clush.conf $TMPDIR/conf/
install -p -m 0644 conf/groups.conf $TMPDIR/conf/
install -p -m 0644 doc/man/man1/clubak.1 $TMPDIR/doc/man/man1/
install -p -m 0644 doc/man/man1/clush.1 $TMPDIR/doc/man/man1/
install -p -m 0644 doc/man/man1/nodeset.1 $TMPDIR/doc/man/man1/
install -p -m 0644 doc/man/man5/clush.conf.5 $TMPDIR/doc/man/man5/
install -p -m 0644 doc/man/man5/groups.conf.5 $TMPDIR/doc/man/man5/
install -p -m 0644 doc/extras/vim/ftdetect/clustershell.vim $TMPDIR/doc/extras/vim/ftdetect/
install -p -m 0644 doc/extras/vim/syntax/clushconf.vim $TMPDIR/doc/extras/vim/syntax/
install -p -m 0644 doc/extras/vim/syntax/groupsconf.vim $TMPDIR/doc/extras/vim/syntax/
install -p -m 0644 doc/epydoc/clustershell_epydoc.conf $TMPDIR/doc/epydoc/
install -p -m 0644 tests/*.py $TMPDIR/tests/
chmod 0755 $TMPDIR/tests/run_testsuite.py

sed -e "s/^Version:       %{version}$/Version:       $VERS/" <clustershell.spec.in >$TMPDIR/clustershell.spec

tar -cvzf $TMPROOT/$PKGNAME.tar.gz -C $TMPROOT/build $PKGNAME || exit 1

sleep 1

echo "Building RPMS..."

rpmbuild -ta --define "dist $DIST" $TMPROOT/$PKGNAME.tar.gz

echo "Wrote: $TMPROOT/$PKGNAME.tar.gz"
md5sum $TMPROOT/$PKGNAME.tar.gz

