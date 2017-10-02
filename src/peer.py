import asyncio
import struct

import bitstring

from util import LOG, PEER_ID, REQUEST_SIZE


class Peer(object):
    def __init__(self, torrent_session, host, port):
        self.host = host
        self.port = port
        self.torrent_session = torrent_session

        # Pieces this torrent is able to serve us
        self.have_pieces = bitstring.BitArray(
            bin='0' * self.torrent_session.number_of_pieces
        )
        self.piece_in_progress = None
        self.blocks = None

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


    def get_blocks_generator(self):
        def blocks():
            while True:
                piece = self.torrent_session.get_piece_request(self.have_pieces)
                LOG.info('[{}] Generating blocks for Piece: {}'.format(self, piece))
                for block in piece.blocks:
                    yield block
        if not self.blocks:
            self.blocks = blocks()
        return self.blocks


    async def request_a_piece(self, writer):
        blocks_generator = self.get_blocks_generator()
        block  = next(blocks_generator)
        LOG.info('[{}] Request Block: {}'.format(self, block))
        msg = struct.pack('>IbIII', 13, 6, block.piece, block.begin, block.length)
        writer.write(msg)
        await writer.drain()

    async def download(self):
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=10
            )
        except ConnectionError:
            LOG.error('Failed to connect to Peer {}'.format(self))
            return

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
            LOG.info('{} Read from peer: {}'.format(self, resp[:80]))

            buf += resp

            LOG.info('Buffer len({}) is {}'.format(len(buf), buf[:80]))

            if not buf and not resp:
                return

            while True:
                if len(buf) < 4:
                    await asyncio.sleep(0)
                    break

                msg_len = buf[0:4]
                length = struct.unpack('>I', msg_len)[0]

                if len(buf[4:]) < length:
                    break

                if length == 0:
                    LOG.info('got keep alive..')
                    buf = buf[4:]

                if len(buf) < 5:
                    break

                msg_id = buf[4] # 5th byte is the ID

                if msg_id == 0:
                    buf = buf[5:]
                    LOG.info('got CHOKE')

                elif msg_id == 1:
                    buf = buf[5:]
                    LOG.info('got UNCHOKE')

                elif msg_id == 5:
                    bitfield = buf[5: 5 + length - 1]
                    self.have_pieces = bitstring.BitArray(bitfield)
                    LOG.info('got bitfield {}'.format(bitfield))
                    buf = buf[5+length-1:]
                    await self.send_interested(writer)

                elif msg_id == 7:
                    piece_index = buf[5]
                    piece_begin = buf[6]
                    block = buf[13: 13 + length]
                    buf = buf[13 + length:]
                    LOG.info('Buffer is reduced to {}'.format(buf))
                    LOG.info('Got piece idx {} begin {}'.format(piece_index, piece_begin))
                    LOG.info('Block has len {}'.format(len(block)))
                    # LOG.info('Got this piece: {}'.format(block))

                    # TODO: delegate to torrent session
                    # with open(self.torrent_session.torrent.info[b'info'][b'name'].decode(), 'wb') as f:
                    #     f.write(block)
                    # continue
                else:
                    LOG.info('unknown ID {}'.format(msg_id))

                await self.request_a_piece(writer)

    def __repr__(self):
        return '[Peer {}:{}]'.format(self.host, self.port)
