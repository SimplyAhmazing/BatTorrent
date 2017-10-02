
class Peer(object):

    # ....

    async def download(self):
        reader, writer = await asyncio.open_connection(
            self.host, self.port
        )

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

        # Read and validate response
        peer_handshake = await reader.read(68)
        self.validate(peer_handshake)

        # Start exchanging messages
