#!/usr/bin/env python
# ClusterShell test suite
# Written by S. Thiell 2010-02-03
# $Id$


"""Unit test for ClusterShell MsgTree Class"""

from operator import itemgetter
import sys
import unittest

sys.path.insert(0, '../lib')

from ClusterShell.MsgTree import MsgTree


class MsgTreeTest(unittest.TestCase):

    def testMsgTree(self):
        """test MsgTree basics"""
        tree = MsgTree()
        self.assertEqual(len(tree), 0)

        tree.add("key", "message")
        self.assertEqual(len(tree), 1)

        tree.add("key", "message2")
        self.assertEqual(len(tree), 1)

        tree.add("key2", "message3")
        self.assertEqual(len(tree), 2)

    def testMsgTreeIterators(self):
        """test MsgTree iterators"""
        # build tree...
        tree = MsgTree()
        self.assertEqual(len(tree), 0)
        tree.add(("item1", "key"), "message0")
        self.assertEqual(len(tree), 1)
        tree.add(("item2", "key"), "message2")
        self.assertEqual(len(tree), 2)
        tree.add(("item3", "key"), "message3")
        self.assertEqual(len(tree), 3)
        tree.add(("item4", "key"), "message3")
        tree.add(("item2", "newkey"), "message4")
        self.assertEqual(len(tree), 5)
        self.assertEqual(tree._depth(), 1)

        # test standard iterator (over keys)
        cnt = 0
        what = set([ ("item1", "key"), ("item2", "key"), ("item3", "key"), \
                    ("item4", "key"), ("item2", "newkey") ])
        for key in tree:
            cnt += 1
            what.remove(key)
        self.assertEqual(cnt, 5)
        self.assertEqual(len(what), 0)

        # test keys() iterator
        cnt = 0
        for key in tree.keys():
            cnt += 1
        self.assertEqual(cnt, 5)

        # test messages() iterator (iterate over different messages)
        cnt = 0
        for msg in tree.messages():
            cnt += 1
        self.assertEqual(cnt, 4)

        # test items() iterator (iterate over all key, msg pairs)
        cnt = 0
        for key, msg in tree.items():
            cnt += 1
        self.assertEqual(cnt, 5)
            
        # test walk() iterator (iterate by msg and give the list of
        # associated keys)
        cnt = 0
        cnt_2 = 0
        for msg, keys in tree.walk():
            cnt += 1
            if len(keys) == 2:
                self.assertEqual(msg, "message3")
                cnt_2 += 1
        self.assertEqual(cnt, 4)
        self.assertEqual(cnt_2, 1)

        # test walk() with provided key-filter
        cnt = 0
        for msg, keys in tree.walk(match=lambda s: s[1] == "newkey"):
            cnt += 1
        self.assertEqual(cnt, 1)

        # test walk() with provided key-mapper
        cnt = 0
        cnt_2 = 0
        for msg, keys in tree.walk(mapper=itemgetter(0)):
            cnt += 1
            if len(keys) == 2:
                for k in keys:
                    self.assertEqual(type(k), str)
                cnt_2 += 1
        self.assertEqual(cnt, 4)
        self.assertEqual(cnt_2, 1)

        # test walk with full options: key-filter and key-mapper
        cnt = 0
        for msg, keys in tree.walk(match=lambda k: k[1] == "newkey",
                                       mapper=itemgetter(0)):
            cnt += 1
            self.assertEqual(msg, "message4")
            self.assertEqual(keys[0], "item2")
        self.assertEqual(cnt, 1)

        cnt = 0
        for msg, keys in tree.walk(match=lambda k: k[1] == "key",
                                       mapper=itemgetter(0)):
            cnt += 1
            self.assertEqual(keys[0][:-1], "item")
        self.assertEqual(cnt, 3) # 3 and not 4 because item3 and item4 are merged

    def testMsgTreeGetItem(self):
        """test MsgTree __getitem__"""
        # build tree...
        tree = MsgTree()
        tree.add("item1", "message0")
        self.assertEqual(len(tree), 1)
        tree.add("item2", "message2")
        tree.add("item3", "message2")
        tree.add("item4", "message3")
        tree.add("item2", "message4")
        tree.add("item3", "message4")
        self.assertEqual(len(tree), 4)
        self.assertEqual(tree["item1"], "message0")
        self.assertEqual(tree["item2"], "message2\nmessage4")
        self.assertEqual(tree._depth(), 2)



if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(MsgTreeTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

