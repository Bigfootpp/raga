import asyncio
import functools
from collections.abc import Coroutine
from typing import Any, AsyncIterable, AsyncIterator, Callable, TypeVar, ParamSpec

T = TypeVar("T")
P = ParamSpec("P")

_background_tasks: set[asyncio.Task[Any]] = set()

async def aenumerate(
    async_iterable: AsyncIterable[T], 
    start: int = 0
) -> AsyncIterator[tuple[int, T]]:
    i = start
    async_iterable_iter = async_iterable
    async for item in async_iterable_iter:
        yield i, item
        i += 1

def fire_and_forget(coro: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task

def background_task(func: Callable[P, Coroutine[Any, Any, T]]) -> Callable[P, asyncio.Task[T]]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> asyncio.Task[T]:
        coro = func(*args, **kwargs)
        return fire_and_forget(coro)
    return wrapper