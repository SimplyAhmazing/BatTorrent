import asyncio

async def foo():
    # yield 1
    await asyncio.sleep(0)


async def run():
    print(type(foo()))
    print('is coroutine', asyncio.iscoroutinefunction(foo))
    # print('is instance coroutine obj', asyncio.iscoroutine(foo()))
    # async for i in foo():
    #     print('Got', i)
    await foo()



loop = asyncio.get_event_loop()
loop.run_until_complete(run())
