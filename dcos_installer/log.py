import logging


class DCOSLog(object):
    def __init__(self, submodule_name=__name__):
        levels = {
            'debug': logging.DEBUG,
            'info': logging.INFO,
            'warning': logging.WARNING,
            'error': logging.ERROR,
            'critical': logging.CRITICAL
        }
        # Default log level to debug
        self.log_level = 'debug'

        # Create a level from the log_level instance
        level = levels.get(self.log_level, logging.NOTSET)
        logging.basicConfig(level=level)

        # Set self to the logging object
        self.log = logging.getLogger(submodule_name)
