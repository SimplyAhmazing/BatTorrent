import ipaddress
import socket
import struct
from urllib import parse as urlparse

import aiohttp
import bencoder
# import yarl

from torrent import Torrent
from util import LOG, PEER_ID


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
            resp = await session.get(self.tracker_url, params=self._get_request_params())
            resp_data = await resp.read()
            LOG.info('Tracker response: {}'.format(resp))
            peers = None
            try:
                peers = bencoder.decode(resp_data)
            except AssertionError:
                LOG.error('Failed to decode Tracker response: {}'.format(resp_data))
                LOG.error('Tracker request URL: {}'.format(str(resp.url).split('&')))
                raise RuntimeError('Failed to get Peers from Tracker')
            return peers

    def _get_request_params(self):
        return {
            'info_hash': self.torrent.info_hash,
            'peer_id': PEER_ID,
            'compact': 1,
            'no_peer_id': 0,
            'event': 'started',
            'port': 59696,
            'uploaded': 0,
            'downloaded': 0,
            'left': self.torrent.size
        }

    def parse_peers(self, peers : bytes):
        self_addr = socket.gethostbyname(socket.gethostname())
        self_addr = '192.168.99.1'
        LOG.info('Self addr is: {}'.format(self_addr))
        def handle_bytes(peers_data):
            peers = []
            for i in range(0, len(peers_data), 6):
                addr_bytes, port_bytes = (
                    peers_data[i:i + 4], peers_data[i + 4:i + 6]
                )
                ip_addr = str(ipaddress.IPv4Address(addr_bytes))
                if ip_addr == self_addr:
                    print('skipping', ip_addr)
                    continue
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