import asyncio
import functools


def make_blocking(f):
    """
    Wrapper to make an async function run as a blocking function
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        result = f(*args, **kwargs)
        if asyncio.iscoroutine(result):
            return asyncio.get_event_loop().run_until_complete(result)
        return result

    return wrapper
