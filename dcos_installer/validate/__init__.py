# dcos.validate lib processes incoming user and dcosgen configuration, ensures that 
# it passes dependency checks (in the case of dcos-specific configuration) and 
# assertions on configuration type. 
#
# Validate should always be called on the configuration before executing generate 
# library. 
#
# Example
# from dcosgen import dcosconfig, validate
#
# my_extra_options = {
#     'config_dir': '/my/dcos/installer/loca/path'
# }
#
# errors, validate_out = validate.onprem_config(dcosconfig.DcosConfigObject().set(my_extra_options))
#
# if not errors:
#     # execute generate
#
# else:
#     print("Errors found: ", validate_out)
from dcosgen import DCOSLogger
log = DCOSLogger(__name__).log

from dcosgen.validate import onprem 
#from dcosgen.validate import $some_other_installation_type


class DCOSValidateConfig():
    """
    DCOSValidateConfig accepts a dictionary of configuration and
    verifies that the install_type contains all neccessary dependencies
    and that those dependencies are of the correct type.

    DCOSValidateConfig can be called on its own and one can 
    assume that it will 'do the right thing'. However, you can also
    call any of it's methods.
    """
    def __init__(self, dcos_config={}):
        self.dcos_config = dcos_config
        
        if len(self.dcos_config) > 0:
            self.validate()


    def validate(self):
        if 'install_type' in self.dcos_config:
            if self.dcos_config['install_type'] == 'onprem':
                log.info("Detected %s validation type", self.dcos_config['install_type'])
                errors, messages = self.onprem_config()
                return errors, messages

            # else if some other type of install...
            else:
                log.error("Unsupported install type %s", self.dcos_config['install_type'])
                raise ValueError("Unsupported install type %s. Supported types: %s", self.dcos_config['install_type'], self.dcos_config['available_install_types'])
        else:
            log.error("Must pass 'install_type' in DCOS configuration.")
            raise ValueError("Must pass 'install_type' in DCOS configuration")

    def onprem_config(self):
        """
        Entry point to on-prem configuration validation.
        """
        log.info("Executing on-premise configuration validation...")
        errors, validate_out = onprem.check_dependencies(self.dcos_config)
        
        if errors:
            log.error("Errors found in on-prem dependencies...")
            log.error(validate_out)
            log.error("Please make sure these errors are corrected. Setting no-generate flag.")
            return errors, validate_out

        else: 
            log.info("Configuration looks good!")
            return errors, validate_out
