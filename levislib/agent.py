#!/usr/bin/env python
"""
The Agent invokes methods via a set of "workers" in two ways:

  1. Immediate invocation
  2. Scheduled invocation

The main structure is illustrated below::

  +---------+
  | Agent   | Basic configuration management and facilitator.
  +-+-------+
    |
    |        +----------------+
    +--1:1-->| input_handler  |  Communication, listen for RPC requests.
    |        +----------------+
    +--1:1-->| output_handler |  Communication, RPC results and error events.
    |        +----------------+
    +--1:1-->| scheduler      |  Task Scheduling, determine when and by whom a task is executed.
    |        +----------------+
    |
    |        +---------+
    +--1:N-->| workers | Pool of workers, executing tasks.
             +---------+

The agent is thread-based and uses queues for inter-thread communication, with
"internal" messages on the form::

  instruction-message: ?? dunno yet ??
  result-message: (returncode, err, output)

The agent communicates with the outside world via beanstalk, "external" messages use the
`JSON-RPC protocol <http://groups.google.com/group/json-rpc/web/json-rpc-2-0>`_.

.. note::

  For the agent to be useful then the commands it is instructed to executed must be available on the systems path. Useful tools include: nc, nmap, ping, wmic, snmpwalk etc.

"""
import cStringIO as StringIO
import json as serializer
import subprocess
import threading
import datetime
import tempfile
import logging
import hashlib
import pprint
import Queue
import uuid
import time
import sys
import os

import levislib.comm as comm
import levislib.wmic as wmic

bufsize = 4096

class TimeoutInterrupt(Exception):
    pass

#
# "External" RPC methods
#

def cmd(params):
    """
    Execute cmdline, limit execution time to 'timeout' seconds.
    Uses the subprocess and subprocess.PIPE.

    Raises TimeoutInterrupt
    """

    try:
        cmdline = params['cmdline']
    except:
        raise ValueError("Insufficient parameters, missing 'cmdline'.")

    if 'timeout' in params:
        timeout = params['timeout']
    else:
        timeout = 60

    p = subprocess.Popen(
        cmdline,
        bufsize = bufsize,
        shell   = False,
        stdout  = subprocess.PIPE,
        stderr  = subprocess.PIPE
    )

    t_begin         = time.time()                         # Monitor execution time
    seconds_passed  = 0

    out = ''
    err = ''

    while p.poll() is None and seconds_passed < timeout:  # Monitor process state
        time.sleep(0.1)                                     # Wait a little
        seconds_passed = time.time() - t_begin
        out += p.stdout.read()                              # Read output
        err += p.stderr.read()

    if seconds_passed >= timeout:

        try:
            p.stdout.close()  # If they are not closed the fds will hang around until
            p.stderr.close()  # os.fdlimit is exceeded and cause a nasty exception
            p.terminate()     # Important to close the fds prior to terminating the process!
                              # NOTE: Are there any other "non-freed" resources?
        except:
            pass

        raise TimeoutInterrupt

    returncode  = p.returncode

    return (returncode, err, out)

def wmi(params):
    """
    Execute one or more wmi-queries.

    Raises: ValueError and Timeout.
    """

    try:                                  # Check params
        wmi_target = {
            'username': params['username'],
            'password': params['password'],
            'domain':   params['domain'],
            'hostname': params['hostname']
        }
        queries = params['queries']
    except:
        raise ValueError("Insufficient parameters.")

    if 'timeout' in params:
        timeout = params['timeout']
    else:
        timeout = 60

    cmdline = wmic.cmdline(wmi_target)    # Get a cmd-line

    returncode  = 0
    err = ''
    out = ''

    dict_out = {}

    for q in queries:                     # Execute quieres
        cmd_params = {
            'cmdline': cmdline+[q],
            'timeout': timeout
        }
        (cur_rc, cur_err, cur_out) = cmd(cmd_params)

        returncode = cur_rc
        err += cur_err
        out += cur_out

        if cur_rc != 0:                     # An error occured so we stop executing
            break

    if out:
        dict_out = wmic.to_dict(out)

    return (returncode, err, dict_out)

# Basic file-transfer
def put(params):
    return (0, '', 'Not yet implemented')

def get(params):
    return (0, '', 'Not yet implemented')

#
# TODO:
#
# - persist last-poll of win-events
# - persist task-list/schedule
# - Consider the "internal" message-format when sending "messages"
#   via the input/output queues. Perhaps JSON-RPC-like DICTS could be used.
#
# - consider how auth-info for wmic, ssh and others should be stored
#
# TODO-Testing:
#
# - prove seconds after midnight scheduling
# - prove that update() does not cause dead-locks
#

