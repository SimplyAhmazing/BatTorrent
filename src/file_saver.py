import asyncio
import os

from util import LOG


class FileSaver(object):
    def __init__(self, outdir, torrent):
        self.file_name = self.get_file_path(outdir, torrent)
        self.fd = os.open(self.file_name, os.O_RDWR | os.O_CREAT)
        self.received_blocks_queue = asyncio.Queue()
        asyncio.ensure_future(self.start())

    def get_received_blocks_queue(self):
        return self.received_blocks_queue

    def get_file_path(self, outdir, torrent):
        name = torrent[b'info'][b'name'].decode()
        file_path = os.path.join(outdir, name)
        if os.path.exists(file_path):
            # TODO: add (num) to file name
            LOG.info('Previous download exists')
        return file_path

    async def start(self):
        while True:
            block = await self.received_blocks_queue.get()
            if not block:
                LOG.info('Received poison pill.Exiting')

            block_abs_location, block_data = block
            os.lseek(self.fd, block_abs_location, os.SEEK_SET)
            os.write(self.fd, block_data)
            # with open(os.path.join(os.getcwd(), self.file_name), 'w+b') as f:
            #     print('gopt here..')
            #     f.seek(block_abs_location)
            #     f.write(block_data)