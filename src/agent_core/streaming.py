from typing import Iterator

class Chunk:
    def __init__(self, type: str, data):
        self.type = type
        self.data = data
    
    def to_dict(self):
        return {
            "type": self.type,
            "data": self.data
        }
    
    def __str__(self) -> str:
        return str(self.to_dict())

class ResponseChunk(Chunk):
    def __init__(self, content: str):
        super().__init__("response", content)

class ThoughtChunk(Chunk):
    def __init__(self, content: str):
        super().__init__("thought", content)

class Stream:
    def __init__(self):
        pass

    def __next__(self) -> Chunk:
        return ResponseChunk(" nexted")

    def __iter__(self) -> Iterator[Chunk]:
        yield ResponseChunk("This")
        yield ResponseChunk(" is")
        yield ResponseChunk(" a")
        yield ResponseChunk(" test")