"""
Главный класс для сжатия и разжатия файлов.
"""

import os
from pathlib import Path
from typing import List, Optional
from compressor import LZ77Compressor, TokenEncoder, Token, TokenType
from huffman import compress_with_huffman, decompress_with_huffman
from format import ArchiveFormat, FileEntry, calculate_crc32, verify_integrity


class Archiver:
    def __init__(self, use_huffman: bool = True):
        self.use_huffman = use_huffman
        self.compressor = LZ77Compressor()
    
    def compress_file(self, file_path: str) -> FileEntry:
        with open(file_path, 'rb') as f:
            data = f.read()
        
        original_size = len(data)
        
        tokens = self.compressor.compress(data)
        lz77_compressed = TokenEncoder.encode_tokens(tokens)
        
        if self.use_huffman:
            final_compressed = compress_with_huffman(lz77_compressed)
        else:
            final_compressed = lz77_compressed
        
        crc32 = calculate_crc32(data)
        filename = Path(file_path).name
        
        entry = FileEntry(
            filename=filename,
            original_size=original_size,
            compressed_size=len(final_compressed),
            compressed_data=final_compressed,
            crc32=crc32
        )
        
        return entry
    
    def decompress_file(self, entry: FileEntry, output_dir: str = '.') -> bool:
        if self.use_huffman:
            lz77_compressed = decompress_with_huffman(entry.compressed_data)
        else:
            lz77_compressed = entry.compressed_data
        
        tokens = TokenEncoder.decode_tokens(lz77_compressed)
        decompressed = self.compressor.decompress(tokens)
        
        if not verify_integrity(entry, decompressed):
            print(f"Warning: CRC32 mismatch for {entry.filename}")
            return False
        
        output_path = os.path.join(output_dir, entry.filename)
        
        os.makedirs(output_dir, exist_ok=True)
        
        with open(output_path, 'wb') as f:
            f.write(decompressed)
        
        return True
    
    def create_archive(self, file_paths: List[str], archive_path: str):
        entries = []
        
        for file_path in file_paths:
            if not os.path.isfile(file_path):
                print(f"Warning: {file_path} not found, skipping")
                continue
            
            print(f"Compressing {file_path}...", end=" ")
            entry = self.compress_file(file_path)
            entries.append(entry)
            
            ratio = (entry.compressed_size / entry.original_size * 100) if entry.original_size > 0 else 0
            print(f"OK ({ratio:.1f}%)")
        
        if not entries:
            print("No files to archive")
            return
        
        archive_data = ArchiveFormat.create_archive(entries)
        
        with open(archive_path, 'wb') as f:
            f.write(archive_data)
        
        total_original = sum(e.original_size for e in entries)
        total_compressed = sum(e.compressed_size for e in entries)
        total_ratio = (total_compressed / total_original * 100) if total_original > 0 else 0
        
        print(f"\nArchive created: {archive_path}")
        print(f"Total: {total_original} -> {total_compressed} bytes ({total_ratio:.1f}%)")
    
    def extract_archive(self, archive_path: str, output_dir: str = '.'):
        if not os.path.isfile(archive_path):
            print(f"Error: Archive {archive_path} not found")
            return
        
        with open(archive_path, 'rb') as f:
            archive_data = f.read()
        
        try:
            entries = ArchiveFormat.read_archive(archive_data)
        except ValueError as e:
            print(f"Error reading archive: {e}")
            return
        
        print(f"Extracting {len(entries)} files...")
        
        for entry in entries:
            print(f"Extracting {entry.filename}...", end=" ")
            success = self.decompress_file(entry, output_dir)
            if success:
                print("OK")
            else:
                print("FAILED")
        
        print("Extraction complete")
    
    def list_archive(self, archive_path: str):
        if not os.path.isfile(archive_path):
            print(f"Error: Archive {archive_path} not found")
            return
        
        with open(archive_path, 'rb') as f:
            archive_data = f.read()
        
        try:
            entries = ArchiveFormat.read_archive(archive_data)
        except ValueError as e:
            print(f"Error reading archive: {e}")
            return
        
        print(f"{'Filename':<40} {'Original':>12} {'Compressed':>12} {'Ratio':>8}")
        print("-" * 80)
        
        total_original = 0
        total_compressed = 0
        
        for entry in entries:
            ratio = (entry.compressed_size / entry.original_size * 100) if entry.original_size > 0 else 0
            print(f"{entry.filename:<40} {entry.original_size:>12} {entry.compressed_size:>12} {ratio:>7.1f}%")
            
            total_original += entry.original_size
            total_compressed += entry.compressed_size
        
        print("-" * 80)
        total_ratio = (total_compressed / total_original * 100) if total_original > 0 else 0
        print(f"{'TOTAL':<40} {total_original:>12} {total_compressed:>12} {total_ratio:>7.1f}%")
    
    def add_files(self, archive_path: str, file_paths: List[str]):
        if not os.path.isfile(archive_path):
            print(f"Error: Archive {archive_path} not found")
            return
        
        with open(archive_path, 'rb') as f:
            archive_data = f.read()
        
        try:
            existing_entries = ArchiveFormat.read_archive(archive_data)
        except ValueError as e:
            print(f"Error reading archive: {e}")
            return
        
        for file_path in file_paths:
            if not os.path.isfile(file_path):
                print(f"Warning: {file_path} not found, skipping")
                continue
            
            filename = Path(file_path).name
            
            existing_entries = [e for e in existing_entries if e.filename != filename]
            
            print(f"Adding {file_path}...", end=" ")
            entry = self.compress_file(file_path)
            existing_entries.append(entry)
            print("OK")
        
        archive_data = ArchiveFormat.create_archive(existing_entries)
        
        with open(archive_path, 'wb') as f:
            f.write(archive_data)
        
        print(f"Archive updated: {archive_path}")