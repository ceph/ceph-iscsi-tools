#!/usr/bin/env python2

import json
import glob
import os
import sys
import time
import argparse


from ceph_daemon import admin_socket

# TO DO
# 1. The IOPS and throughput numbers have been verified, but the latency
#    calculations should really be validated by someone else!
#
#
# Known Issues
# 1. ceph reports rd_iops and wr_iops - but this values are not 100% accurate
#    tests with fio and rate limited io show that ceph reports around 5-10%
#    higher iops
# 2. Latency calculations can show variations when the rd_iops or wr_iops is 0
#    the code accomodates this variance by just return 0 latency if the
#    corresponding iops total is also 0
# 3. Accuracy of the values below 3-5 secs, needs to be confirmed


def bytes2human(in_bytes, target_unit=None):
    """
    Convert a given number of bytes into a more consumable form
    :param in_bytes: bytes to convert (int)
    :param target_unit: target representation MB, GB, TB etc
    :return: string of the converted value with a suffix e.g. 5G
    """

    suffixes = ['K', 'M', 'G', 'T', 'P']

    rounding = {'K': 0, 'M': 2, 'G': 1, 'T': 1, 'P': 2}

    size = float(in_bytes)

    if size < 0:
        raise ValueError('number must be non-negative')

    divisor = 1024

    for suffix in suffixes:
        size /= divisor
        if size < divisor or suffix == target_unit:
            char1 = suffix[0]
            precision = rounding[char1]
            size = round(size, precision)
            fmt_string = '{0:.%df}{1}' % rounding[char1]

            return fmt_string.format(size, suffix)

    raise ValueError('number too large')


class RBDStats(object):

    display_titles = ('{:<30}  r_iops   w_iops     r_lat    w_lat'
                      '   r_tput    w_tput'.format("Pool-Image Name"))

    def __init__(self, socket_path):
        self.socket_path = socket_path
        self.stats = {}
        self.last_stats = {}
        self.key = ''

        self.pool_name = ''
        self.rbd_image = ''

        self.rd_iops = 0
        self.wr_iops = 0
        self.rd_lat = 0
        self.wr_lat = 0
        self.rd_bytes = 0
        self.wr_bytes = 0

    @staticmethod
    def get_librbd_key(json_data):

        for key in json_data.keys():
            if key.startswith('librbd'):
                return key
        return ''

    def _get_stats(self):
        try:
            response = admin_socket(self.socket_path,
                                    ["perf", "dump"],
                                    format='json')
        except RuntimeError:
            # socket error
            pass

        r_json = json.loads(response)
        librbd_key = self.get_librbd_key(r_json)
        if not librbd_key:
            return

        self.key = '-'.join(librbd_key.split('-')[2:])

        self.stats = r_json.get(librbd_key)

    @staticmethod
    def _calc_latency(now, last):

        _sum = now['sum'] - last['sum']
        _avg = now['avgcount'] - last['avgcount']
        if _sum == 0 or _avg == 0:
            return 0
        else:
            return (_sum / float(_avg))*1000    # show as ms

    def _calc(self):

        last = self.last_stats
        now = self.stats

        if last:
            # this is not 100% accurate. tests with fio rate limiting show
            # that ceph is reporting as much as 10% more iops as sent
            # by the client
            self.rd_iops = (now['rd'] - last['rd']) / opts.interval
            self.wr_iops = (now['wr'] - last['wr']) / opts.interval

            if self.rd_iops > 0:
                self.rd_lat = self._calc_latency(now['rd_latency'],
                                                 last['rd_latency'])
            else:
                self.rd_lat = 0

            if self.wr_iops > 0:
                self.wr_lat = self._calc_latency(now['wr_latency'],
                                                 last['wr_latency'])
            else:
                self.wr_lat = 0

            self.rd_bytes = (now['rd_bytes'] - last['rd_bytes']) / opts.interval
            self.wr_bytes = (now['wr_bytes'] - last['wr_bytes']) / opts.interval

        self.last_stats = self.stats

    def update(self):

        self._get_stats()

        self._calc()

    def __repr__(self):
        s = ("{:<30} {:>7}  {:>7}   {:7.2f}  {:7.2f}  {:>7}"
             "   {:>7}".format(self.key,
                                self.rd_iops,
                                self.wr_iops,
                                self.rd_lat,
                                self.wr_lat,
                                bytes2human(self.rd_bytes),
                                bytes2human(self.wr_bytes)))
        return s


def get_sockets(socket_dir='/var/run/ceph'):
    return glob.glob(os.path.join(socket_dir, 'client.admin.*.asok'))


def main():

    image = {}
    sockets = get_sockets()

    # initialise the local stats objects, removing invalid sockets
    for adm_sock in sockets:
        img_stats = RBDStats(adm_sock)
        img_stats.update()
        if not img_stats.stats:
            print("No librbd section found in socket {}..."
                  "dropping".format(adm_sock))
            del img_stats
            continue

        image[img_stats.key] = img_stats

    if opts.rbd_image and opts.rbd_image not in image:
        print("{} is not present in any ceph admin sockets."
              " Unable to continue")
        sys.exit(12)

    print("waiting...")
    time.sleep(opts.interval)

    print(RBDStats.display_titles)
    l_cnt = 0
    pg_limit = 20

    try:
        while True:

            for rbd_key in sorted(image):
                if not opts.rbd_image or opts.rbd_image == rbd_key:

                    img_stats = image[rbd_key]
                    img_stats.update()
                    print(img_stats)
                    l_cnt += 1
                    if l_cnt > pg_limit:
                        l_cnt = 0
                        print(RBDStats.display_titles)

            time.sleep(opts.interval)

    except KeyboardInterrupt:
        pass


def get_options():
    parser = argparse.ArgumentParser(prog='rbdperf',
                                     description='Show librbd performance '
                                                 'metrics')

    parser.add_argument('-i', '--interval', type=int,
                        default=5,
                        help='refresh interval (default = 1)')
    parser.add_argument('-r', '--rbd-image', type=str,
                        default='',
                        help='Show specific image - pool-image_name format')

    return parser.parse_args()

if __name__ == '__main__':

    opts = get_options()

    main()

