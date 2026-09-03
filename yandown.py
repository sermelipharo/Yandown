#!/usr/bin/env python3
import argparse
import requests
import urllib.parse
import os
import sys
import json
import locale
import re
from tqdm import tqdm

API_BASE = "https://cloud-api.yandex.net/v1/disk/public/resources"
DEFAULT_WEB_BASE = "https://disk.yandex.ru"
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# Yandex Disk is served from a lot of regional domains (disk.yandex.ru/.com/.by/.kz/
# .com.tr/...), from disk.360.yandex.* and from the old yadi.sk shortener.
YANDEX_HOST_RE = re.compile(r'(^|\.)(yandex\.[a-z.]{2,6}|yadi\.sk)$', re.I)
# The web client prefixes a public hash with its resource type: d_<hash>, i_<hash>, a_<hash>.
CLIENT_ID_RE = re.compile(r'^([a-z])_(.+)$')


def base_url(link):
    """Return scheme://host of a link, or the default web host if it has none."""
    parsed = urllib.parse.urlparse(link)
    if parsed.scheme and parsed.netloc:
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, '', '', '', ''))
    return DEFAULT_WEB_BASE


def error_text(error):
    """Readable one-line description of an exception, without a traceback."""
    if isinstance(error, OSError) and error.strerror:
        return f"{error.strerror}: {error.filename}" if error.filename else error.strerror
    return str(error) or type(error).__name__


def looks_like_link(value):
    """Tell a Yandex Disk link apart from a filesystem path, so that a trailing
    command line argument can be taken as the download location."""
    if re.match(r'^[a-z][a-z0-9+.-]*://', value, re.I):
        return True
    return bool(YANDEX_HOST_RE.search(value.split('/')[0].split('?')[0]))


def normalize_link(link):
    """Bring a Yandex Disk link to the canonical public form.

    Handles web-client links (https://disk.yandex.ru/client/aa/d_<hash>/ ->
    https://disk.yandex.ru/d/<hash>), the old /public/?hash=<key> form, and strips
    query strings, fragments and the trailing slash — the public API answers 404
    for a public_key that ends with a slash. Links from any regional domain are
    kept on their own domain; non-Yandex links are returned untouched.
    """
    link = link.strip()
    if '://' not in link:
        link = 'https://' + link

    parsed = urllib.parse.urlparse(link)
    if not YANDEX_HOST_RE.search(parsed.hostname or ''):
        return link

    parts = [part for part in parsed.path.split('/') if part]

    # /public/?hash=<public key> — the key itself is the query parameter
    if parts[:1] == ['public']:
        hash_param = urllib.parse.parse_qs(parsed.query).get('hash')
        if hash_param:
            return hash_param[0]

    # /client/aa/d_<hash>/<optional/sub/path> -> /d/<hash>/<optional/sub/path>
    if parts[:1] == ['client']:
        for index, part in enumerate(parts):
            match = CLIENT_ID_RE.match(part)
            if match:
                parts = [match.group(1), match.group(2)] + parts[index + 1:]
                break
        else:
            # e.g. /client/disk/... — a personal link, there is no public key to extract
            return link

    return urllib.parse.urlunparse(
        parsed._replace(path='/' + '/'.join(parts), params='', query='', fragment=''))

