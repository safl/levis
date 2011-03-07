#!/usr/bin/env python
"""
 Helper-functions for execution and output-parsing of the 'wmic' command-line.
"""

def cmdline(wmi_target, sep='<|>'):
    """Creates a list of parameters for use with subprocess.Popen."""

    return [
        'wmic',
        "--delimiter=%s" % sep,
        "-U",
        wmi_target["username"]+'%'+wmi_target["password"],
        '%s//%s'  % (wmi_target["domain"],    wmi_target["hostname"])
    ]

def split_ws(input, seps_per_line=24, eol='\n', sep='<|>'):
    """
    Splits a string into a list of lines, using the seperator ('sep').

    The input is expected to be on a CSV-like format such as::

      Val1<SEP>Val2<SEP>Val3<SEP>Val4<SEP>Val5\eol
      Val6<SEP>Val7<SEP>Val8<SEP>Val9<SEP>Val10\eol

    Which would result in output on the form::

      [
        [Val1, Val2, Val3, Val4, Val5],
        [Val6, Val7, Val8, Val9, Val10]
      ]
    """

    sep_count = 0

    cur_sep   = ''
    cur_line  = ''

    lines = []

    for c in input:

        cur_line += c

        # Count seperators
        if c == sep[len(cur_sep)]:
            cur_sep += c
            if cur_sep == sep:
                sep_count += 1
                cur_sep = ''
        else:
            cur_sep = ''

        # Split the line if a sufficient amount of seperators has ben spotted
        if c == eol and (sep_count % seps_per_line) is 0:
            lines.append(cur_line)
            cur_line = ''

    return lines

def to_dict(query_output, sep='<|>'):
    """
    Converts the raw output from a wmic execution to a dict, example::

      {'Win32_LogicalDisk': [
        ['DeviceID', 'Name', 'VolumeName'],
        [ ['A:', 'A:', '(null)'],
          ['C:', 'C:', ''],
          ['D:', 'D:', '(null)']
        ]
      ]}

    In prose: the wmi-provider is the dict-key, mapping to a list of lists.

      * The first list contains "header-names" ['DeviceID', 'Name', 'VolumeName'].
      * The second list contains a list of values ['C:', 'C:', ''].
      * The ordering and length of the header-list is equal the value-lists.

    The dict can contain multiple wmi-providers.
    """

    wmi_collected = {}
    wmi_classes   = query_output.split('CLASS: ')[1:]

    for wmi_class in wmi_classes:

        wmi_raw = wmi_class.split('\n', 2)
        if len(wmi_raw) is 3:
            (wmi_provider_raw, wmi_attr_raw, wmi_values_raw) = wmi_raw

            wmi_attr    = wmi_attr_raw.replace('\n','').split(sep)
            wmi_values  = [x.split(sep) for x in split_ws(wmi_values_raw, len(wmi_attr)-1)]
            wmi_collected[wmi_provider_raw] = (wmi_attr, wmi_values)

    return wmi_collected

def pretty_print(query_output):
    """
    Pretty-prints the query results on a form like::

      Win32_Service
      Name:   VNC Server
      Displayname:  UVNC
      ...
    """

    (returncode, err, wmi_raw) = query_output
    if returncode == 0:           # Successful output

        wmi_collected = query_dict(query_output)
        for wmi_data in wmi_collected:
            print "[", wmi_data
            h = wmi_collected[wmi_data][0]
            values = wmi_collected[wmi_data][1]
            for v in values:
                for i in xrange(0, (len(h))):
                    print h[i] +' : '+ v[i]
                print "]"

    else:                             # Error output
        print err
