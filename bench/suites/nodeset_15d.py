#!/usr/bin/python

import random
import cPickle

from UnitBench import BenchTest, bench_main

from ClusterShell.NodeSet import NodeSet
from ClusterShell.NodeSet import RangeSet


#
# NodeSet 2D with 1D constant
#

NB_ELEM = 1000

def random_nodes(count, upper=10000):
    return ["foo%d-ib0" % int(random.uniform(1, upper)) for _ in range(1, count)]

def random_ns(count, upper=10000):
    return NodeSet.fromlist(random_nodes(count, upper))

class NodeSet15Parse(BenchTest):

    def setup(self):
        self.txt = ",".join(random_nodes(NB_ELEM))

    def run(self):
        NodeSet(self.txt)

class NodeSet15Add(BenchTest):

    def setup(self):
        self.ns = NodeSet()
        self.nodes = random_nodes(NB_ELEM)

    def run(self):
        for item in self.nodes:
            self.ns.add(item)

class NodeSet15Remove(BenchTest):

    def setup(self):
        self.ns = random_ns(NB_ELEM)
        self.nodes = random_nodes(NB_ELEM)

    def run(self):
        for item in self.nodes:
            try:
                self.ns.remove(item)
            except KeyError:
                pass

class NodeSet15Iter(BenchTest):

    def setup(self):
        self.ns = random_ns(NB_ELEM)

    def run(self):
        for _item in self.ns:
            pass

class NodeSet15Str(BenchTest):

    def setup(self):
        self.ns = random_ns(NB_ELEM)

    def run(self):
        str(self.ns)

class NodeSet15cPickle(BenchTest):

    def setup(self):
        self.ns = random_ns(NB_ELEM)

    def run(self):
        cPickle.dumps(self.ns)

class NodeSet15Contains(BenchTest):

    def setup(self):
        self.ns1 = random_ns(NB_ELEM)
        self.ns2 = random_ns(NB_ELEM)

    def run(self):
        for i in self.ns1:
            i in self.ns2

class NodeSet15Union(BenchTest):

    def setup(self):
        self.ns1 = random_ns(NB_ELEM)
        self.ns2 = random_ns(NB_ELEM)

    def run(self):
        self.ns1.union(self.ns2)


if __name__ == '__main__':
    bench_main()
