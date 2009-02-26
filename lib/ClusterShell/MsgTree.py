# MsgTree.py -- Utility class for ClusterShell
# Copyright (C) 2007, 2008, 2009 CEA
# Written by S. Thiell
#
# This file is part of ClusterShell
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# $Id$

"""
MsgTree

ClusterShell message tree classes.
"""

from sets import Set

class MsgTreeElem:
    """
    Helper class used to build a messages tree. Advantages are:
    (1) low memory consumption especially on a cluster when all nodes
    return similar messages,
    (2) gathering of messages is done (almost) automatically.
    """
    def __init__(self, msg=None, parent=None):
        """
        Initialize message tree element.
        """
        # structure
        self.parent = parent
        self.children = {}
        # content
        self.msg = msg
        self.sources = None
   
    def __iter__(self):
        """
        Iterate over tree key'd elements.
        """
        estack = [ self ]

        while len(estack) > 0:
            elem = estack.pop()
            if len(elem.children) > 0:
                estack += elem.children.values()
            if elem.sources and len(elem.sources) > 0:
                yield elem
    
    def _add_source(self, source):
        """
        Add source tuple (worker, key) to this element.
        """
        if not self.sources:
            self.sources = source.copy()
        else:
            self.sources.union_update(source)
    
    def _remove_source(self, source):
        """
        Remove a source tuple (worker, key) from this element.
        It's used when moving it to a child.
        """
        if self.sources:
            self.sources.difference_update(source)
        
    def add_msg(self, source, msg):
        """
        A new message line is coming, add it to the tree.
        source is a tuple identifying the message source
        """
        if self.sources and len(self.sources) == 1:
            # do it quick when only one source is attached
            src = self.sources
            self.sources = None
        else:
            # remove source from parent (self)
            src = Set([ source ])
            self._remove_source(src)

        # add msg elem to child
        elem = self.children.setdefault(msg, self.__class__(msg, self))
        # add source to elem
        elem._add_source(src)
        return elem

    def message(self):
        """
        Get the whole message buffer from this tree element.
        """
        msg = ""

        # no msg in root element
        if self.msg is None:
            return msg
        
        # build list of msg (reversed by design)
        rmsgs = [self.msg]
        parent = self.parent
        while parent and parent.msg is not None:
            rmsgs.append(parent.msg)
            parent = parent.parent

        # reverse the list
        rmsgs.reverse()

        # concat buffers
        return '\n'.join(rmsgs)

