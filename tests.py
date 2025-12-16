import unittest
import tempfile
import os
import sys
from pathlib import Path

from compressor import LZ77Compressor, TokenEncoder, Token, TokenType
from huffman import HuffmanTree, HuffmanEncoder, compress_with_huffman, decompress_with_huffman
from format import ArchiveFormat, FileEntry, calculate_crc32, verify_integrity
from archiver import Archiver


class TestLZ77Compression(unittest.TestCase):
    def setUp(self):
        self.compressor = LZ77Compressor()
    
    def test_simple_text(self):
        data = b"Hello Hello Hello"
        tokens = self.compressor.compress(data)
        decompressed = self.compressor.decompress(tokens)
        self.assertEqual(data, decompressed)
    
    def test_repeated_pattern(self):
        data = b"abcabcabcabc"
        tokens = self.compressor.compress(data)
        decompressed = self.compressor.decompress(tokens)
        self.assertEqual(data, decompressed)
    
    def test_empty_data(self):
        data = b""
        tokens = self.compressor.compress(data)
        decompressed = self.compressor.decompress(tokens)
        self.assertEqual(data, decompressed)
    
    def test_single_byte(self):
        data = b"A"
        tokens = self.compressor.compress(data)
        decompressed = self.compressor.decompress(tokens)
        self.assertEqual(data, decompressed)
    
    def test_random_data(self):
        data = bytes(range(256)) * 10
        tokens = self.compressor.compress(data)
        decompressed = self.compressor.decompress(tokens)
        self.assertEqual(data, decompressed)
    
    def test_token_encoder(self):
        tokens = [
            Token(TokenType.LITERAL, literal=65),
            Token(TokenType.MATCH, length=10, distance=5),
            Token(TokenType.LITERAL, literal=66),
        ]
        encoded = TokenEncoder.encode_tokens(tokens)
        decoded = TokenEncoder.decode_tokens(encoded)
        self.assertEqual(tokens, decoded)


class TestHuffmanEncoding(unittest.TestCase):
    def test_simple_huffman(self):
        data = b"aaabbc"
        tree_data, encoded_data = HuffmanEncoder.encode(data)
        decoded = HuffmanEncoder.decode(tree_data, encoded_data)
        self.assertEqual(data, decoded)
    
    def test_empty_huffman(self):
        data = b""
        tree_data, encoded_data = HuffmanEncoder.encode(data)
        decoded = HuffmanEncoder.decode(tree_data, encoded_data)
        self.assertEqual(data, decoded)
    
    def test_single_char(self):
        data = b"AAAA"
        tree_data, encoded_data = HuffmanEncoder.encode(data)
        decoded = HuffmanEncoder.decode(tree_data, encoded_data)
        self.assertEqual(data, decoded)
    
    def test_compression_wrapper(self):
        data = b"The quick brown fox jumps over the lazy dog"
        compressed = compress_with_huffman(data)
        decompressed = decompress_with_huffman(compressed)
        self.assertEqual(data, decompressed)


class TestArchiveFormat(unittest.TestCase):
    def test_create_and_read_archive(self):
        entries = [
            FileEntry(
                filename="test1.txt",
                original_size=100,
                compressed_size=50,
                compressed_data=b"x" * 50,
                crc32=calculate_crc32(b"x" * 100)
            ),
            FileEntry(
                filename="test2.txt",
                original_size=200,
                compressed_size=100,
                compressed_data=b"y" * 100,
                crc32=calculate_crc32(b"y" * 200)
            ),
        ]
        
        archive_data = ArchiveFormat.create_archive(entries)
        read_entries = ArchiveFormat.read_archive(archive_data)
        
        self.assertEqual(len(read_entries), 2)
        self.assertEqual(read_entries[0].filename, "test1.txt")
        self.assertEqual(read_entries[1].filename, "test2.txt")
        self.assertEqual(read_entries[0].original_size, 100)
        self.assertEqual(read_entries[1].original_size, 200)
    
    def test_crc32_verification(self):
        data = b"Test data"
        entry = FileEntry(
            filename="test.txt",
            original_size=len(data),
            compressed_size=100,
            compressed_data=b"compressed",
            crc32=calculate_crc32(data)
        )
        
        self.assertTrue(verify_integrity(entry, data))
        self.assertFalse(verify_integrity(entry, b"Wrong data"))


