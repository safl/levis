#!/usr/bin/env python
import unittest, os
import rpc

class TestKeyParsing(unittest.TestCase):

    def setUp(self):

        self.wmi_target = {
            "host": "192.168.1.101",
            "domain": "",
            "user":   "safl",
            "pass":   "bufasbufas"
        }

        self.queries = {
            'filesize':       "SELECT Name, FileSize FROM CIM_DataFile WHERE Name = 'c:\\\\hej.pst'",
            'exefiles':       "SELECT Name, FileSize FROM CIM_DataFile WHERE Extension = 'exe'",
            'service_enum':   "SELECT * FROM Win32_Service",
            'service_state':  "SELECT Name, State FROM Win32_Service WHERE Name = 'SysmonLog'",
            'disk_enum':      "SELECT * FROM Win32_LogicalDisk",
            'disks':          "SELECT * FROM Win32_DiskDrive",
            'disk_free':      "SELECT Name, DeviceID, FreeSpace FROM Win32_LogicalDisk WHERE DeviceID = 'C:'",
    
            'cpu_enum':      "SELECT * FROM Win32_Processor",
            'cpu_util':      "SELECT Name, DeviceID, LoadPercentage FROM Win32_Processor WHERE DeviceID = 'CPU0'",
            'cpu_avg':       "SELECT Name, LoadPercentage FROM Win32_Processor",
    
            'os_enum':       "SELECT * FROM Win32_OperatingSystem",
    
            'tapedrive':     "SELECT * FROM Win32_TapeDrive",
    
            'os_uptime':         "SELECT LastBootUpTime FROM Win32_OperatingSystem",
            'os_mem_free_phys':  "SELECT FreePhysicalMemory FROM Win32_OperatingSystem",
            'os_mem_free_virt':  "SELECT FreeVirtualMemory FROM Win32_OperatingSystem",
    
            'bios':             "SELECT * FROM Win32_Bios",
            'perf_enum':        "SELECT * FROM Win32_PerfRawData_PerfOS_System",
            'perf':         "SELECT * FROM Win32_PerfFormattedData",
    
            'eventlog_enum': "SELECT CategoryString, EventCode, EventType, Logfile, SourceName, TimeGenerated, TimeWritten FROM Win32_NTLogEvent WHERE TimeWritten > '20100323193917.000000+060'",
    
            'eventlog_describe': "SELECT * FROM Win32_NTLogEvent"
        }

    def test_connect_and_query(self):

        (out, ret) = wmic.query(self.wmi_target, self.queries['os_enum'])
        print out, ret

if __name__ == '__main__':
    unittest.main()
