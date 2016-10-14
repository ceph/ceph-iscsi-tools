#!/usr/bin/env python
__author__ = 'paul'

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

    # device will be of the form - pool/image_name
    for dev in config.devices:

        summary = DiskSummary()
        summary.disk_size = config.devices[dev]['size']
        summary.rbd_name = config.devices[dev]['rbd_name']
        summary.io_source = ''

        for collector in pcp_threads:

            if dev in collector.metrics.disk_stats:
                summary.reads.append(collector.metrics.disk_stats[dev].read)
                summary.writes.append(collector.metrics.disk_stats[dev].write)
                summary.readkb.append(collector.metrics.disk_stats[dev].readkb)
                summary.writekb.append(collector.metrics.disk_stats[dev].writekb)
                summary.await.append(collector.metrics.disk_stats[dev].await)
                summary.r_await.append(collector.metrics.disk_stats[dev].r_await)
                summary.w_await.append(collector.metrics.disk_stats[dev].w_await)

                combined_io = collector.metrics.disk_stats[dev].read + collector.metrics.disk_stats[dev].write
                if combined_io > 0:
                    if collector.hostname == this_host:
                        summary.io_source = 'L'
                    else:
                        summary.io_source = 'R'

            # some metrics we only gather during the first cycle through the collector
            # threads
            if first_pass:
                gw_stats.cpu_busy.append(collector.metrics.cpu_busy_pct)
                gw_stats.net_in.append(collector.metrics.nic_bytes['in'])
                gw_stats.net_out.append(collector.metrics.nic_bytes['out'])

        first_pass = False

        summary.tot_reads = sum(summary.reads) if len(summary.reads) > 0 else 0
        summary.tot_writes = sum(summary.writes) if len(summary.writes) > 0 else 0
        summary.tot_readkb = sum(summary.readkb) if len(summary.readkb) > 0 else 0
        summary.tot_writekb = sum(summary.writekb) if len(summary.writekb) > 0 else 0
        summary.max_await = max(summary.await) if len(summary.await) > 0 else 0
        summary.max_r_await = max(summary.r_await) if len(summary.r_await) > 0 else 0
        summary.max_w_await = max(summary.w_await) if len(summary.w_await) > 0 else 0

        dev_stats[dev] = summary
        gw_stats.total_capacity += int(summary.disk_size)
        gw_stats.total_iops += int(summary.tot_reads + summary.tot_writes)

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
