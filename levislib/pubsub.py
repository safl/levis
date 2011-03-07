#!/usr/bin/env python
"""
Encapsulates AMQP communication and provides helper functions for message representation, serialization and compression.

"""
from amqplib import client_0_8 as amqp
import json as serializer
import zlib as compr
import logging
import uuid

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

def rpc_response(result, id):
    """Response for successful remote invocation."""
    return {"jsonrpc": "2.0", "result": result, "id": id}

def rpc_error(code, message, id):
    """Response for unsuccessful remote invocation."""
    return {"jsonrpc": "2.0", "error": {"code": code, "message": message}, "id": id}

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

# AMQP encapsulation!
class Pubsub:

    def __init__(self,
                 host         = "localhost:5672",
                 userid       = "guest",
                 password     = "guest",
                 virtual_host = "/",
                 insist       = False):

        self.messaging  = True

        self.conn = amqp.Connection(                  # Connect to queue-server
          host          = host,
          userid        = userid,
          password      = password,
          virtual_host  = virtual_host,
          insist        = insist
        )

        self.input_channel  = self.conn.channel() # Get a channel for receiving messages
        self.output_channel = self.conn.channel() # Get a channel for sending messages

        self.channels = [self.input_channel, self.output_channel]

    def publish(self, key, exchange, msg): # TODO: Add an async-RPC method, which sets the return stuff
        """Publish a generic message."""

        return self.output_channel.basic_publish( amqp.Message(msg, None, reply_to='hej'),
                                                  exchange=exchange,
                                                  routing_key=key )

    def rpc(self, key, exchange, msg):
        """Publish an RPC-message."""


        return self.output_channel.basic_publish( amqp.Message(msg, None, reply_to='RPC-RES'),
                                                  exchange=exchange,
                                                  routing_key=key)

    def consume(self, key, exchange, queue, tag, cb):
        """
        Binds and listens for messages, executes 'cb' on message-arrival.
        
        This blocks until disconnect() is called.
        # NOTE: see the diconnect()
        """

        self.input_channel.exchange_declare(exchange=exchange,      # Create exchange
                                            type="topic",
                                            durable=False,
                                            auto_delete=True)

        self.input_channel.queue_declare( queue=queue,              # Create queue
                                          durable=False,
                                          exclusive=False,
                                          auto_delete=False)

        self.input_channel.queue_bind(queue=queue,                  # Bind queue to exchange
                                      exchange=exchange,
                                      routing_key=key)

        self.input_channel.basic_consume(queue=queue,               # Register the callback function
                                          no_ack=True,
                                          callback=cb,
                                          consumer_tag=tag)

        self.__consume()

    def __consume(self):
        """
        This blocks until disconnect() is called.
        # NOTE: see the diconnect()
        """      

        while self.messaging and self.input_channel.callbacks:
            try:
                self.input_channel.wait()
            except:
                self.messaging = False
                logging.debug("Consume loop is broken.")

    def disconnect(self, tag):
        """Disconnect from message-queue."""

        self.messaging = False

        try:
            logging.debug('Trying to close CONNECTION.')
            self.conn.close()

        except IOError:
            logging.debug("Closed connection, ungracefully...")
