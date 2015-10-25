#!/usr/bin/python

"""
Tools classes to implement unit benchmark suites.

Create benchmark test subclassing BenchTest

class NodeSetIter(BenchTest):
    def setup(self):
        self.ns = random_ns(1000)

    def run(self):
        for _item in self.ns:
            pass

suite = BenchSuite()
suite.add_test(NodeSetIter())
self.load(filename)
self.run(branch)
self.save(filename)

or, you can autoload all classes inheriting BenchTest

suite = BenchSuite()
suite.auto_add()
suite.run(branchname)


This script could also be use to analyse benchmark results:

UnitBench.py compare|list|display|clear [ -f RESULTS.YAML ] BRANCHES...

UnitBench.py display v1.7
 TESTNAME                   MEAN     STDDEV  COUNT
 NodeSetParse            0.07308    0.00054      5
 NodeSetUnion            0.00989    0.00032      5
 NodeSetContains         0.11819    0.00041      5

UnitBench.py compare v1.6 v1.7
 TESTNAME                   v1.6       v1.7
 NodeSetParse            0.04251    0.07308       72%
 NodeSetUnion            0.00015    0.00989     6609%
 NodeSetContains         0.04694    0.11819      152%
"""

import sys
import os
import time
import yaml
import math
from optparse import OptionParser


class BenchSuite(object):

    def __init__(self):
        self.results = {}

    # Load result file
    def load(self, filename='results.yaml'):
        if os.path.isfile(filename):
            stream = open(filename)
            data = yaml.load(stream)
            stream.close()
            for tstname, results in data.items():
                self.results.setdefault(tstname, BenchTestResults())
                for branch, values in results.items():
                    for value in values:
                        self.results[tstname][branch].add_result(value)

    # Save result file
    def save(self, filename='results.yaml'):
        data = {}
        for tstname, results in self.results.items():
            for branch, brchresults in results.items():
                data.setdefault(tstname, {})[branch] = list(brchresults)
        backup = open(filename, 'w')
        yaml.dump(data, backup, default_flow_style=False)
        backup.close()

    def add_test(self, test):
        self.results[test.name] = BenchTestResults(test)

    def auto_add(self):
        for cls in BenchTest.__subclasses__():
            self.add_test(cls())

    def run(self, branch, count=5, progress=False):
        # XXX: Do a manual clear
        #self.clear([branch])
        for _ in range(0, count):
            for results in self.results.values():
                if results.test is None:
                    continue
                if progress:
                    sys.stdout.write('.')
                    sys.stdout.flush()
                results.test.setup()
                results.test.bench()
                results[branch].add_result(results.test.elapsed)
        if progress:
            print
        self.display(branch, with_test=True)

    def clear(self, branches):
        for results in self.results.values():
            for branch in branches:
                if branch in results:
                    results.pop(branch)

    def display(self, branch, with_test=False):
        print " %-20s %10s %10s %6s" % ("TESTNAME", "MEAN", "STDDEV", "COUNT")
        for testname in sorted(self.results):
            results = self.results[testname]
            res = results[branch]
            if len(res) == 0:
                continue
            print " %-20s %10.5f %10.5f %6d" % (testname, res.mean(),
                                                res.deviation(), len(res))

    def list(self, branches):
        print " %-20s" % "TESTNAME", " ".join(["%10s" % b for b in branches])
        for testname in sorted(self.results):
            results = self.results[testname]
            strres = []
            for branch in branches:
                if branch in results:
                    strres.append("%10.5f" % results[branch].mean())
                else:
                    strres.append("%10s" % '-')
            if results:
                print " %-20s" % testname, " ".join(strres)

    def compare(self, branch1, branch2):
        print " %-20s %10s %10s" % ("TESTNAME", branch1, branch2)
        for testname in sorted(self.results):
            results = self.results[testname]
            strres = []
            for branch in (branch1, branch2):
                if branch in results:
                    strres.append(results[branch].mean())
                else:
                    strres.append("%10s" % '-')
            if type(strres[0]) is float and type(strres[1]) is float:
                step = (strres[1] - strres[0]) * 100 / strres[0]
                strres = ["%10.5f" % s for s in strres]
                strres.append("%8.0f%%" % step)
            else:
                for i in range(len(strres)):
                    if type(strres[i]) is float:
                        strres[i] = "%10.5f" % strres[i]
            if results:
                print " %-20s" % testname, " ".join(strres)


class BenchTestResults(object):

    def __init__(self, test=None):
        self._results = {}
        self.test = test

    def __getitem__(self, branch):
        return self._results.setdefault(branch, BenchBranchResults())

    def branches(self):
        return self._results.keys()

    def __iter__(self):
        return self.branches()

    def items(self):
        return self._results.items()

    def values(self):
        return self._results.values()

    def __contains__(self, key):
        return key in self._results

    def pop(self, value):
        return self._results.pop(value)


class BenchBranchResults(list):

    add_result = list.append

    def mean(self):
        return sum(self) / len(self)

    def deviation(self):
        avg = self.mean()
        variance = map(lambda x: (x - avg) ** 2, self)
        return math.sqrt(sum(variance) / len(variance))

class BenchTest(object):

    def __init__(self):
        self.elapsed = 0.0
        self.name = self.__class__.__name__

    def bench(self):
        starttime = time.time()
        self.run()
        self.elapsed = time.time() - starttime

    def setup(self):
        pass

    def run(self):
        pass


def bench_main():
    parser = OptionParser(usage="%prog [TAGNAME]")
    parser.add_option("-v", dest="progress", action='store_true',
                      help="display more information for each test")

    (options, args) = parser.parse_args()

    if len(args) == 0:
        print "No tag specified. Results will not be saved."
        tag = None
    else:
        tag = args[0]

    suite = BenchSuite()
    suite.auto_add()
    if tag is not None:
        suite.load()
    suite.run(tag, progress=options.progress)
    if tag is not None:
        suite.save()


def main():
    usage = "%prog compare|list|display|clear|help [-f RESULTS.YAML] BRANCHES..."
    parser = OptionParser(usage)
    parser.add_option("-f", "--file", dest="filename", default="results.yaml",
                      help="stats file to read or write", metavar="FILE")

    (options, args) = parser.parse_args()
    if len(args) == 0:
        parser.error('action name is missing')

    action = args[0]

    suite = BenchSuite()
    if action == 'display':
        suite.load(options.filename)
        if len(args) < 2:
            parser.error("tag name is missing")
        suite.display(args[1])
    elif action == 'list':
        suite.load(options.filename)
        suite.list(args[1:])
    elif action == 'compare':
        suite.load(options.filename)
        if len(args) < 3:
            parser.error("The 2 branch names to compare are missing")
        suite.compare(args[1], args[2])
    elif action == 'clear':
        suite.load(options.filename)
        if len(args) < 2:
            parser.error("tag names to be cleared are missing")
        suite.clear(args[1:])
        suite.save(options.filename)
    elif action == 'help':
        parser.print_help()
        sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == '__main__':
    main()
