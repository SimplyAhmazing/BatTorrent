import sys
from pprint import pformat, pprint as pp

import asyncio
import aiohttp
import bencoder
import hashlib
import ipaddress
import random
import string
from urllib import parse as urlparse
import struct

import yarl


class Torrent(object):
    def __init__(self, path : str):
        self.path = path
        self.info = self.read_torrent_file(path)

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
        return pformat(self.info)


class Tracker(object):
    def __init__(self, torrent : Torrent):
        self.torrent = torrent
        self.tracker_url = torrent.announce_url
        self.peers = []

    async def get_peers(self):
        peers_resp = await self.request_peers()
        peers = self.parse_peers(peers_resp[b'peers'])
        return peers

    async def request_peers(self):
        async with aiohttp.ClientSession() as session:
            resp = await session.get(self._get_tracker_url())
            resp = await resp.read()
            return bencoder.decode(resp)

    def get_peer_id(self):
        return hashlib.sha1(
            ('SA' + ''.join(
                [random.choice(string.digits) for i in range(18)])
             ).encode('utf-8')
        ).digest()

    def _get_tracker_url(self):
        return yarl.URL(self.tracker_url).with_query(self._get_request_params())

    def _get_request_params(self):
        return {
            'info_hash': urlparse.quote(self.torrent.info_hash),
            'peer_id': urlparse.quote(self.get_peer_id()),
            'compact': 1,
            'no_peer_id': 0,
            'event': 'started',
            'port': 59696,
            'uploaded': 0,
            'downloaded': 0,
            'left': self.torrent.size
        }

    def parse_peers(self, peers : bytes):
        def handle_bytes(peers_data):
            peers = []
            for i in range(0, len(peers_data), 6):
                addr_bytes, port_bytes = peers_data[i:i + 4], peers_data[i + 4:i + 6]
                ip_addr = str(ipaddress.IPv4Address(addr_bytes))
                port_bytes = struct.unpack('>H', port_bytes)[0]
                peers.append((ip_addr, port_bytes))
            return peers

        def handle_dict(peers):
            raise NotImplementedError

        handlers = {
            bytes: handle_bytes,
            dict: handle_dict
        }
        return handlers[type(peers)](peers)


class Peer(object):
    def __init__(self, connection_info):
        self.connection_addr = '{}.{}'.format(*connection_info)

    async def download():
        while True:
            print('downloading from ..')


async def download(torrent_file : str, download_location : str):
    # Parse torrent file
    torrent = Torrent(torrent_file)
    print(torrent)

    # Instantiate tracker object
    tracker = Tracker(torrent)

    peers = await tracker.get_peers()

    while not torrent.is_download_complete():
        for peer in peers:
            print(peer)
            await asyncio.sleep(1)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(download(sys.argv[1], '.'))
