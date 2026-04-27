import traceback


class ImageBuildException(Exception):
    def __init__(self, msg: str = "Error occurred on Docker while building image."):
        super().__init__(create_exc_context(msg, traceback.format_exc()))


class ImageRemoveException(Exception):
    def __init__(self, msg: str = "Error occurred on Docker while removing image."):
        super().__init__(create_exc_context(msg, traceback.format_exc()))


def create_exc_context(msg: str, traceback_result: str) -> str:
    return f"\n\n[Message]: {msg}\n[Full details]:\n\n{traceback_result}"
