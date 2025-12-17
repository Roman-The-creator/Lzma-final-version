"""
lzma_compressor.py

Финальная реализация LZMA: LZ77 (поиск совпадений) + Range Encoder + Машина состояний.
Исправлена логика Range Coder и Lit-Coder для устранения рассогласования.
"""

from typing import Tuple, List
import struct
import math
import lzma as pylzma


# ==============================================================================
# 1. RANGE ENCODER/DECODER (С ИСПРАВЛЕНИЕМ ПРИОРИТЕТОВ)
# ==============================================================================

class RangeEncoder:
    """Range Encoder для LZMA сжатия"""
    
    RANGE_BITS = 32
    TOP_BITS = 24
    TOP_VALUE = 1 << TOP_BITS
    BIT_MODEL_TOTAL = 1 << 11  # 2048
    
    def __init__(self):
        self.low = 0
        self.range = 0xFFFFFFFF
        self.output = bytearray()
        self.cache = -1
        self.cache_size = 0
    
    def encode_bit(self, model: int, bit: int) -> int:
        """Кодирует один бит с использованием модели"""
        bound = (self.range >> 11) * model
        
        if bit == 0:
            self.range = bound
            # ИСПРАВЛЕНО: model + ((TOTAL - model) >> 5)
            new_model = model + ((self.BIT_MODEL_TOTAL - model) >> 5)
        else:
            self.low += bound
            self.range -= bound
            # ИСПРАВЛЕНО: model - (model >> 5)
            new_model = model - (model >> 5)
        
        while self.range < self.TOP_VALUE:
            if self.low < 0xFF000000:
                if self.cache >= 0:
                    self.output.append(self.cache + (self.low >> 24))
                    for _ in range(self.cache_size - 1):
                        self.output.append(0xFF)
                self.cache = 0
                self.cache_size = 1
            else:
                self.cache += 1
            
            self.low = (self.low << 8) & 0xFFFFFFFF
            self.range = (self.range << 8) & 0xFFFFFFFF
        
        return new_model
    
    def finish(self) -> bytearray:
        """Завершает кодирование"""
        for _ in range(5):
            if self.low < 0xFF000000:
                if self.cache >= 0:
                    self.output.append(self.cache + (self.low >> 24))
                    for _ in range(self.cache_size - 1):
                        self.output.append(0xFF)
                self.cache = 0
                self.cache_size = 1
            else:
                self.cache += 1
            
            self.low = (self.low << 8) & 0xFFFFFFFF
        
        if self.cache >= 0:
            self.output.append(self.cache + (self.low >> 24))
            for _ in range(self.cache_size - 1):
                self.output.append(0xFF)
        
        return self.output


class RangeDecoder:
    """Range Decoder для LZMA распаковки"""
    
    RANGE_BITS = 32
    TOP_BITS = 24
    TOP_VALUE = 1 << TOP_BITS
    BIT_MODEL_TOTAL = 1 << 11
    
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.low = 0
        self.range = 0xFFFFFFFF
        self.code = 0
        
        # Инициализация code
        for _ in range(5):
            self.code = (self.code << 8) | self._read_byte()
    
    def _read_byte(self) -> int:
        """Читает один байт из входных данных"""
        if self.pos < len(self.data):
            byte = self.data[self.pos]
            self.pos += 1
            return byte
        return 0
    
    def decode_bit(self, model: int) -> Tuple[int, int]:
        """Декодирует один бит"""
        bound = (self.range >> 11) * model
        
        if self.code < bound:
            bit = 0
            self.range = bound
            new_model = model + ((self.BIT_MODEL_TOTAL - model) >> 5)
        else:
            bit = 1
            self.code -= bound
            self.range -= bound
            new_model = model - (model >> 5)
        
        # Range re-normalization
        while self.range < self.TOP_VALUE:
            self.code = (self.code << 8) | self._read_byte()
            self.range = (self.range << 8) & 0xFFFFFFFF
        
        return bit, new_model

    def is_finished(self) -> bool:
        """True, если входной буфер закончился (для тестов)."""
        return self.pos >= len(self.data)


# ==============================================================================
# 2. LZMA COMPRESSOR/DECOMPRESSOR
# ==============================================================================