class Localization:
    def __init__(self):
        self.set_locale()

    def set_locale(self):
        try:
            self.current_locale = locale.getlocale()[0]
        except ValueError:
            self.current_locale = None

    def is_ru_locale(self):
        return self.current_locale == 'ru_RU'

    def get_message(self, message_key):
        messages = {
            'safe_name_warning': {
                'en': "Warning: The file name {name} contains unsupported characters or is invalid. Using safe name: {safe_name}",
                'ru': "Предупреждение: Имя файла {name} содержит неподдерживаемые символы или является недопустимым. Используется безопасное имя: {safe_name}"
            },
            'locale_not_utf8': {
                'en': "Current locale does not support UTF-8. Setting locale to en_US.UTF-8.",
                'ru': "Текущая локаль не поддерживает UTF-8. Устанавливаю локаль en_US.UTF-8."
            },
            'locale_set_error': {
                'en': "Unable to set locale to en_US.UTF-8. Ensure that the required locale is installed on your system.",
                'ru': "Не удалось установить локаль en_US.UTF-8. Убедитесь, что требуемая локаль установлена в вашей системе."
            },
            'download_url_not_found': {
                'en': "Error: Download URL not found in the response for {link}",
                'ru': "Ошибка: URL для загрузки не найден в ответе для {link}"
            },
            'network_error': {
                'en': "Error: Network problem while downloading {link}: {error}",
                'ru': "Ошибка: Проблема с сетью при загрузке {link}: {error}"
            },
            'write_error': {
                'en': "Error: Unable to save files for {link}: {error}",
                'ru': "Ошибка: Не удалось сохранить файлы для {link}: {error}"
            },
            'unexpected_response': {
                'en': "Error: Unexpected response from Yandex Disk for {link}: {error}",
                'ru': "Ошибка: Неожиданный ответ Яндекс.Диска для {link}: {error}"
            },
            'location_error': {
                'en': "Error: Unable to create the download folder {location}: {error}",
                'ru': "Ошибка: Не удалось создать папку для загрузки {location}: {error}"
            },
            'file_read_error': {
                'en': "Error: Unable to read the list of links from {file_path}: {error}",
                'ru': "Ошибка: Не удалось прочитать список ссылок из {file_path}: {error}"
            },
            'interrupted': {
                'en': "Interrupted.",
                'ru': "Прервано."
            },
            'file_not_found': {
                'en': "Error: No downloadable file found with the name {original_file_name} in the provided link: {link}",
                'ru': "Ошибка: Не найден файл с именем {original_file_name} в предоставленной ссылке: {link}"
            },
            'download_complete': {
                'en': "Download complete.",
                'ru': "Загрузка завершена."
            },
            'provide_link_or_file': {
                'en': "Error: You must provide either a link or a file containing links.",
                'ru': "Ошибка: Вы должны указать либо ссылку, либо файл со ссылками."
            },
            'album_fetch_error': {
                'en': "Error: Unable to fetch album data for {link} (albums are not available through the public API, and the web fallback failed — possibly a captcha). Ask the owner to share the content as a folder (/d/ link) or download the album from the browser.",
                'ru': "Ошибка: Не удалось получить данные альбома для {link} (альбомы недоступны через публичный API, а обходной путь через веб не сработал — возможно, капча). Попросите владельца поделиться содержимым как папкой (ссылка вида /d/) или скачайте альбом через браузер."
            },
            'downloading_album': {
                'en': "Downloading album: {name} ({count} files)",
                'ru': "Скачивание альбома: {name} ({count} файлов)"
            },
            'album_complete': {
                'en': "Album download complete: {name}",
                'ru': "Загрузка альбома завершена: {name}"
            },
            'album_item_url_error': {
                'en': "Warning: Unable to get download URL for {name}, skipping.",
                'ru': "Предупреждение: Не удалось получить ссылку для скачивания {name}, пропускаю."
            },
            'client_link_not_public': {
                'en': "Error: {link} is a personal web-client link, it carries no public key. Open the file or folder in the browser, share it and use the resulting /d/, /i/ or /a/ link.",
                'ru': "Ошибка: {link} — ссылка личного веб-клиента, в ней нет публичного ключа. Откройте файл или папку в браузере, поделитесь ими и используйте полученную ссылку вида /d/, /i/ или /a/."
            },
            'resource_fetch_error': {
                'en': "Error: Unable to fetch resource details for {link}. Status code: {status_code}",
                'ru': "Ошибка: Не удалось получить данные ресурса для {link}. Код состояния: {status_code}"
            },
            'downloading_folder': {
                'en': "Downloading folder: {name} ({contents})",
                'ru': "Скачивание папки: {name} ({contents})"
            },
            'folder_files': {
                'en': "{count} files",
                'ru': "{count} файлов"
            },
            'folder_dirs': {
                'en': "{count} subfolders",
                'ru': "{count} подпапок"
            },
            'folder_empty': {
                'en': "empty",
                'ru': "пусто"
            },
            'folder_complete': {
                'en': "Folder download complete: {name}",
                'ru': "Загрузка папки завершена: {name}"
            },
            'arg_help': {
                'en': {
                    'positional_link': 'One or more Yandex Disk URLs, optionally followed by the download location',
                    'link': 'Yandex Disk URL (can be repeated)',
                    'download_location': 'Download location on your PC',
                    'file': 'Path to file with Yandex Disk URLs'
                },
                'ru': {
                    'positional_link': 'Одна или несколько ссылок на Яндекс.Диск, последним аргументом можно указать папку для сохранения',
                    'link': 'Ссылка на Яндекс.Диск (можно указать несколько раз)',
                    'download_location': 'Место сохранения на вашем ПК',
                    'file': 'Путь к файлу со ссылками на Яндекс.Диск'
                }
            }
        }

        language = 'ru' if self.is_ru_locale() else 'en'
        return messages[message_key][language]

