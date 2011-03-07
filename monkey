#!/usr/bin/env python
import pprint
import time
import sys

import levislib.comm as comm

# Async callback for receiving messages
def recv_cb(msg):

    try:
        fd = open('monkey.out', 'a')
        payload = comm.unpack(msg.body)

        pprint.pprint(dir(msg))
        
        invocations = []            
        if isinstance(payload, dict):     # Single RPC invocation
            invocations = [ payload ]
        elif isinstance(payload, list):   # Multiple RPC invocations
            invocations = payload
        else:                             # Unsupported payload
            #
            # NOTE: The type-checks above is not sufficient to validate whether
            #       the request is actually a valid JSON-RPC invocation.
            #
            #       It is up to the RPC method itself to validate the input and
            #       to determine whether it has received the right amount of args!
            #
            logging.debug("Supported payload-type.")
            
        for inv in invocations:

            # Normalize the event
            if 'jsonrpc' in inv:
                print "JSONRPC"
                
            if 'result' in inv:                           # Result-event
                print "We got a result!"
                fd.write(pprint.pformat(payload))
    
            elif 'error' in payload:                            # Error-event
                print "oh no an error!", pprint.pformat(payload, depth=2)
                fd.write(pprint.pformat(payload))
            
        fd.close()

    except:
        print sys.exc_info()

if __name__ == "__main__":

    queue = "network_events"
    c = comm.Comm()

    c.subscribe( recv_cb, ['agent_output'] )
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        c.disconnect('sdf')
