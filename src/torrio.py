import sys
from pprint import pformat, pprint as pp

import asyncio
import aiohttp
import bencoder
import hashlib
import ipaddress
import logging
import random
import socket
import string
import struct
from urllib import parse as urlparse

import yarl

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)7s: %(message)s',
    stream=sys.stderr,
)
LOG = logging.getLogger('')

PEER_ID = 'SimplyAhmazingPython'
PEER_ID_HASH = hashlib.sha1(PEER_ID.encode()).digest()
CHUNK_SIZE = 10 * 1024


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
            print('Response is', resp)
            return bencoder.decode(resp)

    def _get_tracker_url(self):
        return yarl.URL(self.tracker_url).with_query(self._get_request_params())

    def _get_request_params(self):
        return {
            'info_hash': urlparse.quote(self.torrent.info_hash),
            'peer_id': urlparse.quote(PEER_ID),
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


class Peer(object):
    def __init__(self, torrent, host, port):
        self.host = host
        self.port = port
        self.torrent = torrent

    def handshake(self):
        # return b''.join([
        #     chr(19).encode(),
        #     b'BitTorrent protocol',
        #     b'\x00\x00\x00\x00\x00\x10\x00\x05',
        #     self.torrent.info_hash,
        #     PEER_ID.encode()
        # ])
        format = '>B19s8x20s20s'
        return struct.pack(
            format,
            19,
            b'BitTorrent protocol',
            self.torrent.info_hash,
            PEER_ID.encode()
        )

    async def send_interested(self, writer):
        msg = struct.pack('>Ib', 1, 2)
        writer.write(msg)
        await writer.drain()

    async def request_a_piece(self, writer):
        msg = struct.pack('>IbIII', 13, 6, 0, 0, 35)
        writer.write(msg)
        await writer.drain()

    async def download(self):
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port),
            timeout=3
        )

        LOG.info('{} Sending handshake'.format(self))
        writer.write(self.handshake())
        await writer.drain()

        # TODO: Validate handshake
        handshake = await reader.read(68)  # Suspends here if there's nothing to be read

        await self.send_interested(writer)

        buf = b''
        while True:
            resp = await reader.read(CHUNK_SIZE)  # Suspends here if there's nothing to be read
            LOG.info('{} Read from peer: {}'.format(self, resp))

            buf += resp

            LOG.info('Buffer len({}) is {}'.format(len(buf), buf))

            if not buf and not resp:
                return

            while True:
                if len(buf) < 4:
                    await asyncio.sleep(0.01)
                    break

                msg_len = buf[0:4]
                length = struct.unpack('>I', msg_len)[0]

                if len(buf[4:]) < length:
                    break

                if length == 0:
                    LOG.info('got keep alive..')
                    buf = buf[4:]
                    continue

                msg_id = buf[4] # 5th byte is the ID

                if msg_id == 0:
                    buf = buf[5:]
                    LOG.info('got CHOKE')
                    continue
                elif msg_id == 1:
                    buf = buf[5:]
                    LOG.info('got UNCHOKE')
                    await self.request_a_piece(writer)
                    continue
                elif msg_id == 5:
                    bitfield = buf[5: 5 + length - 1]
                    LOG.info('got bitfield {}'.format(bitfield))
                    buf = buf[5+length-1:]

                    await self.send_interested(writer)
                    continue

                elif msg_id == 7:
                    piece_index = buf[5]
                    piece_begin = buf[6]
                    block = buf[13: 13 + length]
                    buf = buf[13 + length:]
                    LOG.info('Buffer is reduced to {}'.format(buf))
                    LOG.info('Got piece idx {} begin {}'.format(piece_index, piece_begin))
                    LOG.info('Got this piece: {}'.format(block))

                    with open(self.torrent.info[b'info'][b'name'].decode(), 'wb') as f:
                        f.write(block)
                    continue
                else:
                    LOG.info('unknown ID {}'.format(msg_id))
                    break


    def __repr__(self):
        return '[Peer {}:{}]'.format(self.host, self.port)


async def download(torrent_file : str, download_location : str, loop=None):
    # Parse torrent file
    torrent = Torrent(torrent_file)
    print(torrent)

    # Instantiate tracker object
    tracker = Tracker(torrent)

    peers_info = await tracker.get_peers()

    # while not torrent.is_download_complete():
    seen_peers = set()
    peers = [
        Peer(torrent, host, port)
        for host, port in peers_info
    ]
    seen_peers.update([str(p) for p in peers])

    print(seen_peers)

    # async def ping():
    #     while True:
    #         await asyncio.sleep(1)
    #         print('alive..')
    #
    # asyncio.ensure_future(ping())

    await (
        asyncio.gather(*[
            peer.download()
            for peer in peers
        ])
    )


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    # loop.set_debug(True)
    # loop.slow_callback_duration = 0.001
    # warnings.simplefilter('always', ResourceWarning)

    loop.run_until_complete(download(sys.argv[1], '.', loop=loop))