class Worker(threading.Thread):
    """Base class of worker for work-pool-like implementation."""

    w_count = 0

    def __init__(self, agent, device_id, input_queue, output_queue):

        self.agent        = agent         # The agent that the worker is "working for"
        self.device_id    = device_id     # Identifier for associating task-results with a device
        self.input_queue  = input_queue   # Incoming tasks
        self.output_queue = output_queue  # Outgoing task-results
        self.running      = True          # Control variable for termination of work

        Worker.w_count += 1
        threading.Thread.__init__(self, name='Worker-%d-%s' % (Worker.w_count, self.device_id))

    def run(self):

        while self.running:

            try:
                task     = self.input_queue.get(True, 1)  # Get a task!
                logging.debug('About to work on %s.' % task['method'])
                task_res = self.work(task)                # Work on that task!
                logging.debug('Done working on %s.' % task['method'])
                if task_res:
                    self.provide(task, task_res)            # Make the results available for others
                    logging.debug('In output queue.')
                else:
                    logging.debug('Nothing to publish.')
            except Queue.Empty:
                pass

    def stop(self):
        """Stops the worker."""

        # NOTE: Consider how to stop a worker while it is executing self.work/self.provide
        self.running = False

    #
    # This is the "interesting part", the stuff above is more or less boiler-plate
    #

    def work(self, task):
        """Execute the actual task, this method should be overridden."""
        return "Did nothing with: [%s]." % str(task)

    def provide(self, task, task_res):
        """Outputs result of the task."""
        self.output_queue.put((self.device_id, task, task_res))

class WinEventsCollector(Worker):
    """
    Gathers windows events via WMI-sampling
    This is a special-case of wmi-sampling where a specific hosts must be
    periodly polled without duplicates.
    """

    def __init__(self, agent, device_id, input_queue, output_queue, last_poll = "20000712153236.000000+120"):

        self.last_poll  = last_poll       # A random timestamp in the past
                                          # TODO: Persist last_poll on update
                                          # to avoid duplicate events.

        Worker.__init__(self, agent, device_id, input_queue, output_queue)

    def work(self, task):
        """
        The task MUST contain a 'logquery', the string: " TimeWritten > \"%s\"
        will be appended to 'logquery', 'logquery' must therefore always end
        with either::

          " WHERE "

        Or::

          " WHERE [your_conditions] AND "
        """

        time_condition  = " TimeWritten > \"%s\"" % self.last_poll
        event_query     = task['params']['logquery'] + time_condition

        wmi_params            = task['params']
        wmi_params['queries'] = [event_query]

        res = None
        try:
            returncode, err, wmi_classes = wmi( wmi_params )

            if  returncode == 0 and \
                wmi_classes.has_key('Win32_NTLogEvent') and \
                wmi_classes['Win32_NTLogEvent'][1] > 0:     # Something to publish?

                res = (returncode, err, wmi_classes)

                # Update last_poll, to avoid duplicate events
                # TODO: persist to disk fix!
                self.last_poll = wmi_classes['Win32_NTLogEvent'][1][-1][-3]

            elif returncode != 0:
                res = (returncode, err, None)

        except TimeoutInterrupt:
            res = (comm.JRPC_APP_TIMEOUT, 'Collection timeout', None)

        return res

class RpcCollector(Worker):
    """RPC-invocations."""

    def work(self, invocation):

        try:
            res = self.agent.invoke_rpc(invocation)
        except TimeoutInterrupt:
            res = (comm.JRPC_APP_TIMEOUT, 'RPC timeout.', None)

        return res

