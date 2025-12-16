"""
Определяет структуру архивного файла и методы чтения/записи.
"""

import struct
import io
import zlib
from typing import List, Dict, Optional
from dataclasses import dataclass


ARCHIVE_MAGIC = b'LZHA'
ARCHIVE_VERSION = 1


@dataclass
class FileEntry:
    filename: str
    original_size: int
    compressed_size: int
    compressed_data: bytes
    crc32: int


class ArchiveHeader:
    def __init__(self):
        self.magic = ARCHIVE_MAGIC
        self.version = ARCHIVE_VERSION
        self.reserved = b'\x00' * 10
    
    def serialize(self) -> bytes:
        output = io.BytesIO()
        output.write(self.magic)
        output.write(struct.pack('B', self.version))
        output.write(struct.pack('B', 0))
        output.write(self.reserved)
        return output.getvalue()
    
    @staticmethod
    def deserialize(data: bytes) -> 'ArchiveHeader':
        if len(data) < 16:
            raise ValueError("Invalid archive header")
        
        header = ArchiveHeader()
        pos = 0
        
        magic = data[pos:pos+4]
        if magic != ARCHIVE_MAGIC:
            raise ValueError("Invalid archive magic")
        pos += 4
        
        version = data[pos]
        if version != ARCHIVE_VERSION:
            raise ValueError(f"Unsupported version: {version}")
        pos += 1
        
        pos += 1
        header.reserved = data[pos:pos+10]
        
        return header


class ArchiveFormat:
    @staticmethod
    def create_archive(entries: List[FileEntry]) -> bytes:
        output = io.BytesIO()
        
        header = ArchiveHeader()
        output.write(header.serialize())
        
        output.write(struct.pack('I', len(entries)))
        
        for entry in entries:
            ArchiveFormat._write_entry(output, entry)
        
        return output.getvalue()
    
    @staticmethod
    def _write_entry(output: io.BytesIO, entry: FileEntry):
        filename_bytes = entry.filename.encode('utf-8')
        
        output.write(struct.pack('H', len(filename_bytes)))
        output.write(filename_bytes)
        output.write(struct.pack('Q', entry.original_size))
        output.write(struct.pack('Q', entry.compressed_size))
        output.write(struct.pack('I', entry.crc32))
        output.write(entry.compressed_data)
    
    @staticmethod
    def read_archive(data: bytes) -> List[FileEntry]:
        pos = 0
        
        if len(data) < 16:
            raise ValueError("Archive too small")
        
        header_data = data[pos:pos+16]
        ArchiveHeader.deserialize(header_data)
        pos += 16
        
        if pos + 4 > len(data):
            raise ValueError("Invalid archive structure")
        
        entry_count = struct.unpack('I', data[pos:pos+4])[0]
        pos += 4
        
        entries = []
        for _ in range(entry_count):
            entry, new_pos = ArchiveFormat._read_entry(data, pos)
            entries.append(entry)
            pos = new_pos
        
        return entries
    
    @staticmethod
    def _read_entry(data: bytes, pos: int) -> tuple:
        if pos + 2 > len(data):
            raise ValueError("Corrupted entry: cannot read filename length")
        
        filename_len = struct.unpack('H', data[pos:pos+2])[0]
        pos += 2
        
        if pos + filename_len > len(data):
            raise ValueError("Corrupted entry: cannot read filename")
        
        filename = data[pos:pos+filename_len].decode('utf-8')
        pos += filename_len
        
        if pos + 16 > len(data):
            raise ValueError("Corrupted entry: cannot read metadata")
        
        original_size = struct.unpack('Q', data[pos:pos+8])[0]
        pos += 8
        compressed_size = struct.unpack('Q', data[pos:pos+8])[0]
        pos += 8
        crc32 = struct.unpack('I', data[pos:pos+4])[0]
        pos += 4
        
        if pos + compressed_size > len(data):
            raise ValueError("Corrupted entry: cannot read compressed data")
        
        compressed_data = data[pos:pos+compressed_size]
        pos += compressed_size
        
        entry = FileEntry(
            filename=filename,
            original_size=original_size,
            compressed_size=compressed_size,
            compressed_data=compressed_data,
            crc32=crc32
        )
        
        return entry, pos


def calculate_crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xffffffff


def verify_integrity(entry: FileEntry, decompressed_data: bytes) -> bool:
    if len(decompressed_data) != entry.original_size:
        return False
    
    calculated_crc = calculate_crc32(decompressed_data)
    return calculated_crc == entry.crc32