import hashlib
import logging
import random
import string

LOG = logging.getLogger('')
PEER_ID = 'SA' + ''.join(
    random.choice(string.ascii_lowercase + string.digits)
    for i in range(18)
)
PEER_ID_HASH = hashlib.sha1(PEER_ID.encode()).digest()
REQUEST_SIZE = 2**14  # 10 * 1024