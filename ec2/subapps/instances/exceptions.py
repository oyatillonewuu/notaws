class InstanceError(Exception):
    pass


class ImageNotReadyError(InstanceError):
    """Image has no built active_build; cannot create instance."""
    pass


class InstanceHasNoContainerError(InstanceError):
    """Instance has no docker_container_id assigned yet."""
    pass
