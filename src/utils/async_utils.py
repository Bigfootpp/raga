from typing import AsyncIterable, AsyncIterator, TypeVar

T = TypeVar("T")

async def aenumerate(
    async_iterable: AsyncIterable[T], 
    start: int = 0
) -> AsyncIterator[tuple[int, T]]:
    i = start
    async_iterable_iter = async_iterable
    async for item in async_iterable_iter:
        yield i, item
        i += 1