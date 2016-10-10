#!/usr/bin/env pmpython

import threading

from pcp import pmapi, pmcc
from gwtop.config.generic import DiskMetrics, GatewayMetrics
import subprocess
import json


# group metrics
# IOSTAT_METRICS = ['disk.dev.read', 'disk.dev.read_bytes',
#                   'disk.dev.write', 'disk.dev.write_bytes',
#                   'disk.dev.read_rawactive', 'disk.dev.write_rawactive']
IOSTAT_METRICS = ['disk.partitions.read', 'disk.partitions.read_bytes',
                  'disk.partitions.write', 'disk.partitions.write_bytes',
                  'disk.partitions.read_rawactive', 'disk.partitions.write_rawactive']

# other metrics that could be useful
#                  'disk.dev.read_rawactive', 'disk.dev.write_rawactive', 'disk.dev.avactive'

NETWORK_METRICS = ['network.interface.in.bytes', 'network.interface.out.bytes']

# single metric
CPU_METRICS = ['kernel.all.cpu.idle', 'kernel.all.load', 'hinv.ncpu']


class RBDMap(object):

    def __init__(self):
        self.map = {}
        self.refresh()

    def refresh(self):
        self._get_map()

    def _get_map(self):

        try:
            map_out = subprocess.check_output('rbd showmapped --format=json', shell=True)
        except subprocess.CalledProcessError:
            pass
        else:
            map_json = json.loads(map_out)
            for dev_id in map_json:
                devname = 'rbd{}'.format(dev_id)
                pool = map_json[dev_id]['pool']
                image_name = map_json[dev_id]['name']
                key = "{}/{}".format(pool, image_name)
                self.map[devname] = key


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
    valid_devices = ('rbd')

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
        subtree = 'disk.partitions'

        # print "DEBUG - in report function"

        group = manager["gateways"]

        nic_list = self.instlist(group, 'network.interface.in.bytes')
        all_disks = self.instlist(group, subtree + '.read')    # just use reads to get all disk instance names
        instlist = [disk_id for disk_id in all_disks if disk_id.startswith(PCPextract.valid_devices)]
        # print "DEBUG - devices found %s " % instlist

        if group[subtree + '.read'].netPrevValues is None:
            # need two fetches for the cur/prev deltas to work
            return

        dt = self.timeStampDelta(group)

        timestamp = group.contextCache.pmCtime(int(group.timestamp)).rstrip()

        # disk metrics
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

                if inst not in self.metrics.disk_stats:
                    self.metrics.disk_stats[inst] = DiskMetrics()
                    try:
                        self.metrics.disk_stats[inst].pool_image = self.rbds.map[inst]
                    except KeyError:
                        self.rbds.refresh()
                        if inst in self.rbds.map:
                            self.metrics.disk_stats[inst].pool_image = self.rbds.map[inst]
                        else:
                            raise NameError("Unable to convert a device name to it's"
                                            " pool/image format - {}".format(inst))

                self.metrics.disk_stats[inst].read = (c_r[inst] - p_r[inst]) / dt

                self.metrics.disk_stats[inst].write = (c_w[inst] - p_w[inst]) / dt
                self.metrics.disk_stats[inst].readkb = (c_rkb[inst] - p_rkb[inst]) / dt
                self.metrics.disk_stats[inst].writekb = (c_wkb[inst] - p_wkb[inst]) / dt

                tot_rios = (float)(c_r[inst] - p_r[inst])
                tot_wios = (float)(c_w[inst] - p_w[inst])
                tot_ios = (float)(tot_rios + tot_wios)

                self.metrics.disk_stats[inst].await = (((c_ractive[inst] - p_ractive[inst]) +
                                                       (c_wactive[inst] - p_wactive[inst]))
                                                       / tot_ios) if tot_ios else 0.0

                self.metrics.disk_stats[inst].r_await = ((c_ractive[inst] - p_ractive[inst])
                                                         / tot_rios) if tot_rios else 0.0

                self.metrics.disk_stats[inst].w_await = ((c_wactive[inst] - p_wactive[inst])
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
