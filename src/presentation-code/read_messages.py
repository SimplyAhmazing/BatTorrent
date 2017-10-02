
class Peer(object):
    async def download(self):
    # Start exchanging messages

        buf = b''
        while True:
            resp = await reader.read(REQUEST_SIZE)  # Suspends here if there's nothing to be read
            buf += resp

            # We're done downloading...
            # if not buf and not resp:
            #     return

            while True:
                if len(buf) < 4:
                    await asyncio.sleep(0)
                    break

                msg_len = buf[0:4]
                length = struct.unpack('>I', msg_len)[0]

                # Message not yet fully recieved
                if len(buf[4:]) < length:
                    break

                if length == 0:
                    LOG.info('[Message] Keep Alive')
                    buf = buf[4:]  # Advance buffer

                if len(buf) < 5:
                    break

                msg_id = buf[4] # 5th byte is the ID

                if msg_id == 0:
                    buf = buf[5:]
                    LOG.info('[Message] CHOKE')

                elif msg_id == 1:
                    buf = buf[5:]
                    LOG.info('[Message] UNCHOKE')

                elif msg_id == 5:
                    bitfield = buf[5: 5 + length - 1]
                    self.have_pieces = bitstring.BitArray(bitfield)
                    LOG.info('[Message] BITFIELD: {}'.format(bitfield))
                    buf = buf[5 + length - 1:]
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


