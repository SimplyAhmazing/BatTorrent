import sys

from torrio import DownloadSession, Torrent


if __name__ == '__main__':
    torrent = Torrent(sys.argv[1])
    downloader = DownloadSession(torrent)
    print(torrent)
    print(downloader)
