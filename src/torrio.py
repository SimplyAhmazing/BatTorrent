import asyncio
import logging
import math
import sys
from pprint import pformat

from torrent import Torrent
from tracker import Tracker
from util import LOG, REQUEST_SIZE

from peer import Peer

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)7s: %(message)s',
    stream=sys.stderr,
)


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

    def __repr__(self):
        return '[Block ({}, {}, {})]'.format(self.piece, self.begin, self.length)


class DownloadSession(object):
    def __init__(self, torrent : Torrent):
        self.torrent = torrent
        self.piece_size = self.torrent[b'info'][b'piece length']
        self.number_of_pieces = math.ceil(self.torrent[b'info'][b'length'] / self.piece_size)
        self.pieces = self.get_pieces()
        self.pieces_in_progress = []
        self.received_pieces = []

    def get_pieces(self):
        pieces = []
        for piece_idx in range(self.number_of_pieces):
            blocks = []
            num_blocks = math.ceil(self.piece_size / REQUEST_SIZE)
            for block_idx in range(num_blocks):
                is_last_block = (num_blocks - 1) == block_idx
                block_length = (
                    (self.piece_size % REQUEST_SIZE) or REQUEST_SIZE
                    if is_last_block
                    else REQUEST_SIZE
                )
                blocks.append(
                    Block(block_idx, block_length * block_idx, block_length)
                )
            pieces.append(Piece(piece_idx, blocks, None))
        return pieces

    def get_piece_request(self, have_pieces):
        for piece in self.pieces:
            # Don't create request out of pieces we already have
            if piece in self.received_pieces or piece in self.pieces_in_progress:
                continue
            if have_pieces[piece.index]:
                self.pieces_in_progress.append(piece)
                return piece
        raise Exception('Not eligible for valid pieces')

    def on_block_downloaded(self):
        pass

    def __repr__(self):
        data = {
            'number of pieces': self.number_of_pieces,
            'piece size': self.piece_size,
            'pieces': self.pieces[:5]
        }
        return pformat(data)


async def download(torrent_file : str, download_location : str, loop=None):
    # Parse torrent file
    torrent = Torrent(torrent_file)
    session = DownloadSession(torrent)

    LOG.info('Torrent: {}'.format(torrent))

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
    # For Debugging
    # loop.set_debug(True)
    # loop.slow_callback_duration = 0.001
    # warnings.simplefilter('always', ResourceWarning)

    loop.run_until_complete(download(sys.argv[1], '.', loop=loop))
