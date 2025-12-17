"""
Архиватор с использованием LZMA компрессии
"""

import os
import struct
from pathlib import Path
from typing import List, Optional
from lzma_compressor import compress_lzma, decompress_lzma
import zlib


class ArchiveEntry:
    """Запись в архиве"""
    
    def __init__(self, filename: str, original_size: int = 0, 
                 compressed_size: int = 0, crc32: int = 0, data: bytes = b''):
        self.filename = filename
        self.original_size = original_size
        self.compressed_size = compressed_size
        self.crc32 = crc32
        self.data = data


class ArchiveFormat:
    """Формат архива на основе LZMA"""
    
    MAGIC = b'LZMA'
    VERSION = 1
    
    @staticmethod
    def write_archive(entries: List[ArchiveEntry], output_path: str) -> None:
        """Записывает архив на диск"""
        
        with open(output_path, 'wb') as f:
            # Заголовок
            f.write(ArchiveFormat.MAGIC)
            f.write(struct.pack('<I', ArchiveFormat.VERSION))
            f.write(struct.pack('<I', len(entries)))
            
            # Записываем каждый файл
            for entry in entries:
                # Имя файла
                filename_bytes = entry.filename.encode('utf-8')
                f.write(struct.pack('<H', len(filename_bytes)))
                f.write(filename_bytes)
                
                # Размеры и CRC
                f.write(struct.pack('<Q', entry.original_size))
                f.write(struct.pack('<Q', entry.compressed_size))
                f.write(struct.pack('<I', entry.crc32))
                
                # Сжатые данные
                f.write(entry.data)
    
    @staticmethod
    def read_archive(data: bytes) -> List[ArchiveEntry]:
        """Читает архив из памяти"""
        
        if not data.startswith(ArchiveFormat.MAGIC):
            raise ValueError("Неверный формат архива")
        
        pos = 4
        version = struct.unpack_from('<I', data, pos)[0]
        pos += 4
        
        if version != ArchiveFormat.VERSION:
            raise ValueError(f"Неподдерживаемая версия: {version}")
        
        num_files = struct.unpack_from('<I', data, pos)[0]
        pos += 4
        
        entries = []
        for _ in range(num_files):
            # Читаем имя файла
            filename_len = struct.unpack_from('<H', data, pos)[0]
            pos += 2
            
            filename = data[pos:pos+filename_len].decode('utf-8')
            pos += filename_len
            
            # Читаем размеры и CRC
            original_size = struct.unpack_from('<Q', data, pos)[0]
            pos += 8
            
            compressed_size = struct.unpack_from('<Q', data, pos)[0]
            pos += 8
            
            crc32 = struct.unpack_from('<I', data, pos)[0]
            pos += 4
            
            # Читаем сжатые данные
            compressed_data = data[pos:pos+compressed_size]
            pos += compressed_size
            
            entry = ArchiveEntry(filename, original_size, compressed_size, crc32, compressed_data)
            entries.append(entry)
        
        return entries


