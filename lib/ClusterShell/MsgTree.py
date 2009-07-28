#
# Copyright CEA/DAM/DIF (2007, 2008, 2009)
#  Contributor: Stephane THIELL <stephane.thiell@cea.fr>
#
# This file is part of the ClusterShell library.
#
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software.  You can  use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
# "http://www.cecill.info".
#
# As a counterpart to the access to the source code and  rights to copy,
# modify and redistribute granted by the license, users are provided only
# with a limited warranty  and the software's author,  the holder of the
# economic rights,  and the successive licensors  have only  limited
# liability.
#
# In this respect, the user's attention is drawn to the risks associated
# with loading,  using,  modifying and/or developing or reproducing the
# software by the user in light of its specific status of free software,
# that may mean  that it is complicated to manipulate,  and  that  also
# therefore means  that it is reserved for developers  and  experienced
# professionals having in-depth computer knowledge. Users are therefore
# encouraged to load and test the software's suitability as regards their
# requirements in conditions enabling the security of their systems and/or
# data to be ensured and,  more generally, to use and operate it in the
# same conditions as regards security.
#
# The fact that you are presently reading this means that you have had
# knowledge of the CeCILL-C license and that you accept its terms.
#
# $Id$

"""
MsgTree

ClusterShell message tree classes.
"""


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
            self.sources.update(source)
    
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
            src = set([ source ])
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

