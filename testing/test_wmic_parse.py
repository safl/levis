#!/usr/bin/env python
import unittest, os
import wmic
import agent

class TestWmicOutputParsing(unittest.TestCase):

    def setUp(self):

        self.prefix = 'testing'+os.sep+'files'
        self.output_files = {'empty': 0, 'bios':1, 'eventlog':1, 'perf':49, 'product':1, 'services':1}

    def test_parse_empty(self):

        fd = open(self.prefix + os.sep + 'empty.txt', 'r')
        parsed = wmic.to_dict(fd.read())
        fd.close()

        self.assertEqual(len(parsed), 0)

    def test_parse_error(self):

        fd = open(self.prefix + os.sep + 'error.txt', 'r')
        parsed = wmic.to_dict(fd.read())
        fd.close()

        self.assertEqual(len(parsed), 0)

    def test_parse_singleclass(self):

        fd = open(self.prefix + os.sep + 'win32_bios.txt', 'r')
        parsed = wmic.to_dict(fd.read())
        fd.close()

        self.assertEqual(len(parsed), 1)

    def test_parse_multiclass(self):

        fd = open(self.prefix + os.sep + 'win32_perf.txt', 'r')
        parsed = wmic.to_dict(fd.read())
        fd.close()

        self.assertEqual(len(parsed), 47)

class TestKeyParsing(unittest.TestCase):

    def setUp(self):
        self.key = "Type=win_events.Representation=string.Compression=False.Result=False"

class TestWmicReturncodes(unittest.TestCase):

    def setUp(self):

        self.wmi_target_dead = {'username': 'hej', 'password': 'none', 'hostname': '172.31.110.37', 'domain':''}
        self.wmi_target_alive = {'username': 'safl', 'password': 'bufasbufas', 'hostname': '172.31.110.37', 'domain':''}

    def test_error(self):
        (returncode, err, out) = agent.cmd({'cmdline': wmic.cmdline(self.wmi_target_dead)})
        self.assertEqual(1, returncode)

    def test_success(self):
        (returncode, err, out) = agent.cmd({'cmdline': wmic.cmdline(self.wmi_target_alive)+['SELECT * FROM Win32_Service']})
        self.assertEqual(0, returncode)

if __name__ == '__main__':
    unittest.main()
