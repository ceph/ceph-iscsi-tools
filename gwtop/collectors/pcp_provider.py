#!/usr/bin/env pmpython

import threading

from pcp import pmapi, pmcc
from gwtop.config.generic import DiskMetrics, GatewayMetrics
import re
import os
import glob
from rtslib_fb.utils import fread

# group metrics
IOSTAT_METRICS = ['disk.dm.read', 'disk.dm.read_bytes',
                  'disk.dm.write', 'disk.dm.write_bytes',
                  'disk.dm.read_rawactive', 'disk.dm.write_rawactive']

NETWORK_METRICS = ['network.interface.in.bytes', 'network.interface.out.bytes']

# single metric
CPU_METRICS = ['kernel.all.cpu.idle', 'kernel.all.load', 'hinv.ncpu']

class CollectorError(Exception):
    pass


class RBDMap(object):

    def __init__(self):
        self.map = {}
        self.refresh()

    def refresh(self):
        self._get_map()

        if not self.map:
            raise CollectorError("RBDMAP: Unable to create the dm -> rbd_name lookup table")

    def _get_map(self):
        """
        Convert dm devices into their pool/rbd_image name. All gateway nodes should see
        the same rbds, and each rbd when mapped through device mapper will have the same
        name, so this gives us a common reference point.
        """

        dm_devices = glob.glob('/dev/mapper/[0-255]-*')

        if dm_devices:
            for dm_path in dm_devices:
                key = os.path.basename(dm_path)                     # e.g. 0-198baf12200854
                dm_id = os.path.realpath(dm_path).split('/')[-1]    # e.g. dm-4
                rbd_device = os.listdir('/sys/class/block/{}/slaves'.format(dm_id))[0]    # rbdX
                rbd_num = rbd_device[3:]                            # X
                pool = fread('/sys/devices/rbd/{}/pool'.format(rbd_num))
                image = fread('/sys/devices/rbd/{}/name'.format(rbd_num))

                self.map[key] = {"rbd_name": "{}.{}".format(pool, image),
                                 "rbd_dev": rbd_device}


class IOstatOptions(pmapi.pmOptions):
    """
    Define the options parser object needed by the pmcc.MetricGroupManager
    object
    """

    def __init__(self, host):
        pmapi.pmOptions.__init__(self, "h:t:")
        self.pmSetLongOptionHost()
        self.pmSetLongOptionInterval()


