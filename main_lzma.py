"""
CLI интерфейс для LZMA архиватора
"""

import argparse
import sys
from archiver_lzma import Archiver


def main():
    parser = argparse.ArgumentParser(
        description='LZMA архиватор - архивирование файлов с LZMA сжатием'
    )
    subparsers = parser.add_subparsers(dest='command', help='Команды')
    
    # Команда: create
    create_parser = subparsers.add_parser('create', help='Создать архив')
    create_parser.add_argument('-o', '--output', required=True, help='Выходной файл архива')
    create_parser.add_argument('-l', '--level', type=int, default=6, 
                              help='Уровень сжатия (0-9, default=6)')
    create_parser.add_argument('files', nargs='+', help='Файлы для архивирования')
    
    # Команда: extract
    extract_parser = subparsers.add_parser('extract', help='Распаковать архив')
    extract_parser.add_argument('archive', help='Архив для распаковки')
    extract_parser.add_argument('-d', '--directory', default='.', help='Выходная папка')
    
    # Команда: list
    list_parser = subparsers.add_parser('list', help='Показать содержимое архива')
    list_parser.add_argument('archive', help='Архив для просмотра')
    
    # Команда: add
    add_parser = subparsers.add_parser('add', help='Добавить файлы в архив')
    add_parser.add_argument('archive', help='Архив')
    add_parser.add_argument('files', nargs='+', help='Файлы для добавления')
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return
    
    try:
        archiver = Archiver(level=getattr(args, 'level', 6))
        
        if args.command == 'create':
            archiver.create_archive(args.files, args.output)
        
        elif args.command == 'extract':
            archiver.extract_archive(args.archive, args.directory)
        
        elif args.command == 'list':
            archiver.list_archive(args.archive)
        
        elif args.command == 'add':
            archiver.add_files(args.archive, args.files)
    
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()