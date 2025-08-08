import logging

from rich.logging import RichHandler

LOG = logging.getLogger()
LOG.setLevel(level=logging.INFO)
FORMAT = "%(message)s"
logging.basicConfig(
    level=logging.DEBUG, format=FORMAT, datefmt="[%X]", handlers=[RichHandler(level=logging.INFO)]
)
