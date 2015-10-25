#!/usr/bin/python

import random
import cPickle

from UnitBench import BenchTest, bench_main

from ClusterShell.NodeSet import NodeSet


#
# NodeSet with 2 dimensions
#

NB_ELEM = 1000

def random_nodes(count, uppers=[10000, 10]):
    lst = []
    for _ in range(1, count):
        randoms = tuple((int(random.uniform(1, up)) for up in uppers))
        lst.append("foo%d-ib%d" % randoms)
    return lst

def random_ns(count, upper=[10000, 3]):
    return NodeSet.fromlist(random_nodes(count, upper))

class NodeSet2DParse(BenchTest):

    def setup(self):
        self.txt = ",".join(random_nodes(NB_ELEM))

    def run(self):
        NodeSet(self.txt)

class NodeSet2DAdd(BenchTest):

    def setup(self):
        self.ns = NodeSet()
        self.nodes = random_nodes(NB_ELEM)

    def run(self):
        for item in self.nodes:
            self.ns.add(item)

class NodeSet2DRemove(BenchTest):

    def setup(self):
        self.ns = random_ns(NB_ELEM)
        self.nodes = random_nodes(NB_ELEM)

    def run(self):
        for item in self.nodes:
            try:
                self.ns.remove(item)
            except KeyError:
                pass

class NodeSet2DIter(BenchTest):

    def setup(self):
        self.ns = random_ns(NB_ELEM)

    def run(self):
        for _item in self.ns:
            pass

class NodeSet2DStr(BenchTest):

    def setup(self):
        self.ns = random_ns(NB_ELEM)

    def run(self):
        str(self.ns)

class NodeSet2DcPickle(BenchTest):

    def setup(self):
        self.ns = random_ns(NB_ELEM)

    def run(self):
        cPickle.dumps(self.ns)

class NodeSet2DContains(BenchTest):

    def setup(self):
        self.ns1 = random_ns(NB_ELEM)
        self.ns2 = random_ns(NB_ELEM)

    def run(self):
        for i in self.ns1:
            i in self.ns2

class NodeSet2DUnion(BenchTest):

    def setup(self):
        self.ns1 = random_ns(NB_ELEM)
        self.ns2 = random_ns(NB_ELEM)

    def run(self):
        self.ns1.union(self.ns2)


if __name__ == '__main__':
    bench_main()
