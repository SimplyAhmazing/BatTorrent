import asyncio
import bitstring
import hashlib
import logging
import math
import sys
from typing import Dict, List
from pprint import pformat

from file_saver import FileSaver
from peer import Peer
from torrent import Torrent
from tracker import Tracker
from util import LOG, REQUEST_SIZE

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)7s: %(message)s',
    stream=sys.stderr,
)


class Piece(object):
    def __init__(self, index : int, blocks : list):
        self.index : int = index
        self.blocks : list = blocks
        self.downloaded_blocks : bitstring.BitArray = \
            bitstring.BitArray(bin='0'*len(blocks))

    def flush(self):
        [block.flush() for block in self.blocks]

    def is_complete(self) -> bool:
        """
        Return True if all the Blocks in this piece exist
        """
        return all(self.downloaded_blocks)

    def save_block(self, begin : int, data : bytes):
        """
        Writes block 'data' into block object
        """
        for block_idx, block in enumerate(self.blocks):
            if block.begin == begin:
                block.data = data
                self.downloaded_blocks[block_idx] = True

    @property
    def data(self) -> bytes:
        """
        Returns Piece data
        """
        return b''.join([block.data for block in self.blocks])

    @property
    def hash(self):
        return hashlib.sha1(self.data)

    def __repr__(self):
        return '<Piece: {} Blocks: {}>'.format(
            self.index,
            len(self.blocks)
        )


class Block(object):
    def __init__(self, piece, begin, length):
        self.piece = piece
        self.begin = begin
        self.length = length
        self.data = None

    def flush(self):
        self.data = None

    def __repr__(self):
        return '[Block ({}, {}, {})]'.format(
            self.piece,
            self.begin,
            self.length
        )


# TODO: check if file isn't already downloaded
class DownloadSession(object):
    def __init__(
            self, torrent : Torrent, received_blocks : asyncio.Queue = None):
        self.torrent : Torrent = torrent
        self.piece_size : int = self.torrent[b'info'][b'piece length']
        self.number_of_pieces : int = math.ceil(
            self.torrent[b'info'][b'length'] / self.piece_size)
        self.pieces : list = self.get_pieces()
        self.pieces_in_progress : Dict[int, Piece] = {}
        self.received_pieces : Dict[int, Piece]= {}
        self.received_blocks : asyncio.Queue = received_blocks

    def on_block_received(self, piece_idx, begin, data):
        """
        TODO: implement writing off downloaded piece
        1. Removes piece from self.pieces
        2. Verifies piece hash
        3. Sets self.have_pieces[piece.index] = True if hash is valid
        4. Else re-inserts piece into self.pieces

        :return:  None
        """

        piece = self.pieces[piece_idx]
        piece.save_block(begin, data)

        # Verify all blocks in the Piece have been downloaded
        if not piece.is_complete():
            return

        piece_data = piece.data

        res_hash = hashlib.sha1(piece_data).digest()
        exp_hash = self.torrent.get_piece_hash(piece.index)

        if res_hash != exp_hash:
            # TODO: re-enqueue request
            LOG.info('Hash check failed for Piece {}'.format(piece.index))
            piece.flush()
            return
        else:
            import pdb; pdb.set_trace()
            LOG.info('Piece {} hash is valid'.format(piece.index))

        self.received_blocks.put_nowait((piece.index * self.piece_size, piece_data))

    def get_pieces(self) -> list:
        """
        Generates list of pieces and their blocks
        """

        # TODO: fix bug where blocks are incorrectly generated for
        # files less than the REQUEST_SIZE

        pieces = []
        blocks_per_piece = math.ceil(self.piece_size / REQUEST_SIZE)
        for piece_idx in range(self.number_of_pieces):
            blocks = []
            for block_idx in range(blocks_per_piece):
                is_last_block = (blocks_per_piece - 1) == block_idx
                block_length = (
                    (self.piece_size % REQUEST_SIZE) or REQUEST_SIZE
                    if is_last_block
                    else REQUEST_SIZE
                )
                blocks.append(
                    Block(
                        piece_idx,
                        block_length * block_idx,
                        block_length
                    )
                )
            pieces.append(Piece(piece_idx, blocks))
        return pieces

    def get_piece_request(self, have_pieces):
        """
        Determines next piece for downloading. Expects BitArray
        of pieces a peer can request
        """
        for piece in self.pieces:
            # Don't create request out of pieces we already have
            is_piece_downloaded = piece.index in self.received_pieces
            is_piece_in_progress = piece.index in self.pieces_in_progress

            # Skip pieces we already have
            if is_piece_downloaded or is_piece_in_progress:
                continue

            if have_pieces[piece.index]:
                self.pieces_in_progress[piece.index] = piece
                return piece
        raise Exception('Not eligible for valid pieces')

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
    LOG.info('Torrent: {}'.format(torrent))

    torrent_writer = FileSaver(download_location, torrent)
    session = DownloadSession(torrent, torrent_writer.get_received_blocks_queue())

    # Instantiate tracker object
    tracker = Tracker(torrent)

    peers_info = await tracker.get_peers()

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
    loop.close()
