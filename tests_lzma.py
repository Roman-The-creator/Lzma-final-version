"""
Модульные тесты для LZMA архиватора
"""

import unittest
import os
import tempfile
import zlib
from lzma_compressor import compress_lzma, decompress_lzma, RangeEncoder, RangeDecoder
from archiver_lzma import Archiver, ArchiveFormat, ArchiveEntry


class TestRangeEncoder(unittest.TestCase):
    """Тесты для Range Encoder"""
    
    def test_encode_zero_bits(self):
        """Тест кодирования нулевых битов"""
        encoder = RangeEncoder()
        model = 1024
        
        for _ in range(8):
            model = encoder.encode_bit(model, 0)
        
        result = encoder.finish()
        self.assertIsInstance(result, bytearray)
        self.assertGreater(len(result), 0)
    
    def test_encode_one_bits(self):
        """Тест кодирования единичных битов"""
        encoder = RangeEncoder()
        model = 1024
        
        for _ in range(8):
            model = encoder.encode_bit(model, 1)
        
        result = encoder.finish()
        self.assertIsInstance(result, bytearray)
        self.assertGreater(len(result), 0)
    
    def test_encode_alternating_bits(self):
        """Тест кодирования чередующихся битов"""
        encoder = RangeEncoder()
        model = 1024
        
        for i in range(16):
            bit = i % 2
            model = encoder.encode_bit(model, bit)
        
        result = encoder.finish()
        self.assertIsInstance(result, bytearray)
        self.assertGreater(len(result), 0)
    
    def test_model_updates(self):
        """Тест обновления моделей"""
        encoder = RangeEncoder()
        model_0 = 1024
        model_1 = 1024
        
        # Кодируем ноль
        model_0_new = encoder.encode_bit(model_0, 0)
        # Модель должна измениться
        self.assertNotEqual(model_0, model_0_new)
        
        # Кодируем единицу
        encoder2 = RangeEncoder()
        model_1_new = encoder2.encode_bit(model_1, 1)
        # Модели должны отличаться
        self.assertNotEqual(model_0_new, model_1_new)


class TestRangeDecoder(unittest.TestCase):
    """Тесты для Range Decoder"""
    
    def test_decoder_initialization(self):
        """Тест инициализации декодера"""
        data = b'\x00\x00\x00\x00\x00'
        decoder = RangeDecoder(data)
        
        self.assertEqual(decoder.pos, 5)
        self.assertIsNotNone(decoder.code)
        self.assertEqual(decoder.range, 0xFFFFFFFF)
    
    def test_decoder_with_empty_data(self):
        """Тест декодера с пустыми данными"""
        decoder = RangeDecoder(b'')
        self.assertTrue(decoder.is_finished())


class TestLZMACompressor(unittest.TestCase):
    """Тесты для LZMA компрессора"""
    
    def test_compress_empty_data(self):
        """Тест сжатия пустых данных"""
        data = b''
        compressed = compress_lzma(data)
        
        self.assertTrue(compressed.startswith(b'LZMA'))
        self.assertEqual(len(compressed), 12)  # Заголовок LZMA
    
    def test_compress_single_byte(self):
        """Тест сжатия одного байта"""
        data = b'A'
        compressed = compress_lzma(data)
        
        self.assertTrue(compressed.startswith(b'LZMA'))
        self.assertGreater(len(compressed), 12)
    
    def test_compress_repeated_data(self):
        """Тест сжатия повторяющихся данных"""
        data = b'AAAAAAAAAA'
        compressed = compress_lzma(data)
        
        self.assertTrue(compressed.startswith(b'LZMA'))
        self.assertGreater(len(compressed), 0)
    
    def test_compress_text(self):
        """Тест сжатия текста"""
        data = b'Hello World! Hello World!'
        compressed = compress_lzma(data)
        
        self.assertTrue(compressed.startswith(b'LZMA'))
        self.assertGreater(len(compressed), 12)
    
    def test_compress_russian_text(self):
        """Тест сжатия русского текста"""
        data = 'Привет мир! Привет мир!'.encode('utf-8')
        compressed = compress_lzma(data)
        
        self.assertTrue(compressed.startswith(b'LZMA'))
        self.assertGreater(len(compressed), 12)
    
    def test_compress_decompress_roundtrip(self):
        """Тест сжатия и распаковки"""
        data = b'Test data for compression'
        compressed = compress_lzma(data)
        decompressed = decompress_lzma(compressed)
        
        self.assertEqual(data, decompressed)
    
    def test_compress_large_data(self):
        """Тест сжатия больших данных"""
        data = b'X' * 10000
        compressed = compress_lzma(data)
        decompressed = decompress_lzma(compressed)
        
        self.assertEqual(data, decompressed)
    
    def test_compression_levels(self):
        """Тест разных уровней сжатия"""
        data = b'Compression level test' * 100
        
        compressed_0 = compress_lzma(data, level=0)
        compressed_6 = compress_lzma(data, level=6)
        compressed_9 = compress_lzma(data, level=9)
        
        # Все должны сжаться
        self.assertTrue(compressed_0.startswith(b'LZMA'))
        self.assertTrue(compressed_6.startswith(b'LZMA'))
        self.assertTrue(compressed_9.startswith(b'LZMA'))
        
        # Все должны распаковаться правильно
        self.assertEqual(data, decompress_lzma(compressed_0))
        self.assertEqual(data, decompress_lzma(compressed_6))
        self.assertEqual(data, decompress_lzma(compressed_9))


