#!/usr/bin/env python

"""
This script can help clear out selected rabbitmq queues and helps to
ensure that *only* transient queues are cleared (vs notifications queues
which should not be cleared due to side-effects this causes when those
queues are cleared).
"""

from __future__ import print_function

import argparse
import os
import subprocess
import sys

# Taken from a *liberty* CAP and MAP capture of the
# output of `rabbitmqctl list_queues`
QUEUE_ROOTS = tuple([
    ('cells.intercell.broadcast', True),
    ('cells.intercell.response', True),
    ('cells.intercell.targeted', True),
    ('cells.', True),
    ('cells_fanout', True),
    ('cert', False),
    ('cinder-backup', False),
    ('cinder-scheduler', False),
    ('compute', False),
    ('conductor', False),
    ('console', False),
    ('consoleauth', False),
    ('dhcp_agent', False),
    ('engine', False),
    ('heat-engine-listener', False),
    ('l3_agent', False),
    ('q-agent-notifier-dvr-update', False),
    ('q-agent-notifier-network-update', False),
    ('q-agent-notifier-port-delete', False),
    ('q-agent-notifier-port-update', False),
    ('q-agent-notifier-security_group-update', False),
    ('q-agent-notifier-tunnel-delete', False),
    ('q-agent-notifier-tunnel-update', False),
    ('q-l3-plugin', False),
    ('q-plugin', False),
    # All reply queues should be ok to purge as they will either
    # just timeout or retry (or that's the desired goal).
    ('reply_', True),
    ('scheduler', False),
])

# Most queues get either '${root}_fanout.*' related queues or
# '${root}.some_uuid' or '${root}.some_hostname' formats so these will
# capture all of those as these will be appended to the root and will
# match if they are a prefix of a queue name.
AUTO_PREFIX_SUFFIXES = tuple(["_fanout", "."])


def prompt_for_purge(queue_count):
    input = ""
    while input == "":
        input = raw_input("Purge %s queues? " % (queue_count))
        input = input.lower().strip()
        if input not in ('yes', 'no', 'y', 'n'):
            print("Please enter one of 'yes' or 'no'")
            input = ""
        else:
            if input in ['yes', 'y']:
                return True
            else:
                return False


def should_purge_queue(queue_name, size):
    for r, is_prefix in QUEUE_ROOTS:
        if r == queue_name:
            # Don't delete the roots themselves...
            return False
        # Otherwise check if we should try a bunch of prefix or just
        # check the prefix itself...
        if is_prefix and queue_name.startswith(r):
            return True
        else:
            for prefix_suffix in AUTO_PREFIX_SUFFIXES:
                if queue_name.startswith(r + prefix_suffix):
                    return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-d", "--dry_run",
                        action='store_true', default=False,
                        help="simulate purge commands but do not"
                             " actually run them")
    parser.add_argument("-e", "--ensure_gone",
                        action='append', default=[],
                        help="ensure named queue is purged",
                        metavar="queue")
    parser.add_argument("-n", "--no_prompt",
                        action='store_true', default=False,
                        help="skip being prompted before purging")
    parser.add_argument("-u", "--username",
                        help=("purge via a connection"
                              " using given username (default=%(default)s)"),
                        default='guest')
    parser.add_argument("-p", "--password",
                        help=("purge via a connection using"
                              " given password (default=%(default)s)"),
                        default='guest')
    args = parser.parse_args()
    if os.getuid() != 0:
        # We can't run rabbitmqctl or rabbitmqadmin without root
        # so make sure we have it...
        print("This program must be ran as root!", file=sys.stderr)
        sys.exit(1)
    # This tries to get the list queues output and then parses it to
    # try to figure out why queues we should try to clear, this is not
    # a formal (sadly it appears there is none) so this may break
    # at some point in the future...
    stdout = subprocess.check_output(['rabbitmqctl', 'list_queues'])
    # The first line is expected to be 'Listing queues ...'
    lines = stdout.splitlines()
    first_line = lines[0]
    if first_line != "Listing queues ...":
        print("First line of the output of `rabbitmqctl list_queues`"
              " was not as expected, avoiding further damage by exiting"
              " early!", file=sys.stderr)
        sys.exit(1)
    goodbye_queues = []
    queues = sorted(lines[1:])
    if queues:
        print("There are %s queues..." % (len(queues)))
        for i, line in enumerate(queues):
            queue_name, str_size = line.split()
            if (queue_name in args.ensure_gone
                    or should_purge_queue(queue_name, int(str_size))):
                print("%s. %s (purging)" % (i + 1, queue_name))
                goodbye_queues.append(queue_name)
            else:
                print("%s. %s (not purging)" % (i + 1, queue_name))
    if not args.dry_run and goodbye_queues:
        if not args.no_prompt:
            if not prompt_for_purge(len(goodbye_queues)):
                sys.exit(0)
        print("Executing %s purges, please wait..." % (len(goodbye_queues)))
        for queue_name in goodbye_queues:
            purge_cmd = [
                'rabbitmqadmin', 'purge', 'queue', 'name=%s' % queue_name,
            ]
            if args.username:
                purge_cmd.extend(['-u', args.username])
            if args.password:
                purge_cmd.extend(['-p', args.password])
            subprocess.check_output(purge_cmd)


if __name__ == '__main__':
    main()
