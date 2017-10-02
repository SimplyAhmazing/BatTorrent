# example.py

import asyncio

async def download(torrent_file):
    torrent = read_torrent()
    peer_addresses = await get_peers(torrent)
    peers = [Peer(addr) for addr in peer_addresses]

    await asyncio.gather(
        *[peer.start() for peer in peers]
    )


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    
    loop.run_until_complete(download(sys.argv[1])
    
    loop.close()
