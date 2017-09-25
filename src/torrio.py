import asyncio
import logging
import math
import struct
import sys
from pprint import pformat

from torrent import Torrent
from tracker import Tracker
from util import LOG, PEER_ID, REQUEST_SIZE

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)7s: %(message)s',
    stream=sys.stderr,
)


# PEER_ID = 'SimplyAhmazingPython'


class Piece(object):
    def __init__(self, index, blocks, _hash):
        self.index = index
        self.blocks = blocks
        self.hash = _hash

    def __repr__(self):
        return '<Piece: {} Blocks: {}>'.format(self.index, len(self.blocks))


class Block(object):
    def __init__(self, piece, begin, length):
        self.piece = piece
        self.begin = begin
        self.length = length


class DownloadSession(object):
    def __init__(self, torrent : Torrent):
        self.torrent = torrent
        self.piece_size = self.torrent[b'info'][b'piece length']
        self.number_of_pieces = math.ceil(self.torrent[b'info'][b'length'] / self.piece_size)
        self.pieces = self.get_pieces()
        self.request_pieces = []
        self.received_pieces = []

    def get_pieces(self):
        pieces = []
        for piece_idx in range(self.number_of_pieces):
            blocks = []
            piece_begin = self.piece_size * piece_idx
            num_blocks = math.ceil(self.piece_size / REQUEST_SIZE)
            for block_idx in range(num_blocks):
                is_last_block = (num_blocks - 1) == block_idx
                block_length = (
                    (self.piece_size % REQUEST_SIZE)
                    if is_last_block
                    else REQUEST_SIZE
                )
                blocks.append(
                    Block(block_idx, piece_begin + block_length * block_idx, block_length)
                )
            pieces.append(Piece(piece_idx, blocks, None))
        return pieces

    def __repr__(self):
        data = {
            'number of pieces': self.number_of_pieces,
            'piece size': self.piece_size,
            'pieces': self.pieces[:5]
        }
        return pformat(data)


class Peer(object):
    def __init__(self, torrent_session, host, port):
        self.host = host
        self.port = port
        self.torrent_session = torrent_session
        # TODO: track pieces a peer has

    def handshake(self):
        return struct.pack(
            '>B19s8x20s20s',
            19,
            b'BitTorrent protocol',
            self.torrent_session.torrent.info_hash,
            PEER_ID.encode()
        )

    async def send_interested(self, writer):
        # TODO: refactor into messages util
        msg = struct.pack('>Ib', 1, 2)
        writer.write(msg)
        await writer.drain()

    async def request_a_piece(self, writer):
        # TODO: request a piece dynamically based on torrent (use torrent session)
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

        # TODO: use async iterator
        buf = b''
        while True:
            resp = await reader.read(REQUEST_SIZE)  # Suspends here if there's nothing to be read
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

                    # TODO: delegate to torrent session
                    # with open(self.torrent_session.torrent.info[b'info'][b'name'].decode(), 'wb') as f:
                    #     f.write(block)
                    continue
                else:
                    LOG.info('unknown ID {}'.format(msg_id))
                    break

    def __repr__(self):
        return '[Peer {}:{}]'.format(self.host, self.port)


async def download(torrent_file : str, download_location : str, loop=None):
    # Parse torrent file
    torrent = Torrent(torrent_file)
    session = DownloadSession(torrent)

    print(torrent)

    # Instantiate tracker object
    tracker = Tracker(torrent)

    peers_info = await tracker.get_peers()

    # while not torrent.is_download_complete():
    seen_peers = set()
    peers = [
        Peer(session, host, port)
        for host, port in peers_info
    ]
    seen_peers.update([str(p) for p in peers])

    LOG.info('[Peers] {}'.format(seen_peers))

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
