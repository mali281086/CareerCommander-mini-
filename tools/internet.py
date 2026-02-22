import socket
from tools.logger import logger

def is_internet_available(host="8.8.8.8", port=53, timeout=3):
    """
    Checks if internet is available by trying to connect to a reliable host (Google DNS).
    """
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error as ex:
        logger.warning(f"Internet check failed: {ex}")
        return False

def wait_for_internet(timeout=300, interval=10):
    """
    Blocks until internet is available or timeout is reached.
    """
    import time
    start = time.time()
    while time.time() - start < timeout:
        if is_internet_available():
            return True
        logger.info(f"Waiting for internet connection... (retrying in {interval}s)")
        time.sleep(interval)
    return False
