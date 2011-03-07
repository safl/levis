#!/usr/bin/env python
import threading
import unittest
import pprint
import time
import os

import levislib.comm as comm

queue = "network_events"

# Async callback for receiving messages
def recv_cb(msg):
    
    payload = comm.unpack(msg)
    pprint.pprint(payload)

class TestCommunication(unittest.TestCase):

    def setUp(self):
        self.data_struct = {'hej': [1,2,3,4], 'der': [3,2,1], 'jam': {'hej':'igen', 'der': [[1,2,3], [1,2,3], [1,2,3], [1,2,3], ]}}
        self.server = "127.0.0.1"
        self.port   = 11300

    def test_rw(self):

        c = comm.Comm(host=self.server, port=self.port)
        
        c.subscribe(recv_cb)
        c.publish(comm.pack(self.data_struct))
        
        c.disconnect('network_consumer')        

    def test_wr(self):

        c = comm.Comm(host=self.server, port=self.port)
        
        c.publish(comm.pack(self.data_struct))        
        c.subscribe(recv_cb)
        
        c.disconnect('network_consumer')

if __name__ == '__main__':
    unittest.main()