class TestArchiver(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.archiver = Archiver(use_huffman=True)
    
    def tearDown(self):
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_compress_decompress_file(self):
        test_file = os.path.join(self.temp_dir, "test.txt")
        with open(test_file, 'wb') as f:
            f.write(b"Hello World! " * 100)
        
        entry = self.archiver.compress_file(test_file)
        self.assertEqual(entry.filename, "test.txt")
        self.assertGreater(entry.original_size, 0)
        self.assertLess(entry.compressed_size, entry.original_size)
    
    def test_create_and_extract_archive(self):
        test_file1 = os.path.join(self.temp_dir, "file1.txt")
        test_file2 = os.path.join(self.temp_dir, "file2.txt")
        archive_path = os.path.join(self.temp_dir, "test.lzha")
        extract_dir = os.path.join(self.temp_dir, "extracted")
        
        with open(test_file1, 'wb') as f:
            f.write(b"Content of file 1\n" * 50)
        
        with open(test_file2, 'wb') as f:
            f.write(b"Content of file 2\n" * 50)
        
        self.archiver.create_archive([test_file1, test_file2], archive_path)
        self.assertTrue(os.path.isfile(archive_path))
        
        self.archiver.extract_archive(archive_path, extract_dir)
        
        extracted_file1 = os.path.join(extract_dir, "file1.txt")
        extracted_file2 = os.path.join(extract_dir, "file2.txt")
        
        self.assertTrue(os.path.isfile(extracted_file1))
        self.assertTrue(os.path.isfile(extracted_file2))
        
        with open(test_file1, 'rb') as f:
            original1 = f.read()
        with open(extracted_file1, 'rb') as f:
            extracted1 = f.read()
        
        self.assertEqual(original1, extracted1)
        
        with open(test_file2, 'rb') as f:
            original2 = f.read()
        with open(extracted_file2, 'rb') as f:
            extracted2 = f.read()
        
        self.assertEqual(original2, extracted2)
    
    def test_add_files_to_archive(self):
        test_file1 = os.path.join(self.temp_dir, "file1.txt")
        test_file2 = os.path.join(self.temp_dir, "file2.txt")
        archive_path = os.path.join(self.temp_dir, "test.lzha")
        
        with open(test_file1, 'wb') as f:
            f.write(b"File 1 content\n" * 30)
        
        self.archiver.create_archive([test_file1], archive_path)
        
        with open(test_file2, 'wb') as f:
            f.write(b"File 2 content\n" * 30)
        
        self.archiver.add_files(archive_path, [test_file2])
        
        extract_dir = os.path.join(self.temp_dir, "extracted")
        self.archiver.extract_archive(archive_path, extract_dir)
        
        self.assertTrue(os.path.isfile(os.path.join(extract_dir, "file1.txt")))
        self.assertTrue(os.path.isfile(os.path.join(extract_dir, "file2.txt")))


class TestEdgeCases(unittest.TestCase):
    def setUp(self):
        self.compressor = LZ77Compressor()
    
    def test_very_long_match(self):
        data = b"A" * 1000
        tokens = self.compressor.compress(data)
        decompressed = self.compressor.decompress(tokens)
        self.assertEqual(data, decompressed)
    
    def test_no_compression_benefit(self):
        import random
        random.seed(42)
        data = bytes(random.randint(0, 255) for _ in range(1000))
        tokens = self.compressor.compress(data)
        decompressed = self.compressor.decompress(tokens)
        self.assertEqual(data, decompressed)
    
    def test_huffman_large_data(self):
        data = b"Lorem ipsum dolor sit amet " * 200
        compressed = compress_with_huffman(data)
        decompressed = decompress_with_huffman(compressed)
        self.assertEqual(data, decompressed)


def run_tests():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestLZ77Compression))
    suite.addTests(loader.loadTestsFromTestCase(TestHuffmanEncoding))
    suite.addTests(loader.loadTestsFromTestCase(TestArchiveFormat))
    suite.addTests(loader.loadTestsFromTestCase(TestArchiver))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())