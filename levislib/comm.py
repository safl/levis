#!/usr/bin/env python
"""
Encapsulates communication and provides helper functions for message representation, serialization and compression.

"""
import json as serializer
import zlib as compr
import threading
import logging
import uuid

import beanstalkc

# JSON-RPC 2.0 - Messages
# http://groups.google.com/group/json-rpc/web/json-rpc-2-0
#

# RPC error-codes
JRPC_PARSE_ERROR       = -32700
JRPC_INVALID_REQUEST   = -32600
JRPC_METHOD_NOT_FOUND  = -32601
JRPC_INVALID_PARAMS    = -32602
JRPC_INTERNAL_ERROR    = -32603
JRPC_SERVER_ERROR      = -32604

# RPC error-codes -32099 to -32000 are reserved for application specific codes.
JRPC_APP_TIMEOUT = -32100

# rpc messages
def rpc_request(method, params, id=None):
    """Remote invocation request, with or without an expected return-value."""

    if id:            # Remote invocation with return-value
        return {"jsonrpc": "2.0", "method": method, "params": params, "id": id}
    else:             # Remote invocation WITHOUT return-value aka "notification"
        return {"jsonrpc": "2.0", "method": method, "params": params}

def rpc_response(result, id, agent_id, device_id=None):
    """Response for successful remote invocation."""
    return {
        "jsonrpc": "2.0",
        "result": result,
        "agent_id": agent_id,
        "device_id": device_id,
        "id": id
    }

def rpc_error(code, message, id, agent_id, device_id=None):
    """Response for unsuccessful remote invocation."""
    return {
        "jsonrpc": "2.0",
        "error": {"code": code, "message": message},
        "agent_id": agent_id,
        "device_id": device_id,
        "id": id
    }

#
# Helper-functions for message representation
#
def serialize(data):
    """Python datatypes to string representation."""
    return serializer.dumps(data)

def compress(data):
    """Compress string representation."""
    return compr.compress(data)

def deserialize(data):
    """String representation to Python datatypes."""
    return serializer.loads(data)

def decompress(data):
    """Decompress string representation."""
    return compr.decompress(data)

def pack(data):
    """Serialize & Compress."""
    return compress(serialize(data))

def unpack(data):
    """Decompress & Deserialize."""
    return deserialize(decompress(data))

def key_to_attr(key):
    """
    Maps a routing key on the form::

      Type=win_events.Representation=json.Compression=True.Result=True

    To a dict::

      { 'Type':           'win_events',
        'Representation': 'json',
        'Compression':    'True',
        'Result':         'True'
      }

    See the unit-test for expected output and corner cases. WOW a UNIT-test!
    """

    attributes = {}
    for attr in key.split("."):
        try:
            (k, v) = attr.split("=")
            if k and v:               # We do not want empty values nor keys!
                attributes[k] = v
        except:                     # We need a = to split on!
            pass
    return attributes

# Some more intelligent pack/unpack functions would be nice, which should
# inspect the content-type and check whether they should be compressed / uncompressed, serialized / deserialized etc...
# such as "gzip/json" should be decompressed and deserialized.

class Comm:
    
    def __init__(self, host='127.0.0.1', port=11300):
        
        self.messaging = True
        
        self.input  = beanstalkc.Connection(host, port)        
        self.output = beanstalkc.Connection(host, port)
        
        self.threads = []
    
    def publish(self, msg, queue='default', pri=0):
        
        self.output.use(queue)
        self.output.put(msg)
    
    def subscribe(self, cb, queues=['default'], timeout=10):
                
        t = threading.Thread(
            target  = self._subscribe,
            args    = (cb, queues, timeout)
        )
        self.threads.append(t)
        t.start()
        
    def _subscribe(self, cb, queues=['default'], timeout=10):
        
        for w in self.input.watching(): # Ensure only default is watched
            self.input.ignore(w)
        
        for q in queues:                # Watch 'queues'
            self.input.watch(q)
        
        if 'default' not in queues:     # Ignore 'default'
            self.input.ignore('default')
        
        while self.messaging:
            j = self.input.reserve(timeout)
            if j:
                cb(j)
                j.delete()
    
    def disconnect(self, tag):
        
        self.messaging = False