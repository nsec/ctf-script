import logging

import coloredlogs

LOG = logging.getLogger()
LOG.setLevel(level=logging.DEBUG)
coloredlogs.install(level="DEBUG", logger=LOG)
