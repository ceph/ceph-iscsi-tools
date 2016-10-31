#!/usr/bin/env python
__author__ = 'Paul Cuzner'

import time
import threading
import sys

from gwtop.utils.kbd import TerminalFile
from gwtop.utils.data import bytes2human
from gwtop.UI.datamanager import summarize
from gwtop.config.ceph import CephCluster


class TextMode(threading.Thread):
    """
    Class that provides the text mode of the tool. An object of this
    class runs as a thread
    """

    ceph_update_interval = 30

    def __init__(self, config, pcp_threads):
        threading.Thread.__init__(self)
        self.config = config
        self.pcp_collectors = pcp_threads
        self.terminal = None
        self.ceph = CephCluster()
        self.ceph_health = ''
        self.ceph_osds = 0

    def sort_stats(self, in_dict):
        """
        sort the disk_summary by any sort keys requested, returning the
        pool/image name sequence that adheres to the sort request
        @param in_dict: dict of objects (indexed by pool/image)
        :return: keys to use to adhere to the sort keys
        """

        sort_key = self.config.opts.sortkey
        reverse_mode = self.config.opts.reverse

        if sort_key == 'image':
            sorted_keys = sorted(in_dict, reverse=reverse_mode)
        else:
            sorted_keys = sorted(in_dict,
                                 key=lambda keyname: getattr(in_dict[keyname], sort_key),
                                 reverse=reverse_mode)

        return sorted_keys

    def show_stats(self, gw_stats, disk_summary):
        """
        Display the aggregated stats to the console
        :param gw_stats: gateway metrics (cpu, network)
        :param disk_summary: disk summary information (dict) indexed by pool/rbd_image
        :return: nothing
        """

        num_gws = len(gw_stats.cpu_busy)
        desc = "Gateways" if num_gws > 1 else "Gateway"
        total_gateways = len(self.config.gateway_config.gateways)
        gw_summary = "{}/{}".format(num_gws, total_gateways)

        print("gwtop  {:>3} {:<8}   CPU% MIN:{:>3.0f} MAX:{:>3.0f}    Network Total In:{:>6}"
              "  Out:{:>6}   {}".format(gw_summary,
                                        desc,
                                        gw_stats.min_cpu,
                                        gw_stats.max_cpu,
                                        bytes2human(gw_stats.total_net_in),
                                        bytes2human(gw_stats.total_net_out),
                                        gw_stats.timestamp))

        print("Capacity: {:>5}    IOPS: {:>5}   Clients:{:>3}   Ceph: {:<26}   "
              "OSDs: {:>4}".format(
                                bytes2human(gw_stats.total_capacity),
                                gw_stats.total_iops,
                                self.config.gateway_config.client_count,
                                self.ceph_health,
                                self.ceph_osds))

        print("Pool.Image        Src  Device   Size     r/s     w/s    rMB/s     wMB/s"
              "    await  r_await  w_await  Client")

        # Metrics shown sorted by pool/image name by default

        for devname in self.sort_stats(disk_summary):

            if devname in self.config.gateway_config.diskmap:
                client = self.config.gateway_config.diskmap[devname]
            else:
                client = ''

            print("{:<16}  {:^3}  {:^6}   {:>4}   {:>5}   {:>5}   {:>6.2f}    {:>6.2f}   {:>6.2f}"
                  "   {:>6.2f}   {:>6.2f}  {:<20}".format(devname,
                                                          disk_summary[devname].io_source,
                                                          disk_summary[devname].rbd_name,
                                                          bytes2human(disk_summary[devname].disk_size),
                                                          int(disk_summary[devname].tot_reads),
                                                          int(disk_summary[devname].tot_writes),
                                                          disk_summary[devname].tot_readkb/1024,
                                                          disk_summary[devname].tot_writekb/1024,
                                                          disk_summary[devname].max_await,
                                                          disk_summary[devname].max_r_await,
                                                          disk_summary[devname].max_w_await,
                                                          client))
        # put a blank line between iterations
        print

    def reset(self):
        """
        return the console environment to normal
        """
        self.terminal.reset()

    def update_ceph(self):
        """
        Run the ceph objects health method at regular intervals
        """
        self.ceph.update_state()
        self.ceph_health = self.ceph.health
        self.ceph_osds = self.ceph.osds
        threading.Timer(TextMode.ceph_update_interval, self.update_ceph).start()

    def refresh_display(self):
        """
        Aggregate the stats, and display at a set interval
        """
        gw_stats, disk_summary = summarize(self.config, self.pcp_collectors)
        self.show_stats(gw_stats, disk_summary)
        threading.Timer(self.config.sample_interval, self.refresh_display).start()

    def run(self):
        """
        Main method for the thread. Creeate the timers to refresh the data, and
        loop until the user hit's 'q' or CTRL-C
        """

        term = TerminalFile(sys.stdin)
        self.terminal = term

        # start the periodic functions
        self.update_ceph()
        self.refresh_display()

        # Loop to handle ctrl-c or 'q' interaction with the user
        while 1:
            try:
                time.sleep(0.5)

                c = term.getch()
                if c == 'q':
                    break
            except KeyboardInterrupt:
                print "breaking from thread"
                break

        self.reset()

        # exit the thread
