
class Peer(object):
    def __init__(self, host, port, file_queue):
        self.host = host
        self.port = port
        self.file_queue = file_queue

        # Denotes if peer is choking us
        self.peer_choking = True

        # Denotes if we've informed our peer we're interested
        self.am_interested = False

    async def download(self):
        reader, writer = await asyncio.open_connection(self.host, self.port)

        handshake = b''.join([
            chr(19).encode(),
            b'BitTorrent protocol',
            (chr(0) * 8).encode(),
            info_hash,
            PEER_ID.encode()
        ])

        # Send Handshake
        writer.write(handshake)
        await writer.drain()
