class CloudConfigParameters:

    def AddTestclusterEphemeralVolume(self):
        """Adds necessary units for mounting an ephemeral instance drive
        at /ephemeral."""
        raise NotImplementedError()

    def GetParameter(self, name):
        """Gets out the string to use to refer to the given template parameter"""
        raise NotImplementedError()

    @property
    def extra_files(self):
        return self.extra_files_base + self.extra_files_extra

    @property
    def late_units(self):
        return self.late_units_base + self.late_units_extra

    extra_files_extra = ""
    late_units_extra = ""

    stack_name = None
    early_units = None
    config_writer = None
    resolvers = ["8.8.8.8", "8.8.4.4"]
