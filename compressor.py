# Поиск повторяющейся последовательности байтов

"""
LZ77 Compression Module

Реализует алгоритм LZ77 для поиска и кодирования повторяющихся
последовательностей данных.
"""

import struct
import io
from typing import List, Tuple, Optional, Dict
from collections import defaultdict, Counter


WINDOW_SIZE = 32 * 1024
MIN_MATCH = 3
MAX_MATCH = 258
HASH_BITS = 16
HASH_SIZE = 1 << HASH_BITS


class TokenType:
    LITERAL = 0
    MATCH = 1


class Token:
    def __init__(self, token_type: int, length: int = 0, distance: int = 0, literal: int = 0):
        self.type = token_type
        self.length = length
        self.distance = distance
        self.literal = literal
    
    def __repr__(self):
        if self.type == TokenType.LITERAL:
            return f"LITERAL({self.literal:02x})"
        else:
            return f"MATCH(len={self.length}, dist={self.distance})"
    
    def __eq__(self, other):
        if not isinstance(other, Token):
            return False
        return (self.type == other.type and 
                self.length == other.length and 
                self.distance == other.distance and 
                self.literal == other.literal)


class MatchFinder:
    def __init__(self):
        self.hash_chains: Dict[int, List[int]] = defaultdict(list)
        self.data = b''
    
    def _hash3(self, data: bytes, pos: int) -> int:
        if pos + 3 > len(data):
            return 0
        
        b0 = data[pos]
        b1 = data[pos + 1] if pos + 1 < len(data) else 0
        b2 = data[pos + 2] if pos + 2 < len(data) else 0
        
        h = ((b0 * 65599 + b1) * 65599 + b2) & (HASH_SIZE - 1)
        return h
    
    def update(self, data: bytes):
        start_pos = len(self.data)
        self.data = data
        
        for pos in range(start_pos, len(data) - 2):
            h = self._hash3(data, pos)
            self.hash_chains[h].append(pos)
    
    def find_best_match(self, pos: int, window_start: int) -> Optional[Tuple[int, int]]:
        if pos + MIN_MATCH > len(self.data):
            return None
        
        h = self._hash3(self.data, pos)
        candidates = self.hash_chains[h]
        
        best_length = MIN_MATCH - 1
        best_distance = 0
        
        for candidate_pos in reversed(candidates):
            if candidate_pos >= pos or candidate_pos < window_start:
                continue
            
            match_length = 0
            max_possible_length = min(MAX_MATCH, len(self.data) - pos)
            
            while (match_length < max_possible_length and
                   self.data[candidate_pos + match_length] == 
                   self.data[pos + match_length]):
                match_length += 1
            
            if match_length > best_length:
                best_length = match_length
                best_distance = pos - candidate_pos
                
                if best_length >= 258:
                    break
        
        if best_length >= MIN_MATCH:
            return (best_length, best_distance)
        return None


class LZ77Compressor:
    def __init__(self, window_size: int = WINDOW_SIZE, 
                 min_match: int = MIN_MATCH,
                 max_match: int = MAX_MATCH):
        self.window_size = window_size
        self.min_match = min_match
        self.max_match = max_match
        self.matcher = MatchFinder()
    
    def compress(self, data: bytes) -> List[Token]:
        if not data:
            return []
        
        self.matcher.update(data)
        tokens: List[Token] = []
        
        pos = 0
        while pos < len(data):
            window_start = max(0, pos - self.window_size)
            match = self.matcher.find_best_match(pos, window_start)
            
            if match and match[0] >= self.min_match:
                length, distance = match
                tokens.append(Token(TokenType.MATCH, length=length, distance=distance))
                pos += length
            else:
                tokens.append(Token(TokenType.LITERAL, literal=data[pos]))
                pos += 1
        
        return tokens
    
    def decompress(self, tokens: List[Token]) -> bytes:
        output = bytearray()
        
        for token in tokens:
            if token.type == TokenType.LITERAL:
                output.append(token.literal)
            
            elif token.type == TokenType.MATCH:
                match_pos = len(output) - token.distance
                
                for _ in range(token.length):
                    output.append(output[match_pos])
                    match_pos += 1
        
        return bytes(output)


class TokenEncoder:
    @staticmethod
    def encode_tokens(tokens: List[Token]) -> bytes:
        output = io.BytesIO()
        
        for token in tokens:
            if token.type == TokenType.LITERAL:
                byte_val = token.literal & 0xFF
                output.write(struct.pack('B', 0x00))
                output.write(struct.pack('B', byte_val))
            
            else:
                encoded_length = token.length - MIN_MATCH
                
                assert token.length <= MAX_MATCH
                assert token.distance <= WINDOW_SIZE
                
                output.write(struct.pack('B', 0x01))
                output.write(struct.pack('B', encoded_length))
                output.write(struct.pack('H', token.distance))
        
        return output.getvalue()
    
    @staticmethod
    def decode_tokens(data: bytes) -> List[Token]:
        tokens: List[Token] = []
        pos = 0
        
        while pos < len(data):
            token_type = data[pos]
            pos += 1
            
            if token_type == 0x00:
                if pos >= len(data):
                    break
                literal_val = data[pos]
                pos += 1
                tokens.append(Token(TokenType.LITERAL, literal=literal_val))
            
            elif token_type == 0x01:
                if pos + 3 > len(data):
                    break
                
                encoded_length = data[pos]
                pos += 1
                distance = struct.unpack('H', data[pos:pos+2])[0]
                pos += 2
                
                length = encoded_length + MIN_MATCH
                tokens.append(Token(TokenType.MATCH, length=length, distance=distance))
        
        return tokens


def compress_data(data: bytes) -> bytes:
    compressor = LZ77Compressor()
    tokens = compressor.compress(data)
    return TokenEncoder.encode_tokens(tokens)


def decompress_data(compressed: bytes) -> bytes:
    tokens = TokenEncoder.decode_tokens(compressed)
    compressor = LZ77Compressor()
    return compressor.decompress(tokens)


class CompressionStats:
    def __init__(self, tokens: List[Token], original_size: int):
        self.tokens = tokens
        self.original_size = original_size
        
        self.literal_count = sum(1 for t in tokens if t.type == TokenType.LITERAL)
        self.match_count = sum(1 for t in tokens if t.type == TokenType.MATCH)
        
        self.total_match_length = sum(
            t.length for t in tokens if t.type == TokenType.MATCH
        )
        
        self.estimated_compressed = (
            self.literal_count * 2 +
            self.match_count * 4
        )
        
        self.compression_ratio = (
            self.estimated_compressed / original_size * 100 
            if original_size > 0 else 0
        )
    
    def print_stats(self):
        print(f"LZ77 Compression Statistics:")
        print(f"  Original size:       {self.original_size} bytes")
        print(f"  Literals:            {self.literal_count}")
        print(f"  Matches:             {self.match_count}")
        print(f"  Total match length:  {self.total_match_length}")
        if self.match_count > 0:
            print(f"  Avg match length:    {self.total_match_length / self.match_count:.1f}")
        print(f"  Estimated compressed: {self.estimated_compressed} bytes")
        print(f"  Compression ratio:   {self.compression_ratio:.1f}%")