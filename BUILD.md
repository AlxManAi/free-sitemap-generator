# Инструкция по сборке десктопного приложения

## Требования

- Python 3.8 или выше
- Все зависимости из `requirements.txt` установлены
- PyInstaller (установится автоматически при запуске `setup.py`)

## Быстрая сборка (Windows)

Просто запустите:
```bash
build.bat
```

Или вручную:
```bash
python setup.py
```

## Ручная сборка

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
pip install pyinstaller
```

### 2. Сборка приложения

```bash
python setup.py
```

### 3. Результат

После успешной сборки исполняемый файл будет находиться в папке `dist/`:
- Windows: `dist/ALXSitemapGenerator.exe`
- Linux/Mac: `dist/ALXSitemapGenerator`

## Настройки сборки

Основные настройки находятся в `setup.py`:
- `APP_NAME` - имя исполняемого файла
- `VERSION` - версия приложения
- Опции PyInstaller настраиваются в функции `build_executable()`

## Что включается в сборку

- ✅ Основной модуль `main.py`
- ✅ Модули `sitemap_generator.py` и `url_normalizer.py`
- ✅ Темная тема `dark_theme.qss`
- ✅ Иконка приложения `assets/icon/app.ico`
- ✅ Все зависимости PyQt6, requests, beautifulsoup4, lxml

## Размер файла

Ожидаемый размер exe файла: **50-80 MB** (включает Python runtime и все зависимости)

## Устранение проблем

### Ошибка "PyInstaller not found"
```bash
pip install --upgrade pyinstaller
```

### Ошибка "Module not found"
Убедитесь, что все зависимости установлены:
```bash
pip install -r requirements.txt
```

### Иконка не отображается
Проверьте, что файл `assets/icon/app.ico` существует. Если нет:
```bash
python create_icon.py
```

### Файл слишком большой
Используйте опцию `--onedir` вместо `--onefile` для создания папки вместо одного файла (измените в `setup.py`)

## Тестирование сборки

После сборки протестируйте exe файл:
1. Запустите `dist/ALXSitemapGenerator.exe`
2. Проверьте, что интерфейс отображается корректно
3. Попробуйте выполнить сканирование тестового сайта
4. Проверьте экспорт sitemap.xml и списка URL

## Распространение

Для распространения приложения просто скопируйте `ALXSitemapGenerator.exe` на целевой компьютер. Дополнительные файлы не требуются - всё включено в exe.

