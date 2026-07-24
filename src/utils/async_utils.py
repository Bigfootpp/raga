import asyncio
import functools
from collections.abc import AsyncIterable, AsyncIterator, Callable, Coroutine

_background_tasks: set[asyncio.Task] = set()

async def aenumerate[T](
    async_iterable: AsyncIterable[T],
    start: int = 0
) -> AsyncIterator[tuple[int, T]]:
    i = start
    async for item in async_iterable:
        yield i, item
        i += 1

def fire_and_forget[T](coro: Coroutine[None, None, T]) -> asyncio.Task[T]:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task

def background_task[T, **P](
    func: Callable[P, Coroutine[None, None, T]]
) -> Callable[P, asyncio.Task[T]]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> asyncio.Task[T]:
        coro = func(*args, **kwargs)
        return fire_and_forget(coro)
    return wrapper