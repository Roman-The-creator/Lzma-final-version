"""
Командная строка для архиватора.
"""

import argparse
import sys
from archiver import Archiver


def main():
    parser = argparse.ArgumentParser(
        description='LZ77 + Huffman Archiver',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py create -o archive.lzha file1.txt file2.txt
  python main.py extract archive.lzha -d ./output
  python main.py list archive.lzha
  python main.py add archive.lzha file3.txt
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    create_parser = subparsers.add_parser('create', help='Create archive')
    create_parser.add_argument('files', nargs='+', help='Files to archive')
    create_parser.add_argument('-o', '--output', required=True, help='Archive path')
    create_parser.add_argument('--no-huffman', action='store_true', help='Disable Huffman encoding')
    
    extract_parser = subparsers.add_parser('extract', help='Extract archive')
    extract_parser.add_argument('archive', help='Archive path')
    extract_parser.add_argument('-d', '--dir', default='.', help='Output directory')
    
    list_parser = subparsers.add_parser('list', help='List archive contents')
    list_parser.add_argument('archive', help='Archive path')
    
    add_parser = subparsers.add_parser('add', help='Add files to archive')
    add_parser.add_argument('archive', help='Archive path')
    add_parser.add_argument('files', nargs='+', help='Files to add')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    use_huffman = not getattr(args, 'no_huffman', False)
    archiver = Archiver(use_huffman=use_huffman)
    
    try:
        if args.command == 'create':
            archiver.create_archive(args.files, args.output)
        
        elif args.command == 'extract':
            archiver.extract_archive(args.archive, args.dir)
        
        elif args.command == 'list':
            archiver.list_archive(args.archive)
        
        elif args.command == 'add':
            archiver.add_files(args.archive, args.files)
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()