class TestArchiveFormat(unittest.TestCase):
    """Тесты для формата архива"""
    
    def test_archive_entry_creation(self):
        """Тест создания записи архива"""
        entry = ArchiveEntry(
            filename='test.txt',
            original_size=100,
            compressed_size=50,
            crc32=12345,
            data=b'compressed'
        )
        
        self.assertEqual(entry.filename, 'test.txt')
        self.assertEqual(entry.original_size, 100)
        self.assertEqual(entry.compressed_size, 50)
    
    def test_archive_magic_number(self):
        """Тест магической сигнатуры архива"""
        self.assertEqual(ArchiveFormat.MAGIC, b'LZMA')
        self.assertEqual(ArchiveFormat.VERSION, 1)
    
    def test_write_read_single_file_archive(self):
        """Тест записи и чтения архива с одним файлом"""
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_path = os.path.join(tmpdir, 'test.lzma')
            
            # Создаем запись
            data = b'Test file content'
            crc32 = zlib.crc32(data) & 0xffffffff
            compressed = compress_lzma(data)
            
            entry = ArchiveEntry(
                filename='test.txt',
                original_size=len(data),
                compressed_size=len(compressed),
                crc32=crc32,
                data=compressed
            )
            
            # Пишем архив
            ArchiveFormat.write_archive([entry], archive_path)
            
            # Читаем архив
            with open(archive_path, 'rb') as f:
                archive_data = f.read()
            
            entries = ArchiveFormat.read_archive(archive_data)
            
            # Проверяем
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].filename, 'test.txt')
            self.assertEqual(entries[0].original_size, len(data))
            self.assertEqual(entries[0].crc32, crc32)
    
    def test_write_read_multiple_files_archive(self):
        """Тест архива с несколькими файлами"""
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_path = os.path.join(tmpdir, 'test.lzma')
            
            entries = []
            for i in range(3):
                data = f'File {i} content'.encode()
                crc32 = zlib.crc32(data) & 0xffffffff
                compressed = compress_lzma(data)
                
                entry = ArchiveEntry(
                    filename=f'file{i}.txt',
                    original_size=len(data),
                    compressed_size=len(compressed),
                    crc32=crc32,
                    data=compressed
                )
                entries.append(entry)
            
            # Пишем архив
            ArchiveFormat.write_archive(entries, archive_path)
            
            # Читаем архив
            with open(archive_path, 'rb') as f:
                archive_data = f.read()
            
            read_entries = ArchiveFormat.read_archive(archive_data)
            
            # Проверяем
            self.assertEqual(len(read_entries), 3)
            for i, entry in enumerate(read_entries):
                self.assertEqual(entry.filename, f'file{i}.txt')


