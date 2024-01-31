from enum import Enum
from typing import Any, Optional, Tuple

class CompressionEnum(str, Enum):
    none: str
    lzma: str
    zstd: str

def get_compressed_ext(compression_type: str) -> str: ...
def compress(input_data: Any, compression_type: CompressionEnum = ..., compression_level: Optional[int] = None) -> Tuple[bytes, CompressionEnum, int]: ...
def decompress(compressed_data: bytes, compression_type: CompressionEnum) -> Any: ...