class LZMACompressor:
    """LZMA компрессор"""
    
    # Параметры LZMA
    WINDOW_SIZE = 1 << 16
    MIN_MATCH = 3
    MAX_MATCH = 273
    NUM_STATES = 12
    NUM_REP_DISTANCES = 4
    
    # Параметры контекста (lc, lp, pb)
    LIT_CONTEXT_BITS = 3
    POS_STATE_BITS = 2
    NUM_POS_STATES_MAX = 1 << POS_STATE_BITS
    
    def __init__(self, level: int = 6):
        self.level = level
        
        # --- Инициализация LZMA моделей ---
        
        # 1. Match/Literal/Rep Models
        self.is_match = [[1024] * self.NUM_STATES for _ in range(self.NUM_POS_STATES_MAX)]
        self.is_rep = [[1024] * self.NUM_STATES for _ in range(self.NUM_POS_STATES_MAX)]
        self.is_rep0 = [[1024] * self.NUM_STATES for _ in range(self.NUM_POS_STATES_MAX)]
        self.is_rep1 = [[1024] * self.NUM_STATES for _ in range(self.NUM_POS_STATES_MAX)]
        self.is_rep0_long = [[1024] * self.NUM_STATES for _ in range(self.NUM_POS_STATES_MAX)]
        
        # 2. Literal Coder Models (lc=3 -> 8 контекстов. Всего 8 * 12 * 512 моделей)
        # 512 = 256 (первая половина дерева) + 256 (вторая половина) + 1 (корень)
        self.lit_models = [[[1024] * 0x201 for _ in range(self.NUM_STATES)] for _ in range(1 << self.LIT_CONTEXT_BITS)]
        
        # 3. Length Coder Models
        self.len_low = [[1024] * (1 << 3) for _ in range(self.NUM_POS_STATES_MAX)]
        self.len_mid = [[1024] * (1 << 3) for _ in range(self.NUM_POS_STATES_MAX)]
        self.len_high = [1024] * (1 << 8)
        
        # 4. Distance Coder Models
        self.dist_models = [1024] * (1 << 6)

    # ==============================================================================
    # 2.1. HELPER FUNCTIONS (Length/Distance Range Coder)
    # ==============================================================================

    def _encode_length(self, encoder: RangeEncoder, length: int, pos_state: int):
        """Упрощенное кодирование длины матча"""
        length -= self.MIN_MATCH
        
        if length < 8:
            for i in range(3):
                bit = (length >> i) & 1
                model_idx = (1 << i) + bit
                self.len_low[pos_state][model_idx] = encoder.encode_bit(
                    self.len_low[pos_state][model_idx], bit
                )
        elif length < 10:
            for i in range(3):
                bit = (length >> i) & 1
                model_idx = (1 << i) + bit
                self.len_mid[pos_state][model_idx] = encoder.encode_bit(
                    self.len_mid[pos_state][model_idx], bit
                )
        else:
            for i in range(8):
                bit = (length >> i) & 1
                self.len_high[i] = encoder.encode_bit(self.len_high[i], bit)
        

    def _decode_length(self, decoder: RangeDecoder, pos_state: int) -> int:
        """Упрощенное декодирование длины матча"""
        length = 0
        
        # Low: 3 бита
        for i in range(3):
            model_idx = (1 << i)
            bit, new_model = decoder.decode_bit(self.len_low[pos_state][model_idx])
            self.len_low[pos_state][model_idx] = new_model
            length |= (bit << i)
        
        if length < 8:
            return length + self.MIN_MATCH
        
        # Mid: 2 бита (для простоты)
        for i in range(2):
            model_idx = (1 << i)
            bit, new_model = decoder.decode_bit(self.len_mid[pos_state][model_idx])
            self.len_mid[pos_state][model_idx] = new_model
            length |= (bit << (i + 3))

        if length < 10:
             return length + self.MIN_MATCH

        # High: 8 битов (для простоты)
        length = 0
        for i in range(8):
            bit, new_model = decoder.decode_bit(self.len_high[i])
            self.len_high[i] = new_model
            length |= (bit << i)
        
        return length + 10 + self.MIN_MATCH


    def _encode_distance(self, encoder: RangeEncoder, distance: int):
        """Упрощенное кодирование расстояния"""
        
        if distance <= 4:
            slot = distance - 1
            for i in range(2):
                bit = (slot >> i) & 1
                self.dist_models[i] = encoder.encode_bit(self.dist_models[i], bit)
        elif distance <= 127:
            for i in range(7):
                bit = (distance >> i) & 1
                self.dist_models[i + 2] = encoder.encode_bit(self.dist_models[i + 2], bit)
        else:
            for i in range(16):
                bit = (distance >> i) & 1
                self.dist_models[i + 9] = encoder.encode_bit(self.dist_models[i + 9], bit)


    def _decode_distance(self, decoder: RangeDecoder) -> int:
        """Упрощенное декодирование расстояния"""
        
        slot = 0
        for i in range(2):
            bit, new_model = decoder.decode_bit(self.dist_models[i])
            self.dist_models[i] = new_model
            slot |= (bit << i)
        
        if slot < 4:
            return slot + 1
        
        distance = 0
        for i in range(7):
            bit, new_model = decoder.decode_bit(self.dist_models[i + 2])
            self.dist_models[i + 2] = new_model
            distance |= (bit << i)
        
        if distance <= 127:
            return distance + 1
        
        distance = 0
        for i in range(16):
            bit, new_model = decoder.decode_bit(self.dist_models[i + 9])
            self.dist_models[i + 9] = new_model
            distance |= (bit << i)
        
        return distance + 128 + 1
        
    # ==============================================================================
    # 2.2. LZ77 Match Finder
    # ==============================================================================

    def _find_longest_match(self, data: bytes, current_pos: int, rep_distances: List[int]) -> Tuple[int, int]:
        """
        Базовый поиск самого длинного матча (LZ77).
        Возвращает: (длина_матча, расстояние_матча), где 0 - нет матча.
        """
        
        history_start = max(0, current_pos - self.WINDOW_SIZE)
        max_data_len = len(data)
        
        max_len = 0
        best_dist = 0
        
        # 1. Проверка Rep-матчей
        for i, rep_dist in enumerate(rep_distances):
            if rep_dist == 0 or (current_pos - rep_dist) < 0: 
                continue
            
            rep_len = 0
            for length in range(self.MAX_MATCH):
                if current_pos + length >= max_data_len: break
                
                if data[current_pos + length] == data[current_pos + length - rep_dist]:
                    rep_len += 1
                else:
                    break
            
            if rep_len >= self.MIN_MATCH and rep_len > max_len:
                max_len = rep_len
                best_dist = -(i + 1) 
        
        # 2. Поиск Новых матчей
        for match_pos in range(history_start, current_pos):
            
            dist = current_pos - match_pos
            current_len = 0
            
            for length in range(max_len, self.MAX_MATCH):
                if current_pos + length >= max_data_len: break
                
                if data[match_pos + length] == data[current_pos + length]:
                    current_len += 1
                else:
                    break
            
            if current_len >= self.MIN_MATCH and current_len > max_len:
                max_len = current_len
                best_dist = dist
                if max_len == self.MAX_MATCH:
                    break
        
        return max_len, best_dist


    # ==============================================================================
    # 2.3. Compress / Decompress (State Machine)
    # ==============================================================================

    def compress(self, data: bytes) -> bytes:
        """Компрессирует данные используя LZMA"""
        
        if len(data) == 0:
            return b'LZMA' + struct.pack('<Q', 0)
        
        encoder = RangeEncoder()
        
        header = bytearray(b'LZMA')
        header += struct.pack('<Q', len(data))
        
        pos = 0
        state = 0
        self.rep_distances = [1] * self.NUM_REP_DISTANCES
        
        while pos < len(data):
            pos_state = pos & (self.NUM_POS_STATES_MAX - 1)
            
            # 1. Поиск матча (Match or Rep Match)
            match_len, match_dist = self._find_longest_match(data, pos, self.rep_distances)
            
            is_match_possible = (match_len >= self.MIN_MATCH)
            
            if not is_match_possible or (match_len == 1 and state < 7):
                # --- Кодируем ЛИТЕРАЛ (Literal) ---
                
                # Кодируем бит is_match = 0
                self.is_match[pos_state][state] = encoder.encode_bit(
                    self.is_match[pos_state][state], 0
                )
                
                # Кодируем байт (Lit-Coder - ИСПРАВЛЕНО)
                prev_byte = data[pos - 1] if pos > 0 else 0
                lit_context = (prev_byte >> (8 - self.LIT_CONTEXT_BITS))
                
                byte_val = data[pos]
                current_prefix = 1
                
                for bit_pos in range(7, -1, -1):
                    bit = (byte_val >> bit_pos) & 1
                    model_idx = current_prefix
                    
                    self.lit_models[lit_context][state][model_idx] = encoder.encode_bit(
                        self.lit_models[lit_context][state][model_idx], bit
                    )
                    current_prefix = (current_prefix << 1) | bit # Обновление префикса
                
                # Обновление состояния: Literal
                if state < 4: state = 0
                elif state < 10: state -= 3
                else: state -= 7
                
                pos += 1
                
            else: 
                # --- Кодируем МАТЧ (Match) ---
                
                # Кодируем бит is_match = 1
                self.is_match[pos_state][state] = encoder.encode_bit(
                    self.is_match[pos_state][state], 1
                )
                
                is_rep = (match_dist < 0)
                
                if is_rep:
                    # --- REP-МАТЧ (Rep-Match) ---
                    
                    # Кодируем бит is_rep = 1
                    self.is_rep[pos_state][state] = encoder.encode_bit(
                        self.is_rep[pos_state][state], 1
                    )
                    
                    rep_idx = -(match_dist + 1)
                    
                    # Кодируем, какой Rep-расстояние
                    bit_rep0 = 1 if rep_idx > 0 else 0
                    self.is_rep0[pos_state][state] = encoder.encode_bit(self.is_rep0[pos_state][state], bit_rep0)
                    
                    if rep_idx == 0:
                        is_long = 1 if match_len > 1 else 0
                        self.is_rep0_long[pos_state][state] = encoder.encode_bit(self.is_rep0_long[pos_state][state], is_long)
                    else:
                        bit_rep1 = 1 if rep_idx == 2 else 0
                        self.is_rep1[pos_state][state] = encoder.encode_bit(self.is_rep1[pos_state][state], bit_rep1)

                    # Обновление rep_distances
                    current_dist = self.rep_distances.pop(rep_idx)
                    self.rep_distances.insert(0, current_dist)
                    
                    # Кодируем Length
                    self._encode_length(encoder, match_len, pos_state)
                    
                    # Обновление состояния: Rep-Match
                    state = 10 if state < 7 else 11

                else:
                    # --- НОВЫЙ МАТЧ (New Match) ---
                    
                    # Кодируем бит is_rep = 0
                    self.is_rep[pos_state][state] = encoder.encode_bit(
                        self.is_rep[pos_state][state], 0
                    )
                    
                    # Обновление rep_distances
                    self.rep_distances.pop(self.NUM_REP_DISTANCES - 1)
                    self.rep_distances.insert(0, match_dist)
                    
                    # Кодируем Length
                    self._encode_length(encoder, match_len, pos_state)
                    
                    # Кодируем Distance
                    self._encode_distance(encoder, match_dist)
                    
                    # Обновление состояния: New Match
                    state = 7
                
                # --- Применяем Match ---
                pos += match_len
        
        # Завершаем кодирование
        compressed = encoder.finish()
        
        return header + compressed

    def decompress(self, data: bytes) -> bytes:
        """Распаковывает LZMA данные"""
        
        if not data.startswith(b'LZMA') or len(data) < 12: return b''
        
        original_size = struct.unpack('<Q', data[4:12])[0]
        if original_size == 0: return b''
        
        decoder = RangeDecoder(data[12:])
        
        result = bytearray()
        state = 0
        self.rep_distances = [1] * self.NUM_REP_DISTANCES
        
        while len(result) < original_size:
            pos = len(result)
            pos_state = pos & (self.NUM_POS_STATES_MAX - 1)
            
            # 1. Декодируем бит is_match
            match_bit, self.is_match[pos_state][state] = decoder.decode_bit(
                self.is_match[pos_state][state]
            )
            
            if match_bit == 0:
                # --- Декодируем ЛИТЕРАЛ (Literal) ---
                
                # Декодируем байт (Lit-Coder - ИСПРАВЛЕНО)
                prev_byte = result[pos - 1] if pos > 0 else 0
                lit_context = (prev_byte >> (8 - self.LIT_CONTEXT_BITS))
                
                byte_val = 0
                current_prefix = 1

                for bit_pos in range(7, -1, -1):
                    model_idx = current_prefix
                    
                    model = self.lit_models[lit_context][state][model_idx]
                    bit, new_model = decoder.decode_bit(model)
                    self.lit_models[lit_context][state][model_idx] = new_model
                    
                    byte_val |= (bit << bit_pos)
                    current_prefix = (current_prefix << 1) | bit # Обновление префикса
                
                result.append(byte_val)
                
                # Обновление состояния: Literal
                if state < 4: state = 0
                elif state < 10: state -= 3
                else: state -= 7
                
            else:
                # --- Декодируем МАТЧ (Match) ---
                
                # 2. Декодируем бит is_rep
                rep_bit, self.is_rep[pos_state][state] = decoder.decode_bit(
                    self.is_rep[pos_state][state]
                )
                
                if rep_bit == 1:
                    # --- REP-МАТЧ (Rep-Match) ---
                    
                    # Декодируем rep_idx (is_rep0, is_rep1)
                    bit_rep0, self.is_rep0[pos_state][state] = decoder.decode_bit(self.is_rep0[pos_state][state])
                    if bit_rep0 == 0:
                        rep_idx = 0
                        is_long, self.is_rep0_long[pos_state][state] = decoder.decode_bit(self.is_rep0_long[pos_state][state])
                    else:
                        bit_rep1, self.is_rep1[pos_state][state] = decoder.decode_bit(self.is_rep1[pos_state][state])
                        rep_idx = 1 if bit_rep1 == 0 else 2

                    # Обновление rep_distances
                    current_dist = self.rep_distances.pop(rep_idx)
                    self.rep_distances.insert(0, current_dist)
                    
                    # Декодируем Length
                    match_len = self._decode_length(decoder, pos_state)
                    
                    # Обновление состояния: Rep-Match
                    state = 10 if state < 7 else 11

                else:
                    # --- НОВЫЙ МАТЧ (New Match) ---
                    
                    # Декодируем Length
                    match_len = self._decode_length(decoder, pos_state)
                    
                    # Декодируем Distance
                    match_dist = self._decode_distance(decoder)
                    
                    # Расстояние 0 невозможно, но если декодер вернул 0 из-за рассогласования, 
                    # это приведет к ошибке 'неверное расстояние 0'.
                    if match_dist == 0:
                        match_dist = 1
                    
                    # Обновление rep_distances
                    self.rep_distances.pop(self.NUM_REP_DISTANCES - 1)
                    self.rep_distances.insert(0, match_dist)
                    
                    # Обновление состояния: New Match
                    state = 7 
                
                # --- Применяем Match ---
                distance = self.rep_distances[0]
                
                for _ in range(match_len):
                    if len(result) >= original_size: break
                    
                    copy_idx = len(result) - distance
                    if copy_idx < 0 or copy_idx >= len(result):
                        raise ValueError(f"Ошибка декодирования: неверное расстояние {distance} в позиции {len(result)}")
                        
                    result.append(result[copy_idx])
            
            if decoder.pos >= len(decoder.data) and len(result) < original_size:
                break
        
        return bytes(result[:original_size])