class TestArchiver(unittest.TestCase):
    """Тесты для архиватора"""
    
    def setUp(self):
        """Подготовка к тестам"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = self.temp_dir.name
        self.archiver = Archiver(level=6)
    
    def tearDown(self):
        """Очистка после тестов"""
        self.temp_dir.cleanup()
    
    def test_create_archive_single_file(self):
        """Тест создания архива с одним файлом"""
        # Создаем файл
        test_file = os.path.join(self.temp_path, 'test.txt')
        test_data = b'Test content'
        with open(test_file, 'wb') as f:
            f.write(test_data)
        
        # Создаем архив
        archive_path = os.path.join(self.temp_path, 'archive.lzma')
        self.archiver.create_archive([test_file], archive_path)
        
        # Проверяем, что архив создан
        self.assertTrue(os.path.isfile(archive_path))
        self.assertGreater(os.path.getsize(archive_path), 0)
    
    def test_create_archive_multiple_files(self):
        """Тест создания архива с несколькими файлами"""
        # Создаем файлы
        files = []
        for i in range(3):
            test_file = os.path.join(self.temp_path, f'file{i}.txt')
            with open(test_file, 'wb') as f:
                f.write(f'Content {i}'.encode())
            files.append(test_file)
        
        # Создаем архив
        archive_path = os.path.join(self.temp_path, 'archive.lzma')
        self.archiver.create_archive(files, archive_path)
        
        # Проверяем
        self.assertTrue(os.path.isfile(archive_path))
    
    def test_extract_archive(self):
        """Тест распаковки архива"""
        # Создаем файл
        test_file = os.path.join(self.temp_path, 'test.txt')
        test_data = b'Test content for extraction'
        with open(test_file, 'wb') as f:
            f.write(test_data)
        
        # Создаем архив
        archive_path = os.path.join(self.temp_path, 'archive.lzma')
        self.archiver.create_archive([test_file], archive_path)
        
        # Распаковываем
        extract_dir = os.path.join(self.temp_path, 'extracted')
        self.archiver.extract_archive(archive_path, extract_dir)
        
        # Проверяем
        extracted_file = os.path.join(extract_dir, 'test.txt')
        self.assertTrue(os.path.isfile(extracted_file))
        
        with open(extracted_file, 'rb') as f:
            extracted_data = f.read()
        
        self.assertEqual(test_data, extracted_data)
    
    def test_archive_file_integrity(self):
        """Тест целостности файлов в архиве"""
        # Создаем файлы
        test_files = {}
        for i in range(3):
            test_file = os.path.join(self.temp_path, f'file{i}.txt')
            test_data = f'Content file {i}'.encode('utf-8')
            with open(test_file, 'wb') as f:
                f.write(test_data)
            test_files[test_file] = test_data
        
        # Создаем архив
        archive_path = os.path.join(self.temp_path, 'archive.lzma')
        self.archiver.create_archive(list(test_files.keys()), archive_path)
        
        # Распаковываем
        extract_dir = os.path.join(self.temp_path, 'extracted')
        self.archiver.extract_archive(archive_path, extract_dir)
        
        # Проверяем целостность каждого файла
        for original_file, original_data in test_files.items():
            filename = os.path.basename(original_file)
            extracted_file = os.path.join(extract_dir, filename)
            
            with open(extracted_file, 'rb') as f:
                extracted_data = f.read()
            
            self.assertEqual(original_data, extracted_data)
    
    def test_add_files_to_archive(self):
        """Тест добавления файлов в архив"""
        # Создаем первый файл и архив
        test_file1 = os.path.join(self.temp_path, 'file1.txt')
        with open(test_file1, 'wb') as f:
            f.write(b'File 1')
        
        archive_path = os.path.join(self.temp_path, 'archive.lzma')
        self.archiver.create_archive([test_file1], archive_path)
        
        # Добавляем второй файл
        test_file2 = os.path.join(self.temp_path, 'file2.txt')
        with open(test_file2, 'wb') as f:
            f.write(b'File 2')
        
        self.archiver.add_files(archive_path, [test_file2])
        
        # Распаковываем и проверяем
        extract_dir = os.path.join(self.temp_path, 'extracted')
        self.archiver.extract_archive(archive_path, extract_dir)
        
        self.assertTrue(os.path.isfile(os.path.join(extract_dir, 'file1.txt')))
        self.assertTrue(os.path.isfile(os.path.join(extract_dir, 'file2.txt')))
    
    def test_compression_ratio(self):
        """Тест коэффициента сжатия"""
        # Создаем файл с повторяющимся содержимым
        test_file = os.path.join(self.temp_path, 'repeated.txt')
        test_data = b'AAAA' * 1000  # 4000 байт повторений
        with open(test_file, 'wb') as f:
            f.write(test_data)
        
        # Создаем архив
        archive_path = os.path.join(self.temp_path, 'archive.lzma')
        self.archiver.create_archive([test_file], archive_path)
        
        # Проверяем сжатие
        original_size = os.path.getsize(test_file)
        archive_size = os.path.getsize(archive_path)
        
        # Архив должен быть меньше оригинала
        self.assertLess(archive_size, original_size)


class TestRussianText(unittest.TestCase):
    """Тесты для русского текста"""
    
    def test_compress_russian_text_roundtrip(self):
        """Тест сжатия-распаковки русского текста"""
        data = 'Привет мир! Это тестовая строка на русском языке.'.encode('utf-8')
        
        compressed = compress_lzma(data)
        decompressed = decompress_lzma(compressed)
        
        self.assertEqual(data, decompressed)
    
    def test_archive_russian_filenames(self):
        """Тест архива с русскими именами файлов"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Создаем файл с русским именем
            test_file = os.path.join(tmpdir, 'тест.txt')
            with open(test_file, 'wb') as f:
                f.write('Русский текст'.encode('utf-8'))
            
            # Создаем архив
            archive_path = os.path.join(tmpdir, 'архив.lzma')
            archiver = Archiver()
            archiver.create_archive([test_file], archive_path)
            
            # Распаковываем
            extract_dir = os.path.join(tmpdir, 'извлечено')
            archiver.extract_archive(archive_path, extract_dir)
            
            # Проверяем
            extracted_file = os.path.join(extract_dir, 'тест.txt')
            self.assertTrue(os.path.isfile(extracted_file))


def run_tests():
    """Запускает все тесты"""
    unittest.main(verbosity=2)


if __name__ == '__main__':
    run_tests()