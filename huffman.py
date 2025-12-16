"""
Реализует кодирование Хаффмана для дополнительного сжатия данных.
Использует переменную длину кодов: частые значения кодируются короче.
"""

import struct
import io
import heapq
from typing import Dict, List, Optional, Tuple
from collections import Counter


class HuffmanNode:
    def __init__(self, char: Optional[int] = None, freq: int = 0, 
                 left: Optional['HuffmanNode'] = None, 
                 right: Optional['HuffmanNode'] = None):
        self.char = char
        self.freq = freq
        self.left = left
        self.right = right
    
    def __lt__(self, other):
        return self.freq < other.freq
    
    def __eq__(self, other):
        return self.freq == other.freq


class HuffmanTree:
    def __init__(self):
        self.root: Optional[HuffmanNode] = None
        self.codes: Dict[int, str] = {}
        self.decode_table: Dict[str, int] = {}
    
    def build(self, frequencies: Dict[int, int]):
        if not frequencies:
            return
        
        heap = [HuffmanNode(char=ch, freq=freq) 
                for ch, freq in frequencies.items()]
        heapq.heapify(heap)
        
        if len(heap) == 1:
            node = heapq.heappop(heap)
            self.root = HuffmanNode(freq=node.freq, left=node)
        else:
            while len(heap) > 1:
                left = heapq.heappop(heap)
                right = heapq.heappop(heap)
                
                parent = HuffmanNode(freq=left.freq + right.freq, 
                                    left=left, right=right)
                heapq.heappush(heap, parent)
            
            self.root = heap[0]
        
        self._generate_codes()
    
    def _generate_codes(self):
        self.codes.clear()
        self.decode_table.clear()
        
        if not self.root:
            return
        
        def traverse(node: Optional[HuffmanNode], code: str):
            if node is None:
                return
            
            if node.char is not None:
                self.codes[node.char] = code if code else '0'
                self.decode_table[code if code else '0'] = node.char
                return
            
            traverse(node.left, code + '0')
            traverse(node.right, code + '1')
        
        traverse(self.root, '')
    
    def serialize(self) -> bytes:
        output = io.BytesIO()
        
        if not self.codes:
            output.write(struct.pack('H', 0))
            return output.getvalue()
        
        output.write(struct.pack('H', len(self.codes)))
        
        for char, code in self.codes.items():
            output.write(struct.pack('B', char))
            output.write(struct.pack('B', len(code)))
            output.write(code.encode('ascii'))
        
        return output.getvalue()
    
    @staticmethod
    def deserialize(data: bytes) -> 'HuffmanTree':
        tree = HuffmanTree()
        pos = 0
        
        if len(data) < 2:
            return tree
        
        count = struct.unpack('H', data[pos:pos+2])[0]
        pos += 2
        
        if count == 0:
            return tree
        
        tree.codes = {}
        tree.decode_table = {}
        
        for _ in range(count):
            if pos + 2 > len(data):
                break
            
            char = data[pos]
            pos += 1
            code_len = data[pos]
            pos += 1
            
            if pos + code_len > len(data):
                break
            
            code = data[pos:pos+code_len].decode('ascii')
            pos += code_len
            
            tree.codes[char] = code
            tree.decode_table[code] = char
        
        return tree


class BitStream:
    def __init__(self):
        self.bits = []
    
    def write_bit(self, bit: int):
        self.bits.append(1 if bit else 0)
    
    def write_bits(self, code: str):
        for bit in code:
            self.write_bit(int(bit))
    
    def to_bytes(self) -> bytes:
        padding = (8 - len(self.bits) % 8) % 8
        self.bits.extend([0] * padding)
        
        output = io.BytesIO()
        output.write(struct.pack('B', padding))
        
        for i in range(0, len(self.bits), 8):
            byte = 0
            for j in range(8):
                byte = (byte << 1) | self.bits[i + j]
            output.write(struct.pack('B', byte))
        
        return output.getvalue()
    
    @staticmethod
    def from_bytes(data: bytes) -> 'BitStream':
        stream = BitStream()
        
        if not data:
            return stream
        
        padding = data[0]
        
        for i in range(1, len(data)):
            byte = data[i]
            for j in range(7, -1, -1):
                stream.bits.append((byte >> j) & 1)
        
        if padding > 0:
            stream.bits = stream.bits[:-padding]
        
        return stream


class HuffmanEncoder:
    @staticmethod
    def encode(data: bytes) -> Tuple[bytes, bytes]:
        if not data:
            tree_data = HuffmanTree().serialize()
            return tree_data, b''
        
        frequencies = Counter(data)
        tree = HuffmanTree()
        tree.build(frequencies)
        
        bitstream = BitStream()
        for byte in data:
            code = tree.codes.get(byte, '0')
            bitstream.write_bits(code)
        
        tree_data = tree.serialize()
        encoded_data = bitstream.to_bytes()
        
        return tree_data, encoded_data
    
    @staticmethod
    def decode(tree_data: bytes, encoded_data: bytes) -> bytes:
        tree = HuffmanTree.deserialize(tree_data)
        
        if not tree.decode_table:
            return b''
        
        bitstream = BitStream.from_bytes(encoded_data)
        
        output = bytearray()
        current_code = ''
        
        for bit in bitstream.bits:
            current_code += str(bit)
            
            if current_code in tree.decode_table:
                char = tree.decode_table[current_code]
                output.append(char)
                current_code = ''
        
        return bytes(output)


def compress_with_huffman(data: bytes) -> bytes:
    tree_data, encoded_data = HuffmanEncoder.encode(data)
    
    output = io.BytesIO()
    output.write(struct.pack('I', len(tree_data)))
    output.write(tree_data)
    output.write(struct.pack('I', len(encoded_data)))
    output.write(encoded_data)
    
    return output.getvalue()


def decompress_with_huffman(data: bytes) -> bytes:
    pos = 0
    
    if len(data) < 8:
        return b''
    
    tree_size = struct.unpack('I', data[pos:pos+4])[0]
    pos += 4
    
    if pos + tree_size > len(data):
        return b''
    
    tree_data = data[pos:pos+tree_size]
    pos += tree_size
    
    if pos + 4 > len(data):
        return b''
    
    encoded_size = struct.unpack('I', data[pos:pos+4])[0]
    pos += 4
    
    if pos + encoded_size > len(data):
        return b''
    
    encoded_data = data[pos:pos+encoded_size]
    
    return HuffmanEncoder.decode(tree_data, encoded_data)