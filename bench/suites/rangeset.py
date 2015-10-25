#!/usr/bin/python

import random
import cPickle

from UnitBench import BenchTest, bench_main

from ClusterShell.NodeSet import RangeSet

NB_ELEM = 1000

def random_list(count, upper=10000):
    return [int(random.uniform(1, upper)) for _ in range(1, count)]

def random_rng(count, upper=10000):
    return RangeSet.fromlist(map(str, random_list(count, upper)))

class RangeSetParse(BenchTest):

    def setup(self):
        self.txt = ",".join([str(nbr) for nbr in random_list(NB_ELEM)])

    def run(self):
        RangeSet(self.txt)

class RangeSetAdd(BenchTest):

    def setup(self):
        self.rng = RangeSet()
        self.numbers = random_list(NB_ELEM)

    def run(self):
        for item in self.numbers:
            self.rng.add(item)

class RangeSetRemove(BenchTest):

    def setup(self):
        self.rng = random_rng(NB_ELEM)
        self.numbers = random_list(NB_ELEM)

    def run(self):
        for item in self.numbers:
            try:
                self.rng.remove(item)
            except KeyError:
                pass

class RangeSetIter(BenchTest):

    def setup(self):
        self.rng = random_rng(NB_ELEM)

    def run(self):
        for _item in self.rng:
            pass

class RangeSetStr(BenchTest):

    def setup(self):
        self.rng = random_rng(NB_ELEM)

    def run(self):
        str(self.rng)

class RangeSetcPickle(BenchTest):

    def setup(self):
        self.rng = random_rng(NB_ELEM)

    def run(self):
        cPickle.dumps(self.rng)

class RangeSetContains(BenchTest):

    def setup(self):
        self.rng1 = random_rng(NB_ELEM)
        self.rng2 = random_rng(NB_ELEM)

    def run(self):
        for i in self.rng1:
            i in self.rng2

class RangeSetUnion(BenchTest):

    def setup(self):
        self.rng1 = random_rng(NB_ELEM)
        self.rng2 = random_rng(NB_ELEM)

    def run(self):
        self.rng1.union(self.rng2)


if __name__ == '__main__':
    bench_main()
