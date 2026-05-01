"""Custom exceptions wrapping docker.errors.APIError and friends.
Service callers handle these, never raw Docker SDK errors."""


class DockerOpsException(Exception):
    pass


class ImageBuildException(DockerOpsException):
    pass


class ImageRemoveException(DockerOpsException):
    pass


class ContainerCreateException(DockerOpsException):
    pass


class ContainerOpException(DockerOpsException):
    pass
