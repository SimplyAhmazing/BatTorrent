class Foo():
    def __iter__(self):
        yield 1


# print([x for x in Foo()])


class FooAsync(object):
    def __iter__(self):
        await asyncio.sleep(1)
        
