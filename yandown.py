import argparse
import requests
import urllib.parse
import os
import sys
import locale
import re
from tqdm import tqdm

API_BASE = "https://cloud-api.yandex.net/v1/disk/public/resources"

class Localization:
    def __init__(self):
        self.set_locale()

    def set_locale(self):
        self.current_locale = locale.getdefaultlocale()[0]

    def is_ru_locale(self):
        return self.current_locale == 'ru_RU'

    def get_message(self, message_key):
        messages = {
            'safe_name_warning': {
                'en': "Warning: The file name {name} contains unsupported characters or is invalid. Using safe name: {safe_name}",
                'ru': "Warning: Имя файла {name} содержит неподдерживаемые символы или является недопустимым. Используется безопасное имя: {safe_name}"
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
                'ru': "Error: URL для загрузки не найден в ответе для {link}"
            },
            'file_not_found': {
                'en': "Error: No downloadable file found with the name {original_file_name} in the provided link: {link}",
                'ru': "Error: Не найден файл с именем {original_file_name} в предоставленной ссылке: {link}"
            },
            'download_complete': {
                'en': "Download complete.",
                'ru': "Загрузка завершена."
            },
            'provide_link_or_file': {
                'en': "Error: You must provide either a link or a file containing links.",
                'ru': "Ошибка: Вы должны указать либо ссылку, либо файл со ссылками."
            },
            'resource_fetch_error': {
                'en': "Error: Unable to fetch resource details for {link}. Status code: {status_code}",
                'ru': "Error: Не удалось получить данные ресурса для {link}. Код состояния: {status_code}"
            },
            'downloading_folder': {
                'en': "Downloading folder: {name} ({count} files)",
                'ru': "Скачивание папки: {name} ({count} файлов)"
            },
            'folder_complete': {
                'en': "Folder download complete: {name}",
                'ru': "Загрузка папки завершена: {name}"
            },
            'arg_help': {
                'en': {
                    'positional_link': 'Link for Yandex Disk URL (optional if -l is used)',
                    'link': 'Link for Yandex Disk URL',
                    'download_location': 'Download location on your PC',
                    'file': 'Path to file with Yandex Disk URLs'
                },
                'ru': {
                    'positional_link': 'Ссылка на Яндекс.Диск (опционально, если используется -l)',
                    'link': 'Ссылка на Яндекс.Диск',
                    'download_location': 'Место сохранения на вашем ПК',
                    'file': 'Путь к файлу со ссылками на Яндекс.Диск'
                }
            }
        }

        language = 'ru' if self.is_ru_locale() else 'en'
        return messages[message_key][language]

class YandexDiskDownloader:
    def __init__(self, link, download_location, custom_name=None):
        self.link = link
        self.download_location = os.path.expanduser(download_location)
        self.custom_name = custom_name
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
            current_locale = locale.getdefaultlocale()
            if 'UTF-8' not in current_locale[1]:
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

    def download(self):
        self.set_locale()

        public_key, subpath = self._parse_link()

        # Get resource info to determine type (file or dir)
        response = self._get_resource_info(public_key, path=subpath)

        if response.status_code != 200:
            # Fallback: try the full link as public_key directly (for simple /i/ links)
            response = self._get_resource_info(self.link)
            if response.status_code != 200:
                print(self.localization.get_message('resource_fetch_error').format(
                    link=self.link, status_code=response.status_code))
                return
            public_key = self.link
            subpath = None

        resource = response.json()
        resource_type = resource.get('type')

        if resource_type == 'dir':
            folder_name = self.custom_name or resource.get('name', 'download')
            save_dir = os.path.join(self.download_location, folder_name)
            total = resource.get('_embedded', {}).get('total', 0)
            print(self.localization.get_message('downloading_folder').format(name=folder_name, count=total))
            self._download_folder(public_key, subpath, save_dir)
            print(self.localization.get_message('folder_complete').format(name=folder_name))
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
                    return

            original_file_name = urllib.parse.unquote(download_url.split("filename=")[1].split("&")[0])
            file_extension = os.path.splitext(original_file_name)[1]
            file_name = self.custom_name + file_extension if self.custom_name else original_file_name
            safe_name = self.safe_file_name(file_name)
            save_path = os.path.join(self.download_location, safe_name)

            os.makedirs(self.download_location, exist_ok=True)
            self._download_file(download_url, save_path)
            print(self.localization.get_message('download_complete'))

def download_from_file(file_path, download_location):
    with open(file_path, 'r') as file:
        lines = file.readlines()

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
            downloader = YandexDiskDownloader(link, download_location, custom_name)
            downloader.download()

if __name__ == "__main__":
    localization = Localization()

    parser = argparse.ArgumentParser(description='Yandex Disk Downloader')
    parser.add_argument('positional_link', nargs='?', help=localization.get_message('arg_help')['positional_link'])
    parser.add_argument('-l', '--link', type=str, help=localization.get_message('arg_help')['link'])
    parser.add_argument('-d', '--download_location', type=str, help=localization.get_message('arg_help')['download_location'], default=os.getcwd())
    parser.add_argument('-f', '--file', type=str, help=localization.get_message('arg_help')['file'])

    args = parser.parse_args()

    link = args.link or args.positional_link

    if args.file:
        download_from_file(args.file, args.download_location)
    elif link:
        downloader = YandexDiskDownloader(link, args.download_location)
        downloader.download()
    else:
        print(localization.get_message('provide_link_or_file'))