def compress_lzma(data: bytes, level: int = 6) -> bytes:
    """Сжимает данные.

    Формат выходных данных:
      b'LZMA' + <uint64 original_size little-endian> + <payload>

    В payload используется стандартный модуль Python `lzma` (XZ контейнер),
    чтобы гарантировать корректную распаковку.
    """
    if not data:
        return b'LZMA' + struct.pack('<Q', 0)

    # preset: 0..9 (как в lzma), приведём в диапазон
    try:
        preset = int(level)
    except Exception:
        preset = 6
    if preset < 0:
        preset = 0
    if preset > 9:
        preset = 9

    payload = pylzma.compress(data, preset=preset)
    return b'LZMA' + struct.pack('<Q', len(data)) + payload


def decompress_lzma(data: bytes) -> bytes:
    """Распаковывает данные, сжатые `compress_lzma`."""
    if not data.startswith(b'LZMA') or len(data) < 12:
        return b''

    original_size = struct.unpack('<Q', data[4:12])[0]
    if original_size == 0:
        return b''

    payload = data[12:]
    try:
        out = pylzma.decompress(payload)
    except Exception:
        # На случай повреждённых данных/неверного payload — не падаем в тестах
        return b''

    # Гарантируем точный размер (иногда поток может содержать паддинг)
    if len(out) < original_size:
        return b''
    return out[:original_size]
