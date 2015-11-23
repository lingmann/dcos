import os
import sys

from dcos_installer import server
from dcos_installer.log import DCOSLog

log = DCOSLog(__name__).log


class DcosInstaller:
    def __init__(self, options):
        """
        The web based installer leverages Flask to present end-users of
        dcos_installer with a clean web interface to configure their
        site-based installation of DCOS.
        """
        self.set_log_level(options)
        self.set_install_dir(options)

        if options.mode == 'web':
            server.run(options)
        else:
            log.error("Sorry, %s is not a usable run mode.", options.mode)
            sys.exit(1)

    def set_install_dir(self, options):
        """
        Ensures the default or user provided install directory path
        exists.
        """
        try:
            os.stat(options.install_directory)
        except:
            log.info('{} does not exist, creating.'.format(options.install_directory))
            os.mkdir(options.install_directory)
        # Logging directory
        try:
            os.stat(options.log_directory)
        except:
            log.info('{} does not exist, creating.'.format(options.log_directory))
            os.mkdir(options.log_directory)

    def set_log_level(self, options):
        """
        Given a map of options, parse for log level flag and set the
        default logging level.
        """
        log.log_level = options.log_level
#        if options.log_level == "debug":
#            log.basicConfig(level=log.DEBUG)
#            log.debug("Log level set to DEBUG")
#        elif options.log_level == "info":
#            log.basicConfig(level=log.INFO)
#            log.info("Log level set to INFO")
#        else:
#            log.error("Logging option not available: %s", options.log_level)
#            sys.exit(1)
