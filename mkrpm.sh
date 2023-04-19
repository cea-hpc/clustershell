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

set -e

if [ $# -lt 1 ]; then
    echo "usage: $0 <dist> [force]"
    echo "Build sdist tarball and RPMS from clustershell.spec.in"
    echo "example: $0 el7"
    exit 1
fi

which python &>/dev/null && PYTHON=python || PYTHON=python3
DIST=$1
FORCE=${2:-no}
VERS=$($PYTHON -c "import ClusterShell; print(ClusterShell.__version__)")
PKGNAME=ClusterShell-$VERS

echo "Building version $VERS for $DIST"
echo

sleep 1

if [ ! -f dist/$PKGNAME.tar.gz -o $FORCE = "force" ]; then
    echo "Building tarball..."

    # symlink png as a workaround to make both html and sphinx_rtd_html themes work
    ln -fs _static/clustershell-nautilus-logo200.png doc/sphinx/

    #
    # Build base source package
    #
    rm -f dist/$PKGNAME.tar.gz
    $PYTHON setup.py sdist
    ls -l $PWD/dist/$PKGNAME.tar.gz
    md5sum dist/$PKGNAME.tar.gz
    echo "Base source tarball successfully built"
else
    md5sum dist/$PKGNAME.tar.gz
    echo "dist/$PKGNAME.tar.gz exists, skipping sdist (use force to override)"
fi

echo
sleep 1

echo "Building RPMS..."

sed -e "s/^Version:\(\s\+\)%{version}$/Version:\1${VERS}/" <clustershell.spec.in >clustershell.spec

rpmbuild --define "dist .$DIST" --define "_sourcedir $PWD/dist" -ba clustershell.spec
