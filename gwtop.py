#!/usr/bin/env python

import argparse
import time
import sys
import logging
import os
import re

try:
    from ConfigParser import ConfigParser
except ImportError:
    from configparser import ConfigParser

from threading import Event
import threading

from gwtop.collectors.pcp_provider import PCPcollector
from gwtop.config.generic import Config
from gwtop.config.local import get_device_info
from gwtop.config.lio import get_gateway_info
from gwtop.UI.textmode import TextMode

import ceph_iscsi_config.settings as settings

# Supported config file locations/names
CFG_FILES = ['/etc/gwtop.rc',
             os.path.join(os.path.expanduser('~'), '.gwtop.rc')
             ]


def setup_thread_excepthook():
    """
    Exceptions in threads don't trigger the normal sys.excepthook definition.
    This function overrides the threading.Thread.__init__ method to allow
    threads to adhere to the same exception handling as the main process.

    This is a common approach, and is discussed here
    http://bugs.python.org/issue1230540

    """

    init_original = threading.Thread.__init__

    def init(self, *args, **kwargs):

        init_original(self, *args, **kwargs)
        run_original = self.run

        def run_with_except_hook(*args2, **kwargs2):
            try:
                run_original(*args2, **kwargs2)
            except Exception:
                sys.excepthook(*sys.exc_info())

        self.run = run_with_except_hook

    threading.Thread.__init__ = init


def exception_handler(exception_type, exception, traceback,
                      debug_hook=sys.excepthook):

    if term:
        # reset the terminal config
        term.reset()

    if options.debug:
        debug_hook(exception_type, exception, traceback)
    else:
        print("{}: {}".format(exception_type.__name__, exception))


def main():
    config = Config()
    config.opts = options
    config.devices = device_map

    if not config.devices:
        print ("Error: No devices have been detected on this host, "
               "unable to continue")
        sys.exit(12)

    config.gateway_config = get_gateway_info(options)
    if config.gateway_config.error:
        # Problem determining the environment, so abort
        print("Error: Unable to determine the gateway configuration")
        sys.exit(12)

    config.sample_interval = options.interval
    collector_threads = []
    sync_point = Event()
    sync_point.clear()

    if options.debug:
        if options.gateways:
            print("Using gateway names from the config file(s)/run time "
                  "parameters")
        else:
            print("Using gateway names from the configuration object defined "
                  "by the ansible modules")

        logger.info("Attempting to open connections to pmcd daemons on the {}"
                    " gateway node(s) ({})".format(len(config.gateway_config.gateways),
                                                   ','.join(config.gateway_config.gateways)))

    # NB. interval must be a string, defaulting to 1 for testing
    for gw in config.gateway_config.gateways:

        collector = PCPcollector(logger,
                                 sync_point,
                                 host=gw,
                                 interval=config.sample_interval,
                                 pcp_type=options.provider)

        # check the state of the collector
        if collector.connected:
            collector.daemon = True
            collector.start()
            collector_threads.append(collector)
        else:
            del collector
            logger.error("Error: Unable to connect to pmcd daemon on {}".format(gw))

    # Continue as long as we have at least 1 collector connected to a pmcd
    if len(collector_threads) > 0:

        sync_point.set()

        if options.mode == 'text':
            interface = TextMode(config, collector_threads)
            interface.daemon = True

            # link the term variable to the textmode interface
            global term
            term = interface

        interface.start()

        try:
            # wait until the interface thread exits
            while interface.isAlive():
                time.sleep(0.2)
        except KeyboardInterrupt:
            # reset the terminal settings
            interface.reset()
    else:
        logger.critical("Unable to continue, no pmcd's are available on the"
                        " gateways to connect to. Is pmcd running on the "
                        "gateways?")


def valid_filter(dev_filter="*"):

    try:
        re.compile(dev_filter)
    except re.error:
        return False
    else:
        return True


