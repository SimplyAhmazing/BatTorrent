import copy
import hashlib
from pprint import pformat

import bencoder


class Torrent(object):
    def __init__(self, path : str):
        self.path = path
        self.info = self.read_torrent_file(path)

    def __getitem__(self, item):
        return self.info[item]

    @property
    def announce_url(self) -> str:
        return self.info[b'announce'].decode('utf-8')

    @property
    def info_hash(self):
        return hashlib.sha1(
            bencoder.encode(self.info[b'info'])
        ).digest()

    @property
    def size(self):
        info = self.info[b'info']
        if b'length' in info:
            return int(info[b'length'])
        else:
            return sum([int(f[b'length']) for f in info[b'files']])

    def read_torrent_file(self, path : str) -> dict:
        with open(path, 'rb') as f:
            return bencoder.decode(f.read())

    def is_download_complete(self):
        return False

    def __str__(self):
        # info = copy.deepcopy(self.info)
        # del info[b'info'][b'pieces']
        return pformat(self.info)