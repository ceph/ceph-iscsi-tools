#!/usr/bin/env python
__author__ = 'Paul Cuzner'

from time import sleep

from gwtop.config.generic import DiskSummary, HostSummary
from socket import gethostname


def summarize(config, pcp_threads):
    """
    Aggregate the data collected across each of the threads for a consolidated view
    of performance across all iscsi gateways
    :param config:
    :param pcp_threads: list of PCPCollector instances
    :return: a HostSummary object containing metrics + a dict of device metrics
    """

    dev_stats = {}
    gw_stats = HostSummary()
    first_pass = True

    # Attempt to sync all the threads by timestamp, before summarising
    in_sync = False
    msg_issued = False

    while not in_sync:
        timestamps = set()        
        for collector in pcp_threads:
            timestamps.add(collector.metrics.timestamp)
        if len(timestamps) != 1:
            # not in sync at the moment
            sleep(0.1)
            if not msg_issued:
                collector.logger.debug("\nWaiting for collectors to synchronise")
                msg_issued = True
        else:
            in_sync = True

    this_host = gethostname().split('.')[0]

    # device will be of the form - <pool>.<image_name>
    for dev in config.devices:

        summary = DiskSummary()
        summary.disk_size = config.devices[dev]['size']
        summary.rbd_name = config.devices[dev]['rbd_name']
        summary.io_source = ''

        # process each collector thread's data for this device
        for collector in pcp_threads:

            if dev in collector.metrics.disk_stats:

                disk = collector.metrics.disk_stats[dev]

                for attr in collector.disk_attr.keys():

                    collector_obs = getattr(disk, attr)
                    current = getattr(summary, attr)
                    current.append(collector_obs)
                    setattr(summary, attr, current)

                if disk.iops > 0:
                    if collector.hostname == this_host:
                        # I/O is serviced (T)his gateway
                        summary.io_source = 'T'
                    else:
                        # I/O is serviced by (O)ther gateway
                        summary.io_source = 'O'

            # some metrics we only gather during the first cycle through the
            # collector threads
            if first_pass:
                gw_stats.cpu_busy.append(collector.metrics.cpu_busy_pct)
                gw_stats.net_in.append(collector.metrics.nic_bytes['in'])
                gw_stats.net_out.append(collector.metrics.nic_bytes['out'])

        first_pass = False

        # roll up the summary data relevant to the specific collectors
        # disk attributes
        for attr_name in collector.disk_attr.keys():
            attr_defn = collector.disk_attr[attr_name]
            if attr_defn['sum_method'] == 'sum':
                field_name = 'tot_{}'.format(attr_name)
                setattr(summary, field_name, sum(getattr(summary, attr_name)))
            elif attr_defn['sum_method'] == 'max':
                field_name = 'max_{}'.format(attr_name)
                current_value = getattr(summary, attr_name)
                if len(current_value) > 0:
                    setattr(summary, field_name, max(current_value))
                else:
                    setattr(summary, field_name, 0)

        summary.collector = collector.collector

        dev_stats[dev] = summary
        gw_stats.total_capacity += int(summary.disk_size)
        gw_stats.total_iops += int(summary.tot_iops)

    gw_stats.total_net_in = sum(gw_stats.net_in)
    gw_stats.total_net_out = sum(gw_stats.net_out)
    gw_stats.min_cpu = min(gw_stats.cpu_busy)
    gw_stats.max_cpu = max(gw_stats.cpu_busy)



    dt_parts = str(list(timestamps)[0]).split()
    if dt_parts[0] == 'None':
        gw_stats.timestamp = 'NO DATA'
    else:
        gw_stats.timestamp = dt_parts[3]

    return gw_stats, dev_stats
