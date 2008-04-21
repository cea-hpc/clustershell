#!/bin/sh

if [ -z "$1" ]; then
    echo "usage: $0 <version>"
    exit 1
fi

VERS=$1
PKGNAME=clustershell-$VERS

TMPDIR=/tmp/clustershell-build/$PKGNAME
rm -vrf /tmp/clustershell-build

mkdir -vp "$TMPDIR/lib/ClusterShell"
mkdir -vp "$TMPDIR/lib/ClusterShell/Engine"
mkdir -vp "$TMPDIR/lib/ClusterShell/Worker"


cp -v clustershell.spec setup.cfg setup.py "$TMPDIR/"
cp -v lib/ClusterShell/*.py "$TMPDIR/lib/ClusterShell"
cp -v lib/ClusterShell/Engine/*.py "$TMPDIR/lib/ClusterShell/Engine/"
cp -v lib/ClusterShell/Worker/*.py "$TMPDIR/lib/ClusterShell/Worker/"

cd "$TMPDIR/.."

tar -czf $PKGNAME.tar.gz $PKGNAME
rpmbuild -tb $PKGNAME.tar.gz

