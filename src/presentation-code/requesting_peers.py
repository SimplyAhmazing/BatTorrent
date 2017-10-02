torrent = get_torrent_file()

tracker_url = str(torrent[b'announce'])
info_hash = hashlib.sha1(
    bencoder.encode(torrent[b'info'])
).digest()
PEER_ID = 'SimplyAhmazingPython'

async def request_peers(self):
    params = {
        'info_hash': info_hash,
        'peer_id': PEER_ID,
        'compact': 1,
        'no_peer_id': 0,
        'event': 'started',
        'port': 59696,
        'uploaded': 0,
        'downloaded': 0,
        'left': 0
    }

    async with aiohttp.ClientSession() as session:
        resp = await session.get(tracker_url, params=params)
        resp_data = await resp.read()
        peers = bencoder.decode(resp_data)
        return peers
