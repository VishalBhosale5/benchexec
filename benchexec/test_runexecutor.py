"""
BenchExec is a framework for reliable benchmarking.
This file is part of BenchExec.

Copyright (C) 2007-2015  Dirk Beyer
All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

# prepare for Python 3
from __future__ import absolute_import, division, print_function, unicode_literals

import logging
import os
import sys
import tempfile
import threading
import time
import unittest
sys.dont_write_bytecode = True # prevent creation of .pyc files

from benchexec.runexecutor import RunExecutor

class TestRunExecutor(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.longMessage = True
        logging.disable(logging.CRITICAL)

    def setUp(self):
        self.runexecutor = RunExecutor()

    def execute_run(self, *args, **kwargs):
        (output_fd, output_filename) = tempfile.mkstemp('.log', 'output_', text=True)
        try:
            result = self.runexecutor.execute_run(args, output_filename, **kwargs)
            output_lines = os.read(output_fd, 4096).decode().splitlines()
            return (result, output_lines)
        finally:
            os.close(output_fd)
            os.remove(output_filename)

    def test_command_output(self):
        if not os.path.exists('/bin/echo'):
            self.skipTest('missing /bin/echo')
        (_, output) = self.execute_run('/bin/echo', 'TEST_TOKEN')
        self.assertEqual(output[0], '/bin/echo TEST_TOKEN', 'run output misses executed command')
        self.assertEqual(output[-1], 'TEST_TOKEN', 'run output misses command output')
        for line in output[1:-1]:
            self.assertRegex(line, '^-*$', 'unexpected text in run output')

    def test_command_result(self):
        if not os.path.exists('/bin/echo'):
            self.skipTest('missing /bin/echo')
        (result, _) = self.execute_run('/bin/echo', 'TEST_TOKEN')
        self.assertEqual(result['exitcode'], 0, 'exit code of /bin/echo is not zero')
        self.assertAlmostEqual(result['walltime'], 0.2, delta=0.2, msg='walltime of /bin/echo not as expected')
        self.assertAlmostEqual(result['cputime'], 0.2, delta=0.2, msg='cputime of /bin/echo not as expected')
        for key in result.keys():
            self.assertIn(key, {'cputime', 'walltime', 'memory', 'exitcode'}, 'unexpected result value ' + key)

    def test_cputime_hardlimit(self):
        if not os.path.exists('/bin/sh'):
            self.skipTest('missing /bin/sh')
        (result, output) = self.execute_run('/bin/sh', '-c', 'i=0; while [ $i -lt 10000000 ]; do i=$(($i+1)); done; echo $i',
                                            hardtimelimit=1)
        self.assertEqual(result['exitcode'], 9, 'exit code of killed process is not 9')
        if 'terminationreason' in result:
            # not produced currently if killed by ulimit
            self.assertEqual(result['terminationreason'], 'cputime', 'termination reason is not "cputime"')
        self.assertAlmostEqual(result['walltime'], 1.4, delta=0.5, msg='walltime is not approximately the time after which the process should have been killed')
        self.assertAlmostEqual(result['cputime'], 1.4, delta=0.5, msg='cputime is not approximately the time after which the process should have been killed')
        for key in result.keys():
            self.assertIn(key, {'cputime', 'walltime', 'memory', 'exitcode', 'terminationreason'}, 'unexpected result value ' + key)

        for line in output[1:]:
            self.assertRegex(line, '^-*$', 'unexpected text in run output')

    def test_cputime_softlimit(self):
        if not os.path.exists('/bin/sh'):
            self.skipTest('missing /bin/sh')
        (result, output) = self.execute_run('/bin/sh', '-c', 'i=0; while [ $i -lt 10000000 ]; do i=$(($i+1)); done; echo $i',
                                            hardtimelimit=10, softtimelimit=1)
        self.assertEqual(result['exitcode'], 15, 'exit code of killed process is not 15')
        self.assertEqual(result['terminationreason'], 'cputime-soft', 'termination reason is not "cputime"')
        self.assertAlmostEqual(result['walltime'], 4, delta=3, msg='walltime is not approximately the time after which the process should have been killed')
        self.assertAlmostEqual(result['cputime'], 4, delta=3, msg='cputime is not approximately the time after which the process should have been killed')
        for key in result.keys():
            self.assertIn(key, {'cputime', 'walltime', 'memory', 'exitcode', 'terminationreason'}, 'unexpected result value ' + key)

        for line in output[1:]:
            self.assertRegex(line, '^-*$', 'unexpected text in run output')

    def test_walltime_limit(self):
        if not os.path.exists('/bin/sleep'):
            self.skipTest('missing /bin/sleep')
        (result, output) = self.execute_run('/bin/sleep', '10', walltimelimit=1, hardtimelimit=1)

        self.assertEqual(result['exitcode'], 9, 'exit code of killed process is not 9')
        self.assertEqual(result['terminationreason'], 'walltime', 'termination reason is not "walltime"')
        self.assertAlmostEqual(result['walltime'], 1.5, delta=0.5, msg='walltime is not approximately the time after which the process should have been killed')
        self.assertAlmostEqual(result['cputime'], 0.2, delta=0.2, msg='cputime of /bin/sleep is not approximately zero')
        for key in result.keys():
            self.assertIn(key, {'cputime', 'walltime', 'memory', 'exitcode', 'terminationreason'}, 'unexpected result value ' + key)

        self.assertEqual(output[0], '/bin/sleep 10', 'run output misses executed command')
        for line in output[1:]:
            self.assertRegex(line, '^-*$', 'unexpected text in run output')

    def test_input_is_redirected_from_devnull(self):
        if not os.path.exists('/bin/cat'):
            self.skipTest('missing /bin/cat')
        (result, output) = self.execute_run('/bin/cat', walltimelimit=1, hardtimelimit=1)

        self.assertEqual(result['exitcode'], 0, 'exit code of process is not 0')
        self.assertAlmostEqual(result['walltime'], 0.2, delta=0.2, msg='walltime of "/bin/cat < /dev/null" is not approximately zero')
        self.assertAlmostEqual(result['cputime'], 0.2, delta=0.2, msg='cputime of "/bin/cat < /dev/null" is not approximately zero')
        for key in result.keys():
            self.assertIn(key, {'cputime', 'walltime', 'memory', 'exitcode'}, 'unexpected result value ' + key)

        self.assertEqual(output[0], '/bin/cat', 'run output misses executed command')
        for line in output[1:]:
            self.assertRegex(line, '^-*$', 'unexpected text in run output')

    def test_stop_run(self):
        if not os.path.exists('/bin/sleep'):
            self.skipTest('missing /bin/sleep')
        thread = _StopRunThread(1, self.runexecutor)
        thread.start()
        (result, output) = self.execute_run('/bin/sleep', '10')
        thread.join()

        self.assertEqual(result['exitcode'], 9, 'exit code of killed process is not 9')
        self.assertEqual(result['terminationreason'], 'killed', 'termination reason is not "killed"')
        self.assertAlmostEqual(result['walltime'], 1, delta=0.5, msg='walltime is not approximately the time after which the process should have been killed')
        self.assertAlmostEqual(result['cputime'], 0.2, delta=0.2, msg='cputime of /bin/sleep is not approximately zero')
        for key in result.keys():
            self.assertIn(key, {'cputime', 'walltime', 'memory', 'exitcode', 'terminationreason'}, 'unexpected result value ' + key)

        self.assertEqual(output[0], '/bin/sleep 10', 'run output misses executed command')
        for line in output[1:]:
            self.assertRegex(line, '^-*$', 'unexpected text in run output')

class _StopRunThread(threading.Thread):
    def __init__(self, delay, runexecutor):
        super(_StopRunThread, self).__init__()
        self.daemon = True
        self.delay = delay
        self.runexecutor = runexecutor

    def run(self):
        time.sleep(self.delay)
        self.runexecutor.stop()
