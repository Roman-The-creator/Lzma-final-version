# скрипт для создания тестовых файлов

def create_test_files():
    print("Создание тестовых файлов...")
    
    with open('file1.txt', 'w', encoding='utf-8') as f:
        f.write("Hello, world!\n" * 100)
    
    with open('file2.txt', 'w', encoding='utf-8') as f:
        f.write("А давайте запретим кузнечиков с усиками длиннее трёх сантиметров», — депутат Делягин.\n" * 80)
    
    with open('file3.txt', 'w', encoding='utf-8') as f:
        f.write("TON выбрал глобальную платежную компанию  OpenPayd для обеспечения работы своих глобальных операций с фиатными валютами..\n" * 60)


if __name__ == '__main__':
    create_test_files()