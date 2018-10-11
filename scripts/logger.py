import logging
import logging.handlers
import logging.config
import coloredlogs
import os.path

# Setup Logging
logging.handlers = logging.handlers
if os.path.isfile('logging_config.ini'):
    logging.config.fileConfig('logging_config.ini')
else:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s: %(levelname)6s: [%(filename)s:%(lineno)s]:  %(message)s"
    )

logger = logging.getLogger()


def getLogger():
    global logger
    return logger
