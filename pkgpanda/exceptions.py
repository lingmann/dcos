class RepositoryError(Exception):
    pass


class PackageError(RepositoryError):
    pass


class ValidationError(Exception):
    pass