class PCPextract(pmcc.MetricGroupPrinter):
    """
    Class based on the pcp-iostat example code that provides disk/network and cpu metrics for the given
    node (thread)
    """

    NIC_BLACKLIST = ['lo', 'docker0']
    HDRcount = 0
    device_regex = '[0-255]-[a-f,0-9]+'

    def __init__(self, metrics):
        pmcc.MetricGroupPrinter.__init__(self)
        self.metrics = metrics
        self.rbds = RBDMap()

    def timeStampDelta(self, group):
        s = group.timestamp.tv_sec - group.prevTimestamp.tv_sec
        u = group.timestamp.tv_usec - group.prevTimestamp.tv_usec
        # u may be negative here, calculation is still correct.
        return s + u / 1000000.0

    def instlist(self, group, name):
        return dict(map(lambda x: (x[1], x[2]), group[name].netValues)).keys()

    def curVals(self, group, name):
        return dict(map(lambda x: (x[1], x[2]), group[name].netValues))

    def prevVals(self, group, name):
        return dict(map(lambda x: (x[1], x[2]), group[name].netPrevValues))

    def report(self, manager):
        subtree = 'disk.dm'

        # print "DEBUG - in report function"

        group = manager["gateways"]

        nic_list = self.instlist(group, 'network.interface.in.bytes')

        all_disks = self.instlist(group, subtree + '.read')    # just use reads to get all disk instance names

        # rbd device mapped for the gateway use the following naming convention
        # <pool_id>-<rbd uid>
        instlist = [disk_id for disk_id in all_disks if re.search(PCPextract.device_regex, disk_id) is not None]
        # print "DEBUG - devices found %s " % instlist

        if group[subtree + '.read'].netPrevValues is None:
            # need two fetches for the cur/prev deltas to work
            return

        dt = self.timeStampDelta(group)

        timestamp = group.contextCache.pmCtime(int(group.timestamp)).rstrip()

        # dm metrics
        c_r = self.curVals(group, subtree + '.read')
        p_r = self.prevVals(group, subtree + '.read')

        c_w = self.curVals(group, subtree + '.write')
        p_w = self.prevVals(group, subtree + '.write')

        c_rkb = self.curVals(group, subtree + '.read_bytes')
        p_rkb = self.prevVals(group, subtree + '.read_bytes')

        c_wkb = self.curVals(group, subtree + '.write_bytes')
        p_wkb = self.prevVals(group, subtree + '.write_bytes')

        c_ractive = self.curVals(group, subtree + '.read_rawactive')
        p_ractive = self.prevVals(group, subtree + '.read_rawactive')

        c_wactive = self.curVals(group, subtree + '.write_rawactive')
        p_wactive = self.prevVals(group, subtree + '.write_rawactive')

        # NIC metrics
        c_nic_in_b = self.curVals(group, 'network.interface.in.bytes')
        p_nic_in_b = self.prevVals(group, 'network.interface.in.bytes')
        c_nic_out_b = self.curVals(group, 'network.interface.out.bytes')
        p_nic_out_b = self.prevVals(group, 'network.interface.out.bytes')

        # CPU metrics
        #
        # load could be used for 1 minute/5minute/15minute data
        # load_idle = self.curVals(group, 'kernel.all.load')

        # get the number of cpu's on this host to calculate cpu utilisation
        num_cpus = self.curVals(group, 'hinv.ncpu')['']

        c_k_idle = float(self.curVals(group, 'kernel.all.cpu.idle')[''])
        p_k_idle = float(self.prevVals(group, 'kernel.all.cpu.idle')[''])
        cpu_multiplier = self.metrics.interval * 1000
        self.metrics.timestamp = timestamp
        idle = 100 * (float(c_k_idle - p_k_idle) / (num_cpus * cpu_multiplier))
        self.metrics.cpu_idle_pct = idle if idle >= 0 else 0
        busy = 100 - float(self.metrics.cpu_idle_pct)
        self.metrics.cpu_busy_pct = busy if busy >= 0 else 0


        # TODO : restrict this to only rbd devices...
        try:
            tot_in = tot_out = 0
            for nic in nic_list:
                if nic in PCPextract.NIC_BLACKLIST:
                    continue
                tot_in += (c_nic_in_b[nic] - p_nic_in_b[nic]) / dt
                tot_out += (c_nic_out_b[nic] - p_nic_out_b[nic]) / dt

            self.metrics.nic_bytes = {'in': tot_in, 'out': tot_out}

            for inst in sorted(instlist):

                try:
                    # get pool/image name for the dm name from the lookup table
                    key = self.rbds.map[inst]['rbd_name']
                except KeyError:
                    self.rbds.refresh()
                    if inst in self.rbds.map:
                        key = self.rbds.map[inst]['rbd_name']
                    else:
                        raise CollectorError("PCPExtract: Unable to convert {} to a pool/image name".format(inst))

                if key not in self.metrics.disk_stats:
                    self.metrics.disk_stats[key] = DiskMetrics()

                self.metrics.disk_stats[key].dm_device = inst
                self.metrics.disk_stats[key].read = (c_r[inst] - p_r[inst]) / dt

                self.metrics.disk_stats[key].write = (c_w[inst] - p_w[inst]) / dt
                self.metrics.disk_stats[key].readkb = (c_rkb[inst] - p_rkb[inst]) / dt
                self.metrics.disk_stats[key].writekb = (c_wkb[inst] - p_wkb[inst]) / dt

                tot_rios = (float)(c_r[inst] - p_r[inst])
                tot_wios = (float)(c_w[inst] - p_w[inst])
                tot_ios = (float)(tot_rios + tot_wios)

                self.metrics.disk_stats[key].await = (((c_ractive[inst] - p_ractive[inst]) +
                                                       (c_wactive[inst] - p_wactive[inst]))
                                                        / tot_ios) if tot_ios else 0.0

                self.metrics.disk_stats[key].r_await = ((c_ractive[inst] - p_ractive[inst])
                                                         / tot_rios) if tot_rios else 0.0

                self.metrics.disk_stats[key].w_await = ((c_wactive[inst] - p_wactive[inst])
                                                         / tot_wios) if tot_wios else 0.0

        except KeyError:
            # ignore missing instance (from previous sample)
            pass

        pass


class PCPcollector(threading.Thread):
    """
    Parent thread object which runs an instance of the pcp metric
    collector for a given host
    """

    def __init__(self, logger, sync_event, host='', interval='1'):
        threading.Thread.__init__(self)
        self.hostname = host
        self.start_me_up = sync_event
        self.logger = logger

        opts = IOstatOptions(host)
        self.context = None

        # The manager object builds it's options from the command line
        # parameters, so we simulate that with a list
        args_list = ['', '-h', host, '-t', str(interval)]
        try:
            self.manager = pmcc.MetricGroupManager.builder(opts, args_list)
            self.manager["gateways"] = IOSTAT_METRICS + CPU_METRICS + NETWORK_METRICS
            self.metrics = GatewayMetrics()
            self.metrics.cpu_busy_pct = 0
            self.metrics.cpu_idle_pct = 0
            self.metrics.interval = interval
            self.metrics.timestamp = None
            self.metrics.disk_stats = {}
            self.metrics.nic_bytes = {'in': 0, 'out': 0}
            self.manager.printer = PCPextract(self.metrics)

            self.connected = True
        except pmapi.pmErr:
            self.connected = False

    def run(self):
        # grab the data and store in dict every second
        self.logger.debug("pcp manager thread started for host {}".format(self.hostname))

        self.start_me_up.wait()
        self.manager.run()

    def get_values(self):
        # return values for this object to the caller
        return self.stats
