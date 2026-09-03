# Yandex Disk Downloader

[![Yandex Disk](https://img.shields.io/badge/Я.Диск-Unofficial-red.svg?logo=data:image/svg+xml;base64,PHN2ZyB3aWR0aD0nNDQnIGhlaWdodD0nNDQnIGZpbGw9J25vbmUnIHhtbG5zPSdodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2Zyc+PHBhdGggZD0nTTIyIDQzYTIxIDIxIDAgMSAwIDAtNDIgMjEgMjEgMCAwIDAgMCA0MlonIGZpbGw9JyNGODYwNEEnLz48cGF0aCBkPSdNMjUuMyAzNS4xM2g0LjU3VjguODZoLTYuNjZjLTYuNyAwLTEwLjIyIDMuNDQtMTAuMjIgOC41IDAgNC4wMiAxLjkzIDYuNDMgNS4zNyA4Ljg4bC01Ljk5IDguODhoNC45N0wyNCAyNS4xOGwtMi4zMi0xLjU0Yy0yLjgtMS45LTQuMTctMy4zNi00LjE3LTYuNTQgMC0yLjc5IDEuOTctNC42OCA1LjcyLTQuNjhoMi4wNXYyMi43aC4wMVonIGZpbGw9JyNmZmYnLz48L3N2Zz4=)](#) [![Static Badge](https://img.shields.io/badge/python3-grey?style=flat&logo=python&logoColor=white)](#) [![en](https://img.shields.io/badge/lang-en-FF8002.svg)](#english) [![ru](https://img.shields.io/badge/lang-ru-00E153.svg)](#русский)

## English

This script allows downloading files, folders and albums from Yandex Disk using public links. It takes one or several links at once, or a text file containing a list of links and file names. When a folder link is provided, all files are downloaded recursively, preserving the directory structure.

### Supported links

Any regional Yandex Disk domain works — `disk.yandex.ru`, `.com`, `.by`, `.kz`, `.uz`, `.com.tr` and the rest, plus `disk.360.yandex.*` and the old `yadi.sk` shortener.

| Link | Meaning |
|---|---|
| `https://disk.yandex.ru/i/<hash>` | a single public file |
| `https://disk.yandex.ru/d/<hash>` | a public folder (downloaded recursively) |
| `https://disk.yandex.ru/d/<hash>/Sub%20Folder/file.jpg` | a file or subfolder inside a public folder |
| `https://disk.yandex.ru/a/<hash>` | a public album |
| `https://disk.yandex.ru/client/aa/d_<hash>/` | web-client link — rewritten to `/d/<hash>` automatically (same for `i_` and `a_`) |
| `https://disk.yandex.ru/public/?hash=<key>` | the old public-key form |

Trailing slashes and query strings (`?utm_source=...`) are stripped, since the public API rejects them.

Personal web-client links such as `https://disk.yandex.ru/client/disk/Documents` carry no public key and cannot be downloaded: share the file or folder first and use the resulting link.

### Requirements

- Python 3.x
- Libraries: `requests tqdm`

### Installation

1. Clone the repository or download the script.
2. Install the required libraries:
    ```bash
    pip install requests tqdm
    ```

### Usage

#### Download a single file or folder

To download a single file or an entire folder from Yandex Disk, use the following command:

```bash
python yandown.py -l <link> -d <download_location>
```

Or simply:

```bash
python yandown.py <link>
```

#### Download several links at once

```bash
python yandown.py <link> <link> <link>
```

The last argument is used as the download location when it is not a link, so `-d` is optional:

```bash
python yandown.py <link> <link> ~/Downloads/materials
```

The download folder is created if it does not exist. When a single link is given and the destination folder is already named after the folder behind the link, its contents are saved straight into it instead of nesting `builds/builds`.

#### Download from a file

To download files from a list contained in a text file, use the following command:

```bash
python yandown.py -f <file_path> -d <download_location>
```

The format of the text file should be as follows: one link per line, followed by the file name, separated by a space, comma, or semicolon.

Example `links.txt` file:
```
https://disk.yandex.ru/i/example1 Square
https://disk.yandex.ru/i/example2, Circle
https://disk.yandex.ru/i/example3; Triangle
https://disk.yandex.ru/d/example4
https://disk.yandex.ru/d/example_folder/file.jpg CustomFileName
```

### Command line arguments

- `<links>`: One or more Yandex Disk links, optionally followed by the download location.
- `-l, --link`: A Yandex Disk link, can be repeated.
- `-f, --file`: Path to a text file with Yandex Disk links.
- `-d, --download_location`: Path to save the downloaded files (optional, default is the current directory; takes precedence over a trailing path).

### Examples

#### Download a single file

```bash
python yandown.py -l "https://disk.yandex.ru/i/example1" -d "/path/to/save"
```

#### Download from a file

```bash
python yandown.py -f "/path/to/links.txt" -d "/path/to/save"
```

#### Download a single file to the current directory

```bash
python yandown.py "https://disk.yandex.ru/i/example1"
```

#### Download several links into one folder

```bash
python yandown.py "https://disk.yandex.ru/d/example1" "https://disk.yandex.ru/d/example2" "/path/to/save"
```

#### Download a folder

```bash
python yandown.py "https://disk.yandex.ru/d/example_hash/Folder%20Name" -d "/path/to/save"
```

All files from the folder (including subfolders) will be downloaded with the directory structure preserved.

#### Download an album

```bash
python yandown.py "https://disk.yandex.ru/a/example_hash" -d "/path/to/save"
```

Album links (`/a/`) are not exposed through the public Yandex Disk API, so the script uses the same internal web API as the browser client. All album files are downloaded into a folder named after the album. Note: since this API is unofficial, Yandex may change it without notice.

---

## Русский

Этот скрипт позволяет загружать файлы, папки и альбомы с Яндекс.Диска по публичным ссылкам. Скрипт принимает одну или несколько ссылок сразу, а также текстовый файл со списком ссылок и названий файлов. При указании ссылки на папку все файлы скачиваются рекурсивно с сохранением структуры директорий.

### Поддерживаемые ссылки

Работает любой региональный домен Яндекс.Диска — `disk.yandex.ru`, `.com`, `.by`, `.kz`, `.uz`, `.com.tr` и остальные, а также `disk.360.yandex.*` и старый сокращатель `yadi.sk`.

| Ссылка | Что это |
|---|---|
| `https://disk.yandex.ru/i/<hash>` | один публичный файл |
| `https://disk.yandex.ru/d/<hash>` | публичная папка (скачивается рекурсивно) |
| `https://disk.yandex.ru/d/<hash>/Папка/file.jpg` | файл или подпапка внутри публичной папки |
| `https://disk.yandex.ru/a/<hash>` | публичный альбом |
| `https://disk.yandex.ru/client/aa/d_<hash>/` | ссылка веб-клиента — автоматически превращается в `/d/<hash>` (то же для `i_` и `a_`) |
| `https://disk.yandex.ru/public/?hash=<key>` | старый формат с публичным ключом |

Завершающий слэш и query-параметры (`?utm_source=...`) отбрасываются: публичный API их не принимает.

Личные ссылки веб-клиента вида `https://disk.yandex.ru/client/disk/Documents` не содержат публичного ключа, и скачать по ним ничего нельзя: сначала поделитесь файлом или папкой и используйте полученную ссылку.

### Требования

- Python 3.x
- Библиотеки: `requests tqdm`

### Установка

1. Склонируйте репозиторий или скачайте скрипт.
2. Установите необходимые библиотеки:
    ```bash
    pip install requests tqdm
    ```

### Использование

#### Загрузка одного файла или папки

Для загрузки одного файла или целой папки с Яндекс.Диска используйте следующую команду:

```bash
python yandown.py -l <ссылка> -d <путь_для_сохранения>
```

Или просто:

```bash
python yandown.py <ссылка>
```

#### Загрузка нескольких ссылок сразу

```bash
python yandown.py <ссылка> <ссылка> <ссылка>
```

Последний аргумент считается папкой для сохранения, если он не похож на ссылку, — тогда `-d` не нужен:

```bash
python yandown.py <ссылка> <ссылка> ~/Downloads/материалы
```

Папка создаётся, если её нет. Если ссылка одна и папка назначения уже названа так же, как папка по ссылке, содержимое кладётся прямо в неё, без вложения вида `builds/builds`.

#### Загрузка из файла

Для загрузки файлов из списка, содержащегося в текстовом файле, используйте следующую команду:

```bash
python yandown.py -f <путь_к_файлу> -d <путь_для_сохранения>
```

Формат текстового файла должен быть следующим: одна ссылка на строку, за которой может следовать название файла, разделенное пробелом, запятой или точкой с запятой.

Пример файла `links.txt`:
```
https://disk.yandex.ru/i/example1 Квадратик
https://disk.yandex.ru/i/example2, Шарик
https://disk.yandex.ru/i/example3; Треугольник
https://disk.yandex.ru/d/example4
https://disk.yandex.ru/d/example_folder/file.jpg НазваниеФайла
```

### Аргументы командной строки

- `<ссылки>`: Одна или несколько ссылок на Яндекс.Диск, последним аргументом можно указать папку для сохранения.
- `-l, --link`: Ссылка на Яндекс.Диск, можно указать несколько раз.
- `-f, --file`: Путь к текстовому файлу с ссылками на файлы Яндекс.Диска.
- `-d, --download_location`: Путь для сохранения загруженных файлов (необязательно, по умолчанию текущая директория; имеет приоритет над путём в конце команды).

### Примеры

#### Загрузка одного файла

```bash
python yandown.py -l "https://disk.yandex.ru/i/example1" -d "/path/to/save"
```

#### Загрузка из файла

```bash
python yandown.py -f "/path/to/links.txt" -d "/path/to/save"
```

#### Загрузка одного файла в текущую папку

```bash
python yandown.py "https://disk.yandex.ru/i/example1"
```

#### Загрузка нескольких ссылок в одну папку

```bash
python yandown.py "https://disk.yandex.ru/d/example1" "https://disk.yandex.ru/d/example2" "/path/to/save"
```

#### Загрузка папки

```bash
python yandown.py "https://disk.yandex.ru/d/example_hash/Название%20Папки" -d "/path/to/save"
```

Все файлы из папки (включая вложенные подпапки) будут загружены с сохранением структуры директорий.

#### Загрузка альбома

```bash
python yandown.py "https://disk.yandex.ru/a/example_hash" -d "/path/to/save"
```

Ссылки на альбомы (`/a/`) недоступны через публичный API Яндекс.Диска, поэтому скрипт использует тот же внутренний веб-API, что и браузерный клиент. Все файлы альбома скачиваются в папку с названием альбома. Примечание: так как этот API неофициальный, Яндекс может изменить его без предупреждения.