def get_options():

    num_user_luns = sum([1 for id in device_map
                         if device_map[id]['lun_type'] == 'user'])

    default_collector = 'dm' if num_user_luns == 0 else 'lio'

    sort_fields = {"dm": ['image', 'iops', 'rbd_name', 'reads', 'writes',
                          'await', 'io_source'],
                   "lio": ['image', 'iops', 'io_source', 'tot_read_mb',
                           'tot_write_mb']}

    # establish the defaults based on any present config file(s) config section
    defaults = {}
    config = ConfigParser()
    dataset = config.read(CFG_FILES)
    if len(dataset) > 0:
        if config.has_section("config"):
            defaults.update(dict(config.items("config")))
            if 'reverse' in defaults:
                defaults['reverse'] = True if defaults['reverse'].lower() == 'true' else False
        else:
            print("Config file detected, but the format is not supported. "
                  "Ensure the file has a single section [config], and "
                  "declares settings like 'gateways' or 'interval'")
            sys.exit(12)
    else:
        # no config files detected, to seed the run time options
        pass

    # Set up the runtime overrides, any of these could be provided by the
    # cfg file(s)
    parser = argparse.ArgumentParser(prog='gwtop',
                                     description='Show iSCSI gateway performance metrics')
    parser.add_argument('-b', '--busy-only', action='store_true',
                        default=False,
                        help='show only active devices (iops > 0)')
    parser.add_argument('-c', '--config-object', type=str,
                        help='pool and object name holding the gateway config '
                             'object (pool/object_name)')
    parser.add_argument('--debug', action='store_true',
                        default=False,
                        help='run with additional debug')
    parser.add_argument('-d', '--device-filter', type=str,
                        default='.*',
                        help='device name filter (default is .* i.e. '
                             'everything!)')
    parser.add_argument('-g', '--gateways', type=str,
                        help='comma separated iscsi gateway server names')
    parser.add_argument('-i', '--interval', type=int,
                        choices=range(1, 10),
                        help='monitoring interval (secs)')
    parser.add_argument('-l', '--limit', type=int,
                        default=9999,
                        help='sepcifiy the number of devices to show per '
                             'sample iteration')
    parser.add_argument('-m', '--mode', type=str,
                        choices=(['text']),
                        help='output mode')
    parser.add_argument('-p', '--provider', type=str,
                        choices=['dm', 'lio'],
                        default=default_collector,
                        help='pcp provider type lio or dm')
    parser.add_argument('-s', '--sortkey', type=str,
                        default='image',
                        help='sort key field name (dependent upon provider - '
                             'see man page for more info)')
    parser.add_argument('-t', '--top-10', action='store_true',
                        default=False,
                        help='show the top 10 LUNs with highest iops')
    parser.add_argument('-r', '--reverse', action='store_true', default=False,
                        help='use reverse sort when displaying the stats')
    parser.add_argument('-v', '--version',
                        action='version',
                        version='%(prog)s 2.2')

    # use the defaults dict for the options
    parser.set_defaults(**defaults)

    # create the opts object which combines the defaults from the config
    # file(s) + runtime overrides
    opts = parser.parse_args()

    # establish defaults, just in case they're missing from the config
    # file(s) AND run time call
    if not opts.interval:
        opts.interval = 1
    if not opts.mode:
        opts.mode = 'text'
    if not opts.config_object:
        opts.config_object = 'rbd/gateway.conf'

    # if the sort key is not the default, validate it against the
    # specific pcp providers sort fields list
    if opts.sortkey != 'image':
        if opts.sortkey not in sort_fields[opts.provider]:
            print("Invalid sort key provided for the requested pcp provider")
            print("For {}, the options are {}".format(opts.provider,
                                                      sort_fields[opts.provider]))
            sys.exit(12)

    # Ensure any device filter name is valid
    if not valid_filter(opts.device_filter):
        print("Invalid device filter specification, must be python regex "
              "compatible")
        sys.exit(16)

    if opts.top_10:
        opts.sortkey = 'iops'
        opts.limit = 10
        opts.reverse = True

    return opts


if __name__ == '__main__':

    settings.init()

    # establish the device map early so we can determine which collector to
    # use by default
    device_map = get_device_info()

    options = get_options()

    term = None

    # Override the default exception handler to only show back traces
    # in debug mode
    sys.excepthook = exception_handler

    setup_thread_excepthook()

    # define logging to the console
    # set the format to just the msg
    logger = logging.getLogger("gwtop")
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()

    if options.debug:
        ch.setLevel(logging.DEBUG)
    else:
        ch.setLevel(logging.INFO)

    fmt = logging.Formatter('%(message)s')
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    main()