class Archiver:
    """LZMA архиватор"""
    
    def __init__(self, level: int = 6):
        self.level = level
    
    def create_archive(self, input_files: List[str], output_path: str) -> None:
        """Создает архив из списка файлов"""
        
        entries = []
        total_original = 0
        total_compressed = 0
        
        for file_path in input_files:
            if not os.path.isfile(file_path):
                print(f"Ошибка: файл {file_path} не найден")
                continue
            
            # Читаем файл
            with open(file_path, 'rb') as f:
                data = f.read()
            
            original_size = len(data)
            
            # Вычисляем CRC32 ДО сжатия
            crc32 = zlib.crc32(data) & 0xffffffff
            
            # Сжимаем данные
            compressed_data = compress_lzma(data, self.level)
            compressed_size = len(compressed_data)
            
            ratio = (compressed_size / original_size * 100) if original_size > 0 else 0
            print(f"Compressing {Path(file_path).name}... OK ({ratio:.1f}%)")
            
            # Создаем запись
            entry = ArchiveEntry(
                Path(file_path).name,
                original_size,
                compressed_size,
                crc32,
                compressed_data
            )
            entries.append(entry)
            
            total_original += original_size
            total_compressed += compressed_size
        
        # Пишем архив
        ArchiveFormat.write_archive(entries, output_path)
        
        total_ratio = (total_compressed / total_original * 100) if total_original > 0 else 0
        print(f"\nArchive created: {output_path}")
        print(f"Total: {total_original} -> {total_compressed} bytes ({total_ratio:.1f}%)")
    
    def extract_archive(self, archive_path: str, output_dir: str) -> None:
        """Распаковывает архив"""
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Читаем архив
        with open(archive_path, 'rb') as f:
            archive_data = f.read()
        
        entries = ArchiveFormat.read_archive(archive_data)
        
        print(f"Extracting {len(entries)} files...")
        
        for entry in entries:
            # Распаковываем данные
            original_data = decompress_lzma(entry.data)
            
            # Проверяем CRC32
            crc32 = zlib.crc32(original_data) & 0xffffffff
            if crc32 != entry.crc32:
                print(f"Ошибка: CRC32 не совпадает для {entry.filename}")
                continue
            
            # Пишем файл
            output_path = os.path.join(output_dir, entry.filename)
            with open(output_path, 'wb') as f:
                f.write(original_data)
            
            print(f"Extracting {entry.filename}... OK")
        
        print("Extraction complete")
    
    def list_archive(self, archive_path: str) -> None:
        """Показывает содержимое архива"""
        
        with open(archive_path, 'rb') as f:
            archive_data = f.read()
        
        entries = ArchiveFormat.read_archive(archive_data)
        
        print("Filename".ljust(40), "Original".rjust(10), "Compressed".rjust(10), "Ratio".rjust(8))
        print("-" * 68)
        
        total_original = 0
        total_compressed = 0
        
        for entry in entries:
            ratio = (entry.compressed_size / entry.original_size * 100) if entry.original_size > 0 else 0
            print(
                entry.filename.ljust(40),
                str(entry.original_size).rjust(10),
                str(entry.compressed_size).rjust(10),
                f"{ratio:.1f}%".rjust(8)
            )
            total_original += entry.original_size
            total_compressed += entry.compressed_size
        
        print("-" * 68)
        total_ratio = (total_compressed / total_original * 100) if total_original > 0 else 0
        print(
            "TOTAL".ljust(40),
            str(total_original).rjust(10),
            str(total_compressed).rjust(10),
            f"{total_ratio:.1f}%".rjust(8)
        )
    
    def add_files(self, archive_path: str, input_files: List[str]) -> None:
        """Добавляет файлы в существующий архив"""
        
        # Читаем существующий архив
        with open(archive_path, 'rb') as f:
            archive_data = f.read()
        
        entries = ArchiveFormat.read_archive(archive_data)
        
        # Добавляем новые файлы
        for file_path in input_files:
            if not os.path.isfile(file_path):
                print(f"Ошибка: файл {file_path} не найден")
                continue
            
            with open(file_path, 'rb') as f:
                data = f.read()
            
            original_size = len(data)
            crc32 = zlib.crc32(data) & 0xffffffff
            compressed_data = compress_lzma(data, self.level)
            compressed_size = len(compressed_data)
            
            ratio = (compressed_size / original_size * 100) if original_size > 0 else 0
            print(f"Adding {Path(file_path).name}... OK ({ratio:.1f}%)")
            
            entry = ArchiveEntry(
                Path(file_path).name,
                original_size,
                compressed_size,
                crc32,
                compressed_data
            )
            entries.append(entry)
        
        # Пишем обновленный архив
        ArchiveFormat.write_archive(entries, archive_path)
        print("Archive updated: " + archive_path)