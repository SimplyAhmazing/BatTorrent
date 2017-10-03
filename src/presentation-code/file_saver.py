class FileSaver(object):
    def __init__(self, torrent, file_queue):
        self.file_obj = self.open_file(torrent)
        self.file_queue = file_queue

    async def start(self):
        while True:
            piece = await self.file_queue.get()

            if not piece: # Poison pill
                return

            await self.save(piece)
