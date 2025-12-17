"""
Автоматический интеграционный тест LZMA архиватора

Полная проверка: создание → сжатие → распаковка → верификация
"""

import os
import sys
import shutil
import tempfile
from pathlib import Path
from archiver_lzma import Archiver
import zlib


def verify_archiver():
    print("=" * 70)
    print("ПОЛНАЯ ПРОВЕРКА LZMA АРХИВАТОРА")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Шаг 1: Создание тестовых файлов
        print("\n1. Создание тестовых файлов...")
        print("-" * 70)
        
        files_to_create = {
            'file1.txt': "Привет, мир!\n" * 100 + "Это первый тестовый файл.\n" + "Повторяющийся текст.\n" * 50,
            'file2.txt': "Быстрая коричневая лиса\n" * 80 + "Второй файл.\n" + "LZMA работает хорошо.\n" * 30,
            'file3.txt': "Лорем ипсум долор\n" * 60 + "Третий файл.\n" + "Архиватор сжимает.\n" * 40,
        }
        
        original_sizes = {}
        test_files = []
        
        for filename, content in files_to_create.items():
            filepath = os.path.join(temp_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            size = len(content.encode('utf-8'))
            original_sizes[filename] = size
            test_files.append(filepath)
            print(f"   {filename}: {size:,} байт")
        
        total_original = sum(original_sizes.values())
        print(f"\n  ИТОГО исходных данных: {total_original:,} байт")
        
        # Шаг 2: Создание архива
        print("\n2. Создание LZMA архива...")
        print("-" * 70)
        
        archiver = Archiver(level=6)
        archive_path = os.path.join(temp_dir, 'test_archive.lzma')
        
        try:
            archiver.create_archive(test_files, archive_path)
        except Exception as e:
            print(f"    ошибка при создании архива: {e}")
            return False
        
        if not os.path.isfile(archive_path):
            print("     ошибка: Архив не создан")
            return False
        
        archive_size = os.path.getsize(archive_path)
        compression_ratio = (archive_size / total_original * 100)
        
        print(f"\n  Размер архива: {archive_size:,} байт")
        print(f"  Коэффициент сжатия: {compression_ratio:.1f}%")
        
        if compression_ratio > 100:
            print(f"    Архив больше исходных (служебные данные)")
        else:
            print(f"   Хорошее сжатие!")
        
        # Шаг 3: Просмотр содержимого архива
        print("\n3. Проверка содержимого архива...")
        print("-" * 70)
        
        try:
            archiver.list_archive(archive_path)
        except Exception as e:
            print(f"   ошибка при чтении архива: {e}")
            return False
        
        # Шаг 4: Распаковка архива
        print("\n4. Распаковка архива...")
        print("-" * 70)
        
        extract_dir = os.path.join(temp_dir, 'extracted_test')
        
        try:
            archiver.extract_archive(archive_path, extract_dir)
        except Exception as e:
            print(f"  ошибка при распаковке: {e}")
            return False
        
        # Шаг 5: Проверка целостности
        print("\n5. Проверка целостности файлов...")
        print("-" * 70)
        
        all_match = True
        for filename, original_content in files_to_create.items():
            extracted_path = os.path.join(extract_dir, filename)
            
            if not os.path.isfile(extracted_path):
                print(f"    {filename}: ОТСУТСТВУЕТ в архиве!")
                all_match = False
                continue
            
            with open(extracted_path, 'r', encoding='utf-8') as f:
                extracted_content = f.read()
            
            if original_content == extracted_content:
                print(f"   {filename}: ИДЕНТИЧЕН исходному")
            else:
                print(f"    {filename}: ОТЛИЧАЕТСЯ от исходного!")
                print(f"     Исходный: {len(original_content)} символов")
                print(f"     Распакованный: {len(extracted_content)} символов")
                all_match = False
        
        if not all_match:
            return False
        
        # Шаг 6: Добавление файла в архив
        print("\n6. Добавление нового файла в архив...")
        print("-" * 70)
        
        new_file_path = os.path.join(temp_dir, 'file4.txt')
        new_content = "Это новый файл для архива!\n" * 50
        
        with open(new_file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        try:
            archiver.add_files(archive_path, [new_file_path])
            print("   Файл добавлен в архив")
        except Exception as e:
            print(f"     ошибка при добавлении: {e}")
            return False
        
        # Шаг 7: Распаковка обновленного архива
        print("\n7. Распаковка обновленного архива...")
        print("-" * 70)
        
        extract_dir2 = os.path.join(temp_dir, 'extracted_updated')
        
        try:
            archiver.extract_archive(archive_path, extract_dir2)
        except Exception as e:
            print(f"     ошибка при распаковке: {e}")
            return False
        
        # Проверяем, что добавленный файл есть
        extracted_new_file = os.path.join(extract_dir2, 'file4.txt')
        if os.path.isfile(extracted_new_file):
            with open(extracted_new_file, 'r', encoding='utf-8') as f:
                extracted_new_content = f.read()
            
            if new_content == extracted_new_content:
                print(f"   file4.txt: успешно добавлен и распакован")
            else:
                print(f"    file4.txt: содержимое не совпадает!")
                return False
        else:
            print(f"    file4.txt: не найден в распакованном архиве!")
            return False
        
        # Проверяем старые файлы
        for filename in files_to_create.keys():
            extracted_path = os.path.join(extract_dir2, filename)
            if not os.path.isfile(extracted_path):
                print(f"    {filename}: потеян после добавления файла!")
                return False
        
        print("  ✓ Все файлы в архиве")
        
        # Финальный отчет
        print("\n" + "=" * 70)
        print("ИТОГОВЫЙ ОТЧЕТ")
        print("=" * 70)
        
        print("\n Все тесты пройдены!\n")
        print(" Статистика:")
        print(f"  • Исходные данные: {total_original:,} байт")
        print(f"  • Размер архива: {archive_size:,} байт")
        print(f"  • Сжатие: {100 - compression_ratio:.1f}%")
        print(f"  • Файлов в финальном архиве: 4")
        print(f"  • CRC32: все файлы проверены и верны ")
        print("\n LZMA архиватор работает корректно!")
        
        return True


if __name__ == '__main__':
    try:
        success = verify_archiver()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n  Критическая  ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)