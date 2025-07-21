import os
import pystray
from PIL import Image

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
STATIC_DIR = os.path.join(BASE_DIR, 'static')


class AppTray:
    def __init__(self, window):
        self.window = window
        self.icon = None
        self.setup_tray()
        self.is_app_hidden = False

    def create_image(self):
        """Загружаем изображение из файла для иконки в трее."""

        dark_logo = os.getenv('DARK_LOGO', 'false').lower()
        if dark_logo in ['true', '1']:
            icon_path = os.path.join(STATIC_DIR, 'img', 'dark_icon.png')
        else:
            icon_path = os.path.join(STATIC_DIR, 'img', 'icon.png')

        try:
            image = Image.open(icon_path)
            return image
        except FileNotFoundError:
            print(f"Ошибка: Файл иконки '{icon_path}' не найден. Использую зеленый квадрат.")
            return Image.new('RGB', (64, 64), "green")
        except Exception as e:
            print(f"Ошибка при загрузке иконки из '{icon_path}': {e}. Использую зеленый квадрат.")
            return Image.new('RGB', (64, 64), "green")

    def on_quit(self, item):
        """Обработчик пункта меню 'Закрыть'"""
        if self.icon:
            self.icon.stop()
        self.window.destroy()

    def on_click(self, item):
        """Обработчик пункта меню 'Открыть' и действия по умолчанию"""
        if self.is_app_hidden:
            # self.window.restore()
            self.window.show()
            # self.window.maximize()
            self.is_app_hidden = False
        else:
            self.window.hide()
            self.is_app_hidden = True

    def on_hide(self, item):
        """Обработчик пункта меню 'Свернуть в трей'"""
        self.window.hide()
        self.is_app_hidden = True

    def setup_tray(self):
        """Настройка иконки в системном трее"""
        image = self.create_image()
        menu = pystray.Menu(
            pystray.MenuItem('Свернуть в трей / Развернуть', self.on_click, default=True),
            # pystray.MenuItem('Свернуть в трей', self.on_hide),
            pystray.MenuItem('Закрыть', self.on_quit)
        )

        self.icon = pystray.Icon("ESXi VM Manager", image, "ESXi VM Manager", menu)

        def setup_icon(icon):
            icon.visible = True

            hide_on_startup_env = os.getenv('HIDE_ON_STARTUP', 'false').lower()
            if hide_on_startup_env in ['true', '1']:
                self.window.hide()
                self.is_app_hidden = True
            else:
                self.is_app_hidden = False

        self.icon.run_detached(setup=setup_icon)

    def stop(self):
        """Остановка иконки в трее"""
        if self.icon:
            self.icon.stop()