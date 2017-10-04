import os

import bitstring
import pytest

from torrent import Torrent
from torrio import DownloadSession

@pytest.fixture
def torrent():
    return Torrent(
        os.path.join(
            os.path.dirname(__file__),
            'data/Zulip-1.3.0-beta-mac.zip.torrent')
    )

def get_piece_block_tuples(pieces) -> list:
    return [
        (block.piece, block.begin)
        for piece in pieces
        for block in piece.blocks
    ]


def test_get_pieces(torrent):
    session = DownloadSession(torrent)
    pieces = session.get_pieces()

    p = [
        (piece.index, block.begin)
        for piece in pieces
        for block in piece.blocks
    ]

    # Ensure all piece/block combinations are unique
    assert len(set(p)) == len(p)

    # Ensure blocks are aware of their pieces
    block_vals = [
        (block.piece, block.begin)
        for piece in pieces
        for block in piece.blocks
    ]
    assert block_vals == p


def test_get_piece_request(torrent):
    session = DownloadSession(torrent)
    pieces = session.get_pieces()
    have_pieces = bitstring.BitArray(bin='1'*len(pieces))

    piece_block_combos = get_piece_block_tuples(pieces)

    req = session.get_piece_request(have_pieces)

    print(req)
