#!/usr/bin/env pmpython

import threading

from pcp import pmapi, pmcc
from gwtop.config.generic import DiskMetrics, GatewayMetrics
from gwtop.utils.data import bytes2human

import re
import os
import glob
from rtslib_fb.utils import fread

# group metrics
DISK_METRICS = {"dm": ['disk.dm.read',
                       'disk.dm.read_bytes',
                       'disk.dm.write',
                       'disk.dm.write_bytes',
                       'disk.dm.read_rawactive',
                       'disk.dm.write_rawactive'
                       ],
                "lio": ['lio.lun.iops',
                        'lio.lun.read_mb',
                        'lio.lun.write_mb'
                        ]
                 }


NETWORK_METRICS = ['network.interface.in.bytes',
                   'network.interface.out.bytes']

# single metric
CPU_METRICS = ['kernel.all.cpu.idle',
               'kernel.all.cpu.sys',
               'kernel.all.cpu.user',
               'kernel.all.cpu.intr',
               'hinv.ncpu']

class CollectorError(Exception):
    pass


class RBDMap(object):

    def __init__(self):
        self.map = {}
        self.refresh()

    def refresh(self):
        self._get_map()

        if not self.map:
            raise CollectorError("RBDMAP: Unable to create the "
                                 "dm -> rbd_name lookup table")

    def _get_map(self):
        """
        Convert dm devices into their pool/rbd_image name. All gateway nodes
        should see the same rbds, and each rbd when mapped through device
        mapper will have the same name, so this gives us a common reference
        point.
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

class PCPbase(pmcc.MetricGroupPrinter):

    NIC_BLACKLIST = ['lo', 'docker0']
    HDRcount = 0

    def __init__(self, metrics):
        pmcc.MetricGroupPrinter.__init__(self)
        self.metrics = metrics

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

    def get_cpu_and_network(self, group, dt):

        timestamp = group.contextCache.pmCtime(int(group.timestamp)).rstrip()
        self.metrics.timestamp = timestamp

        nic_list = self.instlist(group, 'network.interface.in.bytes')

        # NIC metrics
        c_nic_in_b = self.curVals(group, 'network.interface.in.bytes')
        p_nic_in_b = self.prevVals(group, 'network.interface.in.bytes')
        c_nic_out_b = self.curVals(group, 'network.interface.out.bytes')
        p_nic_out_b = self.prevVals(group, 'network.interface.out.bytes')

        tot_in = tot_out = 0
        for nic in nic_list:
            if nic in PCPDMextract.NIC_BLACKLIST:
                continue
            tot_in += (c_nic_in_b[nic] - p_nic_in_b[nic]) / dt
            tot_out += (c_nic_out_b[nic] - p_nic_out_b[nic]) / dt

        self.metrics.nic_bytes = {'in': tot_in, 'out': tot_out}

        # CPU metrics
        #
        # get the number of cpu's on this host to calculate cpu utilisation
        num_cpus = self.curVals(group, 'hinv.ncpu')['']
        cpu_multiplier = self.metrics.interval * 1000

        c_k_sys = float(self.curVals(group, 'kernel.all.cpu.sys')[''])
        p_k_sys = float(self.prevVals(group, 'kernel.all.cpu.sys')[''])
        c_k_user = float(self.curVals(group, 'kernel.all.cpu.user')[''])
        p_k_user = float(self.prevVals(group, 'kernel.all.cpu.user')[''])
        c_k_intr = float(self.curVals(group, 'kernel.all.cpu.intr')[''])
        p_k_intr = float(self.prevVals(group, 'kernel.all.cpu.intr')[''])

        used = []
        used.append(
            100 * (float(c_k_sys - p_k_sys) / (num_cpus * cpu_multiplier)))
        used.append(
            100 * (float(c_k_user - p_k_user) / (num_cpus * cpu_multiplier)))
        used.append(
            100 * (float(c_k_intr - p_k_intr) / (num_cpus * cpu_multiplier)))

        self.metrics.cpu_busy_pct = int(round(sum(used)))


class PCPLIOextract(PCPbase):

    disk_attr = {
                'iops': {'sum_method': 'sum'},
                'read_mb': {'sum_method': 'sum'},
                'write_mb': {'sum_method': 'sum'}
                }

    def __init__(self, metrics):
        PCPbase.__init__(self, metrics)

    def report(self, manager):
        subtree = 'lio.lun'


        group = manager["gateways"]

        # just use iops to get all disk instance names
        lun_list = self.instlist(group, subtree + '.iops')

        if group[subtree + '.iops'].netPrevValues is None:
            # need two fetches for the cur/prev deltas to work
            return

        dt = self.timeStampDelta(group)
        self.get_cpu_and_network(group, dt)

        # LIO metrics originally extracted from
        # /sys/kernel/config/target/iscsi/<iqn>/tpgt_<n>/lun/lun_<n>/statistics
        c_iops = self.curVals(group, subtree + '.iops')
        p_iops = self.prevVals(group, subtree + '.iops')

        c_rmb = self.curVals(group, subtree + '.read_mb')
        p_rmb = self.prevVals(group, subtree + '.read_mb')

        c_wmb = self.curVals(group, subtree + '.write_mb')
        p_wmb = self.prevVals(group, subtree + '.write_mb')

        # try:
        for lun_name in sorted(lun_list):

            if lun_name not in self.metrics.disk_stats:
                self.metrics.disk_stats[lun_name] = DiskMetrics()

            # self.metrics.disk_stats[key].dm_device = inst
            self.metrics.disk_stats[lun_name].iops = (c_iops[lun_name] -
                                                      p_iops[lun_name]) / dt

            self.metrics.disk_stats[lun_name].read_mb = (c_rmb[lun_name] -
                                                         p_rmb[lun_name]) / dt

            self.metrics.disk_stats[lun_name].write_mb = (c_wmb[lun_name] -
                                                          p_wmb[lun_name]) / dt

    @classmethod
    def headers(cls, max_rbd_name):
        return("{:<{}}    Src    Size     iops     rMB/s     wMB/s"
               "   Client".format("Pool.Image",
                                  max_rbd_name))

    @classmethod
    def print_device_data(cls, devname, max_dev_name, disk_data, client):

        return('{:<{}}    {:^3}    {:>4}    {:>5}    {:>6.2f}    '
               '{:>6.2f}   {:<20}'.format(devname, max_dev_name,
                                          disk_data.io_source,
                                          bytes2human(disk_data.disk_size),
                                          int(round(disk_data.tot_iops)),
                                          disk_data.tot_read_mb,
                                          disk_data.tot_write_mb,
                                          client))


class PCPDMextract(PCPbase):
    """
    Class based on the pcp-iostat example code that provides disk/network and
    cpu metrics for the given node (thread)
    """

    device_regex = '[0-255]-[a-f,0-9]+'

    disk_attr = {
        'iops': {'sum_method': 'sum'},
        'reads': {'sum_method': 'sum'},
        'writes': {'sum_method': 'sum'},
        'readkb': {'sum_method': 'sum'},
        'writekb': {'sum_method': 'sum'},
        'avgwait': {'sum_method': 'max'},
        'r_avgwait': {'sum_method': 'max'},
        'w_avgwait': {'sum_method': 'max'}
        }

    def __init__(self, metrics):
        PCPbase.__init__(self, metrics)
        self.rbds = RBDMap()

    @classmethod
    def headers(cls, max_rbd_name):
        return("{:<{}}  Src  Device   Size     r/s     w/s    rMB/s     wMB/s"
               "    await  r_await  w_await  Client".format("Pool.Image",
                                                            max_rbd_name))

    @classmethod
    def print_device_data(cls, devname, max_rbd_name, disk_data, client):

        return("{:<{}}  {:^3}  {:^6}   {:>4}   {:>5}   {:>5}   {:>6.2f}    "
               "{:>6.2f}   {:>6.2f}   {:>6.2f}"
               "   {:>6.2f}  {:<20}".format(devname, max_rbd_name,
                                            disk_data.io_source,
                                            disk_data.rbd_name,
                                            bytes2human(disk_data.disk_size),
                                            int(disk_data.tot_reads),
                                            int(disk_data.tot_writes),
                                            disk_data.tot_readkb / 1024,
                                            disk_data.tot_writekb / 1024,
                                            disk_data.max_avgwait,
                                            disk_data.max_r_avgwait,
                                            disk_data.max_w_avgwait,
                                            client))


    def report(self, manager):
        subtree = 'disk.dm'

        # print "DEBUG - in report function"

        group = manager["gateways"]

        # just use reads to get all disk instance names
        all_disks = self.instlist(group, subtree + '.read')

        # rbd device mapped for the gateway use the following naming convention
        # <pool_id>.<rbd uid>
        instlist = [disk_id for disk_id in all_disks
                    if re.search(PCPDMextract.device_regex, disk_id) is not None]
        # print "DEBUG - devices found %s " % instlist

        if group[subtree + '.read'].netPrevValues is None:
            # need two fetches for the cur/prev deltas to work
            return

        dt = self.timeStampDelta(group)
        self.get_cpu_and_network(group, dt)

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

        # try:
        for inst in sorted(instlist):

            try:
                # get pool/image name for the dm name from the lookup table
                key = self.rbds.map[inst]['rbd_name']
            except KeyError:
                self.rbds.refresh()
                if inst in self.rbds.map:
                    key = self.rbds.map[inst]['rbd_name']
                else:
                    raise CollectorError("PCPExtract: Unable to convert "
                                         "{} to a pool/image name".format(inst))

            if key not in self.metrics.disk_stats:
                self.metrics.disk_stats[key] = DiskMetrics()

            # self.metrics.disk_stats[key].dm_device = inst
            self.metrics.disk_stats[key].reads = (c_r[inst] - p_r[inst]) / dt

            self.metrics.disk_stats[key].writes = (c_w[inst] - p_w[inst]) / dt

            self.metrics.disk_stats[key].iops = self.metrics.disk_stats[key].reads + \
                                                self.metrics.disk_stats[key].writes

            self.metrics.disk_stats[key].readkb = (c_rkb[inst] - p_rkb[inst]) / dt
            self.metrics.disk_stats[key].writekb = (c_wkb[inst] - p_wkb[inst]) / dt

            tot_rios = (float)(c_r[inst] - p_r[inst])
            tot_wios = (float)(c_w[inst] - p_w[inst])
            tot_ios = (float)(tot_rios + tot_wios)

            self.metrics.disk_stats[key].avgawait = (((c_ractive[inst] - p_ractive[inst]) +
                                                      (c_wactive[inst] - p_wactive[inst]))
                                                     / tot_ios) if tot_ios else 0.0

            self.metrics.disk_stats[key].r_avgwait = ((c_ractive[inst] - p_ractive[inst])
                                                      / tot_rios) if tot_rios else 0.0

            self.metrics.disk_stats[key].w_avgwait = ((c_wactive[inst] - p_wactive[inst])
                                                      / tot_wios) if tot_wios else 0.0


class PCPcollector(threading.Thread):
    """
    Parent thread object which runs an instance of the pcp metric
    collector for a given host
    """

    def __init__(self, logger, sync_event, host='', interval='1',
                 pcp_type='dm'):

        threading.Thread.__init__(self)
        self.hostname = host
        self.start_me_up = sync_event
        self.logger = logger

        collector_lookup = {'dm': PCPDMextract,
                            'lio': PCPLIOextract}

        opts = IOstatOptions(host)
        self.context = None

        # The manager object builds it's options from the command line
        # parameters, so we simulate that with a list
        args_list = ['', '-h', host, '-t', str(interval)]
        try:
            self.manager = pmcc.MetricGroupManager.builder(opts, args_list)
            self.manager["gateways"] = (DISK_METRICS[pcp_type] +
                                        CPU_METRICS +
                                        NETWORK_METRICS)
            self.metrics = GatewayMetrics()
            self.metrics.cpu_busy_pct = 0
            self.metrics.cpu_idle_pct = 0
            self.metrics.interval = interval
            self.metrics.timestamp = None
            self.metrics.disk_stats = {}
            self.metrics.nic_bytes = {'in': 0, 'out': 0}

            # set up the disk attributes to collect and summarise based on the
            # provider type
            collector = collector_lookup[pcp_type]
            self.disk_attr = collector.disk_attr
            self.collector = collector

            self.manager.printer = collector(self.metrics)

            self.connected = True
        except pmapi.pmErr:
            self.connected = False

    def run(self):
        # grab the data and store in dict every second
        self.logger.debug("pcp manager thread started for "
                          "host {}".format(self.hostname))

        self.start_me_up.wait()
        self.manager.run()