class Agent(comm.Comm):
    """
    Main orchestration logic, handles:

      * Worker lifecycle management
      * Listens for messages / input
      * Sends messages / results from remote invocations and other output events/messages

    """

    agent_count = 0

    #def __init__(self, agent_conf, amqp_conf, rpc_topic):
    def __init__(self, agent_conf):

        self.schedule = {}            # Work schedule, who does what and when!
        self.schedule_interval = 1    # How often is the schedule updated

        self.agent_conf   = agent_conf
        
        self.internal_rpc = ['ping', 'update']
        self.rpc_methods  = {
          'ping':     self.ping,      # Internal
          'update':   self.update,    # Internal

          'cmd':  cmd,                # External
          'wmi':  wmi,                # External
        }

        self.output_queue   = Queue.Queue() # A job-results queue, shared by all workers
        
        self.input_tube     = 'agent.in-' + self.agent_conf['agent_id']
        self.output_tube    = 'agent.out'
        
        self.running = False              # We are not running until run()/start() has been executed!
        
        self.scheduler_thread       = threading.Thread(target=self.scheduler,       name="Scheduler")
        self.output_handler_thread  = threading.Thread(target=self.output_handler,  name='OutputHandler')

        self.workers = {}             # Dict of workers

        comm.Comm.__init__(self, agent_conf['host'], agent_conf['port'])

        Agent.agent_count += 1

    def start(self):

        self.running = True
        
        for t in [self.scheduler_thread, self.output_handler_thread]:
            t.start()
            logging.debug('Started? %s...' % repr(t))
            
        self.subscribe(self.__handle_input, [self.input_tube])

        logging.debug('Started!')

    def stop(self):

        logging.debug("Stopping threads...")

        self.running = False
        try:
            self.disconnect(self.agent_conf["agent_id"])
        except:
            logging.debug("Something went wrong!", exc_info=3)

        logging.debug("Waiting for them to finish...")
        for t in [self.scheduler_thread, self.output_handler_thread]:  # Wait for them to finish their stuff
            t.join()

        logging.debug("Stopping workers...")
        self.stop_workers()
        logging.debug('And thats it! BYE!')

    def start_workers(self):

        for device_id in self.workers:
            for method in self.workers[device_id]:
                self.workers[device_id][method].start()

    def stop_workers(self):

        for device_id in self.workers:
            for method in self.workers[device_id]:
                self.workers[device_id][method].stop()

        for device_id in self.workers:
            for method in self.workers[device_id]:
                self.workers[device_id][method].join()

    #
    # This is the interesting part, the above is the boring part
    #

    def scheduler(self):   # Scheduling loop
        """Task Scheduling, determine when and which worker."""

        interval_sleep = self.schedule_interval

        while self.running:
            start = time.time()

            self.__schedule() # Interesting part! The actual call to scheduling-alg.

            elapsed = time.time() - start   # Time spend determining schedule
            interval_sleep = self.schedule_interval - elapsed

            if interval_sleep <= 0:         # Does the time spend exceed limits?
                logging.debug("Polling exceeds interval! AKA SYSTEM OVERLOAD!")
                interval_sleep = self.schedule_interval

            time.sleep(interval_sleep)

    def __schedule(self): # The scheduling algorithm

        # Seconds since midnight scheduling (type == 1) uses the values below.
        seconds_in_a_day       = 86400
        midnight  = datetime.datetime.now().replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )
        seconds_since_midnight = (datetime.datetime.now()-midnight).seconds

        for device_id in self.schedule:

            i=0
            for [name, type, seconds, countdown, method, params] in self.schedule[device_id]:

                if int(type) == 0: # Periodic scheduling uses the countdown variable

                    if countdown <= 0:            # It is time!

                        countdown = seconds         # Reset countdown
                        self.workers[device_id][method].input_queue.put({  # Enqueue task
                          'name':   name,
                          'method': method,
                          'params': params
                        })

                    else:                         # Countdown!
                        countdown -= self.schedule_interval

                    # Update the query
                    self.schedule[device_id][i] = [name, type, seconds, countdown, method, params]

                elif int(type) == 1: # Time of day scheduling / seconds since midnight

                    # TODO: verify that this wont invoke more than once!
                    if seconds < seconds_in_a_day and \
                      (seconds >= (seconds_since_midnight) and \
                       seconds < (seconds_since_midnight+self.schedule_interval)):

                        self.workers[device_id][method].input_queue.put({  # Enqueue task
                          'name':   name,
                          'method': method,
                          'params': params
                        })

                else:
                    logging.error('Schedule received unsupported schedule-type.')

                i+=1 # Index is used to update the countdown for periodic scheduling variable

    #
    # Communication
    #

    def output_handler(self):
        """
        Communication, send RPC results and error events.
        """

        while self.running:
            try:
                res = (device_id, task, task_res) = self.output_queue.get(True, 1)  # Grab output from output queue

                method_name   = 'Unknown'
                if 'method' in task:
                    method_name = task['method']

                if 'name' in task:
                    name = task['name']
                else:
                    name = method_name

                invocation_id = None
                if 'id' in task:
                    invocation_id = task['id']
                
                # Check for errors during execution
                (rc, err, out) = (None, None, None)
                try:
                    (rc, err, out) = task_res
                except:
                    logging.debug('OUTPUT-FORMAT-ERROR %s.' % repr(task_res))

                if err:
                    message = comm.pack(comm.rpc_error(rc, err, invocation_id, self.agent_conf['agent_id'], device_id))
                else:
                    message = comm.pack(comm.rpc_response(task_res, invocation_id, self.agent_conf['agent_id'], device_id))

                #publish_tube = "%s-%s" % (self.output_tube, name)
                logging.debug(comm.rpc_response(task_res, invocation_id, self.agent_conf['agent_id'], device_id))
                publish_tube = "%s-%s" % (self.output_tube, method_name)
                logging.debug('Publishing to [%s]...' % publish_tube)
                
                self.publish(message, publish_tube)

            except Queue.Empty:
                pass
            except:
                logging.debug('Noller!', exc_info=3)

    def __handle_input(self, msg):
       
        payload = comm.unpack(msg.body)

        logging.debug("At %d I got: telling me [%s]." % (time.time(), payload))
        
        try:

            #
            # JSON-RPC invocations are send as a dict, multiple invocations
            # can be requested by sending a list of dicts.
            # To simplify code then the handling of JSON-RPC-BATCH is implemented
            # and the JSON-RPC-SINGLE is converted to JSON-RPC-BATCH with just one
            # element in the list.
            #
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

            for invocation in invocations:    # Queue each method
                
                if invocation["method"] in self.internal_rpc:   # Invoke RPC
                    
                    self.output_queue.put((None, invocation, self.invoke_rpc(invocation)))
                    
                else:                                           # Enqueue RPC
                    self.workers[None][invocation['method']].input_queue.put(invocation)


        except:
            logging.debug('Error invoking RPC.', exc_info=3)

    #
    # INTERNAL - RPC METHODS
    #

    def invoke_rpc(self, invocation):
        """Invoke a method available and allowed by the agent."""

        method  = invocation['method']
        params  = invocation['params']

        try:
            res = self.rpc_methods[invocation["method"]](invocation["params"])
        except ValueError:
            res = (-32100, 'RPC-error, invalid parameters.', None)
        except TimeoutInterrupt:
            res = (-32110, 'RPC-error, timeout when executing.', None)
        except:
            res = (-32120, 'RPC-error, unknown error: %s.' % repr(sys.exc_info()), None)

        return res

    # Sort of a test of wheather the agent is responding
    def ping(self, void):
        """Simple RPC, useful to check whether the agent is 'alive'."""
        return (0, None, "PONG!")

    # Update the periodic / schedule based work
    def update(self, device_tasks):
        """Update schedule and instantiate workers to execute scheduled tasks."""

        logging.debug("RPC update args: %s." % repr(device_tasks))

        # 1. Create schedule from tasklist - the actual work of creating a schedule
        # 2. Instantiate new workers    - we need somebody to act on the schedule
        #
        # 3. Stop the scheduler            - if the scheduler is running it would
        #     assign tasks to non-existing workers and other error-situations.
        #
        # 4. Stop the current workers
        # 5. De-allocate the current workers
        #
        # 6. Assign the new schedule
        # 7. Assign the new workers
        #
        # 8. Start the workers
        # 9. Start the scheduler

        schedule_i      = {}                      # Schedule with increment variable
        workers         = {}
        worker_methods  = {}

        for device_id in device_tasks:              # 1. Create schedule from tasklist
            logging.debug("%s" % device_id)
            tasks = []
            for [name, type, seconds, method, params] in device_tasks[device_id]:

                # Add the countdown variable
                tasks.append([name, type, seconds, 0, method, params])

                if device_id in worker_methods:
                    worker_methods[device_id].add(method)
                else:
                    worker_methods[device_id] = set([method])

            schedule_i[device_id] = tasks

        for device_id in worker_methods:     # 2. Instantiate new workers

            workers[device_id] = {}
            for method in worker_methods[device_id]:

                worker_class = Worker             # Determine the worker type/class
                if method == 'win_events':
                    worker_class = WinEventsCollector
                elif method in self.rpc_methods:
                    worker_class = RpcCollector

                workers[device_id][method] = worker_class(
                  self,
                  device_id,
                  Queue.Queue(),
                  self.output_queue
                )
                                                    # 3. Stop the scheduler, TODO: implement

        # Always instantiate workers for "None" used for "immediate" invocations
        # notice: this None might already be instantiated!
        # so there might be redundant work done here...
        workers[None] = {}
        for method in self.rpc_methods:
            workers[None][method] = RpcCollector(
                self,
                None,
                Queue.Queue(),
                self.output_queue
            )

        # Always instantiate workers for:
        # - "None" used for "immediate" invocations
        # - "Internal" used for "immediate" update/heartbeat
        workers[None] = {}
        for method in self.rpc_methods:
            workers[None][method] = RpcCollector(
                self,
                None,
                Queue.Queue(),
                self.output_queue
            )

        self.stop_workers()                     # 4. Stop the current workers
        del(self.workers)                       # 5. De-allocate the current workers

        self.schedule = schedule_i              # 6. Assign the new schedule
        self.workers  = workers                 # 7. Assign the new workers

        self.start_workers()                    # 8. Start the workers
                                                # 9. Start scheduler, TODO: implement

        del(schedule_i, workers, worker_methods) # NOTE: is this necassary?

        return (0, None, "Executed update.")  # TODO: Figure out what kind of output would be usefull here...
