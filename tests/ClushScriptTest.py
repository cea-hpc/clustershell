#!/usr/bin/env python
# scripts/clush.py tool test suite 
# Written by S. Thiell 2011-03-19


"""Unit test for scripts/clush.py"""

from subprocess import Popen, PIPE
import os
import pwd
import tempfile
import time
import unittest

def makeTestFile(text):
    """Create a temporary file with the provided text."""
    f = tempfile.NamedTemporaryFile()
    f.write(text)
    f.flush()
    return f


class ClushScriptTest(unittest.TestCase):
    """Unit test class for testing clush.py"""

    def _launchAndCompare(self, args, expected_output, stdin=None):
        output = Popen(["../scripts/clush.py"] + args, stdout=PIPE,
                       stdin=PIPE).communicate(input=stdin)[0].strip()
        if type(expected_output) is list:
            ok = False
            for o in expected_output:
                if output == o:
                    ok = True
            self.assert_(ok, "Output %s != one of %s" % \
                             (output, expected_output))
        else:
            self.assertEqual(expected_output, output)

    def test1(self):
        """test clush.py command (display)"""
        self._launchAndCompare(["-w", "localhost", "true"], "")
        self._launchAndCompare(["-w", "localhost", "echo", "ok"],
                               "localhost: ok")
        self._launchAndCompare(["-w", "localhost", "echo", "ok", "ok"],
                               "localhost: ok ok")
        self._launchAndCompare(["-N", "-w", "localhost", "echo", "ok", "ok"],
                               "ok ok")
        self._launchAndCompare(["-qw", "localhost", "echo", "ok"],
                               "localhost: ok")
        self._launchAndCompare(["-vw", "localhost", "echo", "ok"],
                               "localhost: ok")
        self._launchAndCompare(["-qvw", "localhost", "echo", "ok"],
                               "localhost: ok")
        self._launchAndCompare(["-Sw", "localhost", "echo", "ok"],
                               "localhost: ok")
        self._launchAndCompare(["-Sqw", "localhost", "echo", "ok"],
                               "localhost: ok")
        self._launchAndCompare(["-Svw", "localhost", "echo", "ok"],
                               "localhost: ok")
        self._launchAndCompare(["--nostdin", "-w", "localhost", "echo", "ok"],
                               "localhost: ok")

    def test2(self):
        """test clush.py command (fanout)"""
        self._launchAndCompare(["-f", "10", "-w", "localhost", "true"], "")
        self._launchAndCompare(["-f", "1", "-w", "localhost", "true"], "")
        self._launchAndCompare(["-f", "1", "-w", "localhost", "echo", "ok"],
                               "localhost: ok")

    def test3(self):
        """test clush.py command (ssh options)"""
        self._launchAndCompare(["-o", "-oStrictHostKeyChecking=no", "-w",
            "localhost", "echo", "ok"], "localhost: ok")
        self._launchAndCompare(["-o", "-oStrictHostKeyChecking=no " \
                                "-oForwardX11=no", "-w", "localhost",
                                "echo", "ok"], "localhost: ok")
        self._launchAndCompare(["-o", "-oStrictHostKeyChecking=no",
                                "-o", "-oForwardX11=no",
                                "-w", "localhost", "echo", "ok"],
                               "localhost: ok")
        self._launchAndCompare(["-o-oStrictHostKeyChecking=no",
                                "-o-oForwardX11=no",
                                "-w", "localhost", "echo", "ok"],
                               "localhost: ok")
        self._launchAndCompare(["-u", "4", "-w", "localhost", "echo", "ok"],
                               "localhost: ok")
        self._launchAndCompare(["-t", "4", "-u", "4", "-w", "localhost",
                                "echo", "ok"], "localhost: ok")

    def test4(self):
        """test clush.py command (output gathering)"""
        self._launchAndCompare(["-w", "localhost", "-L", "echo", "ok"],
                               "localhost: ok")
        self._launchAndCompare(["-w", "localhost", "-bL", "echo", "ok"],
                               "localhost: ok")
        self._launchAndCompare(["-w", "localhost", "-qbL", "echo", "ok"],
                               "localhost: ok")
        self._launchAndCompare(["-w", "localhost", "-BL", "echo", "ok"],
                               "localhost: ok")
        self._launchAndCompare(["-w", "localhost", "-qBL", "echo", "ok"],
                               "localhost: ok")
        self._launchAndCompare(["-w", "localhost", "-BLS", "echo", "ok"],
                               "localhost: ok")
        self._launchAndCompare(["-w", "localhost", "-qBLS", "echo", "ok"],
                               "localhost: ok")
        
    def test5(self):
        """test clush.py command (file copy)"""
        content = "%f" % time.time()
        f = makeTestFile(content)
        self._launchAndCompare(["-w", "localhost", "-c", f.name], "")
        f.seek(0)
        self.assertEqual(f.read(), content)
        # test --dest option
        f2 = tempfile.NamedTemporaryFile()
        self._launchAndCompare(["-w", "localhost", "-c", f.name, "--dest",
                                f2.name], "")
        f2.seek(0)
        self.assertEqual(f2.read(), content)
        # test --user option
        f2 = tempfile.NamedTemporaryFile()
        self._launchAndCompare(["--user", pwd.getpwuid(os.getuid())[0], "-w",
                                "localhost", "--copy", f.name, "--dest", f2.name],
                               "")
        f2.seek(0)
        self.assertEqual(f2.read(), content)
        # test --rcopy
        self._launchAndCompare(["--user", pwd.getpwuid(os.getuid())[0], "-w",
                                "localhost", "--rcopy", f.name, "--dest",
                                os.path.dirname(f.name)], "")
        f2.seek(0)
        self.assertEqual(open("%s.localhost" % f.name).read(), content)

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(ClushScriptTest)
    unittest.TextTestRunner(verbosity=2).run(suite)