class YandexDiskDownloader:
    def __init__(self, link, download_location, custom_name=None, flatten=False):
        self.link = normalize_link(link)
        self.download_location = os.path.expanduser(download_location)
        self.custom_name = custom_name
        # When a single resource is downloaded into a directory that is already named
        # after it, save into that directory instead of creating builds/builds.
        self.flatten = flatten
        self.web_base = base_url(self.link)
        self.localization = Localization()

    def _parse_link(self):
        """Parse link into base public key and optional subpath."""
        parsed = urllib.parse.urlparse(self.link)
        path_parts = parsed.path.strip('/').split('/')
        # Format: /d/<hash>/optional/sub/path or /i/<hash>/...
        if len(path_parts) >= 2:
            base_path = '/' + '/'.join(path_parts[:2])
            base_url = urllib.parse.urlunparse(parsed._replace(path=base_path))
            sub_parts = path_parts[2:]
            if sub_parts:
                subpath = '/' + '/'.join(urllib.parse.unquote(p) for p in sub_parts)
                return base_url, subpath
            return base_url, None
        return self.link, None

    def safe_file_name(self, name):
        safe_name = re.sub(r'[\/:*?"<>|]', '_', name)

        try:
            with open(os.path.join(self.download_location, safe_name), 'w') as test_file:
                pass
            os.remove(os.path.join(self.download_location, safe_name))
        except OSError:
            print(self.localization.get_message('safe_name_warning').format(name=name, safe_name=safe_name))
            return safe_name
        return name

    def set_locale(self):
        try:
            encoding = locale.getencoding()
            if 'UTF-8' not in encoding:
                print(self.localization.get_message('locale_not_utf8'))
                locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
        except locale.Error:
            print(self.localization.get_message('locale_set_error'))
            sys.exit(1)

    def _get_resource_info(self, public_key, path=None, limit=100, offset=0):
        """Get resource metadata from Yandex API."""
        params = {"public_key": public_key, "limit": limit, "offset": offset}
        if path:
            params["path"] = path
        return requests.get(API_BASE, params=params)

    def _get_download_url(self, public_key, path=None):
        """Get direct download URL for a file."""
        params = {"public_key": public_key}
        if path:
            params["path"] = path
        response = requests.get(API_BASE + "/download", params=params)
        if response.status_code == 200:
            return response.json().get("href")
        return None

    def _collect_all_items(self, public_key, path=None):
        """Collect all items from a folder with pagination."""
        items = []
        offset = 0
        limit = 100
        while True:
            response = self._get_resource_info(public_key, path=path, limit=limit, offset=offset)
            if response.status_code != 200:
                print(self.localization.get_message('resource_fetch_error').format(
                    link=self.link, status_code=response.status_code))
                return None
            data = response.json()
            batch = data.get('_embedded', {}).get('items', [])
            if not batch:
                break
            items.extend(batch)
            offset += limit
        return items

    def _download_file(self, download_url, save_path):
        """Download a single file with progress bar."""
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        download_response = requests.get(download_url, stream=True)
        total_size = int(download_response.headers.get('content-length', 0))
        desc = os.path.basename(save_path)

        with open(save_path, "wb") as file, tqdm(
            total=total_size or None, unit='B', unit_scale=True,
            desc=desc, dynamic_ncols=True, miniters=1
        ) as pbar:
            for chunk in download_response.iter_content(chunk_size=1024):
                if chunk:
                    file.write(chunk)
                    file.flush()
                    pbar.update(len(chunk))

    def _download_folder(self, public_key, path, save_dir):
        """Recursively download all files from a folder."""
        items = self._collect_all_items(public_key, path=path)
        if items is None:
            return

        for item in items:
            item_name = self.safe_file_name(item['name'])
            item_path = item['path']  # API returns the path relative to the public root

            if item['type'] == 'file':
                download_url = item.get('file')
                if not download_url:
                    download_url = self._get_download_url(public_key, path=item_path)
                if download_url:
                    save_path = os.path.join(save_dir, item_name)
                    self._download_file(download_url, save_path)
            elif item['type'] == 'dir':
                sub_dir = os.path.join(save_dir, item_name)
                self._download_folder(public_key, item_path, sub_dir)

    def _describe_contents(self, items):
        """Files and subfolders in the root of a folder, counted separately."""
        counts = [
            ('folder_files', sum(1 for item in items if item.get('type') == 'file')),
            ('folder_dirs', sum(1 for item in items if item.get('type') == 'dir')),
        ]
        parts = [self.localization.get_message(key).format(count=count)
                 for key, count in counts if count]
        return ', '.join(parts) or self.localization.get_message('folder_empty')

    def _target_dir(self, name):
        """Directory the contents of a folder or album go into."""
        if self.flatten and os.path.basename(os.path.normpath(self.download_location)) == name:
            return self.download_location
        return os.path.join(self.download_location, self.safe_file_name(name))

    def _fetch_album_state(self, session):
        """Load the album web page and extract the embedded store-prefetch JSON.

        Albums (/a/ links) are not exposed through the public API, so the only
        way in is the same internal API the web client uses: the page embeds the
        first portion of items plus an sk token for further requests.
        """
        response = session.get(self.link)
        if response.status_code != 200:
            return None
        # A link can redirect between domains (yadi.sk -> disk.yandex.ru, regional
        # mirrors), and the sk token is only valid on the host that served the page.
        self.web_base = base_url(response.url)
        session.headers['Origin'] = self.web_base
        match = re.search(r'<script[^>]*id="store-prefetch"[^>]*>(.*?)</script>', response.text, re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None

    def _album_api(self, session, sk, model, payload):
        """Call an internal web API model (e.g. album-download-url)."""
        payload = dict(payload, sk=sk)
        response = session.post(
            self.web_base + "/public/api/" + model,
            data=json.dumps(payload),
            headers={"Content-Type": "text/plain"},
        )
        if response.status_code != 200:
            return None
        body = response.json()
        if body.get('error'):
            return None
        return body.get('data', body)

    def _download_album(self):
        """Return True when the album was fetched and its files were downloaded."""
        session = requests.Session()
        session.headers.update({
            'User-Agent': BROWSER_UA,
            'Origin': self.web_base,
            'Referer': self.link,
        })

        state = self._fetch_album_state(session)
        if not state:
            print(self.localization.get_message('album_fetch_error').format(link=self.link))
            return False

        sk = state['environment']['sk']
        resources = state['resources']
        album = resources[state['rootResourceId']]
        album_hash = album['hash']
        items = [resources[child] for child in album.get('children', []) if child in resources]

        # Paginate: fetch-album-list uses the last item's albumItemId as a cursor
        while not album.get('completed', True):
            data = self._album_api(session, sk, 'fetch-album-list', {
                'hash': album_hash,
                'lastItemId': items[-1]['albumItemId'] if items else None,
            })
            if data is None:
                print(self.localization.get_message('album_fetch_error').format(link=self.link))
                return False
            batch = data.get('resources', [])
            items.extend(batch)
            if data.get('completed', True) or not batch:
                break

        files = [item for item in items if item.get('type') == 'file']
        album_name = self.custom_name or album.get('name', 'album')
        save_dir = self._target_dir(album_name)
        print(self.localization.get_message('downloading_album').format(name=album_name, count=len(files)))

        for item in files:
            data = self._album_api(session, sk, 'album-download-url', {
                'hash': album_hash,
                'itemId': item['albumItemId'],
            })
            download_url = data.get('url') if data else None
            if not download_url:
                print(self.localization.get_message('album_item_url_error').format(name=item.get('name', '?')))
                continue
            save_path = os.path.join(save_dir, self.safe_file_name(item['name']))
            self._download_file(download_url, save_path)

        print(self.localization.get_message('album_complete').format(name=album_name))
        return True

    def download(self):
        """Return True when the link was downloaded, False when it was reported as failed."""
        self.set_locale()
        try:
            os.makedirs(self.download_location, exist_ok=True)
        except OSError as error:
            print(self.localization.get_message('location_error').format(
                location=self.download_location, error=error_text(error)))
            return

        parsed_path = urllib.parse.urlparse(self.link).path
        first_segment = parsed_path.strip('/').split('/')[0]

        if first_segment == 'client':
            print(self.localization.get_message('client_link_not_public').format(link=self.link))
            return False

        if first_segment == 'a':
            return self._download_album()

        public_key, subpath = self._parse_link()

        # Get resource info to determine type (file or dir)
        response = self._get_resource_info(public_key, path=subpath)

        if response.status_code != 200:
            # Fallback: try the full link as public_key directly (for simple /i/ links)
            response = self._get_resource_info(self.link)
            if response.status_code != 200:
                print(self.localization.get_message('resource_fetch_error').format(
                    link=self.link, status_code=response.status_code))
                return False
            public_key = self.link
            subpath = None

        resource = response.json()
        resource_type = resource.get('type')

        if resource_type == 'dir':
            folder_name = self.custom_name or resource.get('name', 'download')
            save_dir = self._target_dir(folder_name)
            embedded = resource.get('_embedded', {})
            root_items = embedded.get('items', [])
            if embedded.get('total', len(root_items)) > len(root_items):
                root_items = self._collect_all_items(public_key, path=subpath) or root_items
            print(self.localization.get_message('downloading_folder').format(
                name=folder_name, contents=self._describe_contents(root_items)))
            self._download_folder(public_key, subpath, save_dir)
            print(self.localization.get_message('folder_complete').format(name=folder_name))
            return True
        else:
            # Single file
            download_url = self._get_download_url(public_key, path=subpath)
            if not download_url:
                # Fallback: search in parent folder
                original_file_name = urllib.parse.unquote(self.link.split('/')[-1])
                higher_level_link = '/'.join(self.link.split('/')[:-1])
                items = self._collect_all_items(higher_level_link)
                if items:
                    for item in items:
                        if item['type'] == 'file' and item['name'] == original_file_name:
                            download_url = item['file']
                            break

                if not download_url:
                    print(self.localization.get_message('file_not_found').format(
                        original_file_name=original_file_name, link=self.link))
                    return False

            parsed_url = urllib.parse.urlparse(download_url)
            file_name_param = urllib.parse.parse_qs(parsed_url.query).get('filename')
            original_file_name = urllib.parse.unquote(
                file_name_param[0] if file_name_param else os.path.basename(parsed_url.path)) or 'download'
            file_extension = os.path.splitext(original_file_name)[1]
            file_name = self.custom_name + file_extension if self.custom_name else original_file_name
            safe_name = self.safe_file_name(file_name)
            save_path = os.path.join(self.download_location, safe_name)

            os.makedirs(self.download_location, exist_ok=True)
            self._download_file(download_url, save_path)
            print(self.localization.get_message('download_complete'))
            return True

def download_link(link, download_location, custom_name=None, flatten=False):
    """Download one link, reporting any failure instead of raising it."""
    localization = Localization()
    try:
        return YandexDiskDownloader(link, download_location, custom_name, flatten).download()
    except requests.RequestException as error:
        print(localization.get_message('network_error').format(link=link, error=error_text(error)))
    except OSError as error:
        print(localization.get_message('write_error').format(link=link, error=error_text(error)))
    except (KeyError, IndexError, ValueError) as error:
        print(localization.get_message('unexpected_response').format(link=link, error=error_text(error)))
    return False


def download_from_file(file_path, download_location):
    localization = Localization()
    try:
        with open(file_path, 'r') as file:
            lines = file.readlines()
    except OSError as error:
        print(localization.get_message('file_read_error').format(
            file_path=file_path, error=error_text(error)))
        return False

    succeeded = True
    for line in lines:
        line = line.strip()
        if line:
            if ' ' in line:
                link, custom_name = line.split(maxsplit=1)
            elif ',' in line:
                link, custom_name = line.split(',', maxsplit=1)
            elif ';' in line:
                link, custom_name = line.split(';', maxsplit=1)
            else:
                link, custom_name = line, None

            custom_name = custom_name.strip() if custom_name else None
            if not download_link(link, download_location, custom_name):
                succeeded = False
    return succeeded

if __name__ == "__main__":
    localization = Localization()

    parser = argparse.ArgumentParser(description='Yandex Disk Downloader')
    parser.add_argument('positional_links', nargs='*', help=localization.get_message('arg_help')['positional_link'])
    parser.add_argument('-l', '--link', dest='links', action='append', default=[], help=localization.get_message('arg_help')['link'])
    parser.add_argument('-d', '--download_location', type=str, help=localization.get_message('arg_help')['download_location'], default=None)
    parser.add_argument('-f', '--file', type=str, help=localization.get_message('arg_help')['file'])

    args = parser.parse_args()

    positional_links = list(args.positional_links)
    download_location = args.download_location

    # yandown <link> <link> ... [download location]: a trailing argument that is not
    # a link is the destination, as long as at least one link is left without it
    if (len(positional_links) > 1 or (positional_links and args.links)) \
            and not looks_like_link(positional_links[-1]):
        trailing_location = positional_links.pop()
        if download_location is None:
            download_location = trailing_location

    links = args.links + positional_links
    if download_location is None:
        download_location = os.getcwd()

    try:
        if args.file:
            succeeded = download_from_file(args.file, download_location)
        elif links:
            succeeded = True
            for link in links:
                if not download_link(link, download_location, flatten=len(links) == 1):
                    succeeded = False
        else:
            print(localization.get_message('provide_link_or_file'))
            succeeded = False
    except KeyboardInterrupt:
        print()
        print(localization.get_message('interrupted'))
        sys.exit(130)

    sys.exit(0 if succeeded else 1)
