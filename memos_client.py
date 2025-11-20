import sys
import os
import json
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel, QMessageBox, QComboBox,
    QSystemTrayIcon, QMenu, QCheckBox
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QUrl, QTimer
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage


CONFIG_DIR = Path.home() / ".memos-client"
CONFIG_FILE = CONFIG_DIR / "config.json"


def save_config(url=None, window_geo=None, close_to_tray=False):
    CONFIG_DIR.mkdir(exist_ok=True)
    data = {
        "memos_url": url,
        "close_to_tray": close_to_tray
    }
    if window_geo is not None:
        if isinstance(window_geo, dict):
            data["window"] = window_geo
        else:
            data["window"] = {
                "x": window_geo.x(),
                "y": window_geo.y(),
                "width": window_geo.width(),
                "height": window_geo.height()
            }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_config():
    default_config = {
        "memos_url": None,
        "window": None,
        "close_to_tray": False
    }
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_config.update(data)
        except:
            pass
    return default_config


class LauncherWindow(QWidget):
    def __init__(self, on_connect):
        super().__init__()
        self.on_connect = on_connect
        self.setWindowTitle("连接到 Memos")
        self.resize(326, 200)
        self.setStyleSheet("font-size: 13px;")
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addWidget(QLabel("Memos 地址："))

        url_layout = QHBoxLayout()
        url_layout.setSpacing(6)
        self.proto_combo = QComboBox()
        self.proto_combo.addItems(["http://", "https://"])
        self.proto_combo.setFixedWidth(80)
        url_layout.addWidget(self.proto_combo)

        self.host_input = QLineEdit()
        self.host_input.setFixedWidth(200)
        self.host_input.setPlaceholderText("192.168.1.100:5230")
        self.host_input.returnPressed.connect(self.handle_connect)
        url_layout.addWidget(self.host_input)
        url_layout.addStretch()
        layout.addLayout(url_layout)

        self.connect_btn = QPushButton("连接")
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background: #4f46e5;
                color: white;
                border: none;
                padding: 6px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #4338ca;
            }
        """)
        self.connect_btn.setFixedWidth(286)
        self.connect_btn.clicked.connect(self.handle_connect)
        layout.addWidget(self.connect_btn)

        tip_label = QLabel(
            "如需重设地址，请删除配置文件：<br>"
            f"<code>{CONFIG_FILE}</code>"
        )
        tip_label.setStyleSheet("font-size: 10px; color: gray;")
        tip_label.setWordWrap(True)
        tip_label.setMaximumWidth(286)
        layout.addWidget(tip_label)

        self.setLayout(layout)

    def handle_connect(self):
        proto = self.proto_combo.currentText()
        host = self.host_input.text().strip()
        if not host:
            QMessageBox.warning(self, "提示", "请输入地址（如：192.168.1.100:5230）")
            return
        url = f"{proto}{host}"
        config = load_config()
        save_config(url=url, close_to_tray=config["close_to_tray"])
        self.on_connect(url)
        self.close()


class SettingsWindow(QWidget):
    def __init__(self, parent_client):
        super().__init__()
        self.parent_client = parent_client
        self.setWindowTitle("Memos 设置")
        self.resize(320, 120)
        layout = QVBoxLayout()

        reset_btn = QPushButton("重新设置 URL")
        reset_btn.clicked.connect(self.reset_url)
        layout.addWidget(reset_btn)

        self.tray_checkbox = QCheckBox("关闭主窗口时最小化到系统托盘")
        config = load_config()
        self.tray_checkbox.setChecked(config["close_to_tray"])
        self.tray_checkbox.stateChanged.connect(self.on_checkbox_changed)
        layout.addWidget(self.tray_checkbox)

        self.setLayout(layout)

    def reset_url(self):
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
        if hasattr(self.parent_client, 'view'):
            self.parent_client.view.close()
            del self.parent_client.view
        self.parent_client.show_launcher()
        self.close()

    def on_checkbox_changed(self, state):
        close_to_tray = (state == 2)
        config = load_config()
        save_config(
            url=config.get("memos_url"),
            window_geo=config.get("window"),
            close_to_tray=close_to_tray
        )


class MemosClient:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        icon = QIcon(self.get_icon_path())
        self.app.setWindowIcon(icon)

        config = load_config()
        if config["memos_url"]:
            QTimer.singleShot(0, lambda: self.show_memo_window(config["memos_url"], config.get("window")))
        else:
            self.show_launcher()

        self.tray_icon = QSystemTrayIcon(icon, self.app)
        self.setup_tray_menu()
        self.tray_icon.show()

    def get_icon_path(self):
        if getattr(sys, 'frozen', False):
            return os.path.join(sys._MEIPASS, "memos.ico")
        else:
            return "memos.ico"

    def setup_tray_menu(self):
        menu = QMenu()
        settings_action = menu.addAction("设置")
        settings_action.triggered.connect(self.show_settings)
        quit_action = menu.addAction("退出")
        quit_action.triggered.connect(self.app.quit)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self.on_tray_activated)

    def on_tray_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick
        ):
            if hasattr(self, 'view'):
                if not self.view.isVisible():
                    self.view.show()
                self.view.raise_()
                self.view.activateWindow()
            elif hasattr(self, 'launcher'):
                if not self.launcher.isVisible():
                    self.launcher.show()
                self.launcher.raise_()
                self.launcher.activateWindow()

    def show_settings(self):
        if not hasattr(self, 'settings_window') or not self.settings_window.isVisible():
            self.settings_window = SettingsWindow(self)
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def show_launcher(self):
        self.launcher = LauncherWindow(self.show_memo_window)
        self.launcher.setWindowIcon(QIcon(self.get_icon_path()))
        self.launcher.show()

    def show_memo_window(self, url, window_state=None):
        WEB_DATA_DIR = CONFIG_DIR / "web_data"
        WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)

        self._profile = QWebEngineProfile("MemosProfile", self.app)
        self._profile.setPersistentStoragePath(str(WEB_DATA_DIR))
        self._profile.setHttpUserAgent(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        )
        self._profile.setHttpCacheMaximumSize(64 * 1024 * 1024)
        self._profile.setHttpCacheType(self._profile.HttpCacheType.DiskHttpCache)

        self._page = QWebEnginePage(self._profile)
        self.view = QWebEngineView()
        self.view.setWindowIcon(QIcon(self.get_icon_path()))
        self.view.setWindowTitle("Memos Desktop")

        if window_state:
            x = max(0, window_state.get("x", 100))
            y = max(0, window_state.get("y", 100))
            w = max(600, window_state.get("width", 1000))
            h = max(400, window_state.get("height", 700))
            self.view.setGeometry(x, y, w, h)
        else:
            self.view.resize(1000, 700)

        def inject_scrollbar_css():
            script = """
            (function() {
                const style = document.createElement('style');
                style.textContent = `
                    ::-webkit-scrollbar {
                        width: 8px;
                        height: 8px;
                    }
                    ::-webkit-scrollbar-thumb {
                        background: rgba(0,0,0,0.2);
                        border-radius: 4px;
                    }
                    ::-webkit-scrollbar-thumb:hover {
                        background: rgba(0,0,0,0.3);
                    }
                    ::-webkit-scrollbar-track {
                        background: transparent;
                    }
                `;
                document.head.appendChild(style);
            })();
            """
            self.view.page().runJavaScript(script)

        self.view.loadFinished.connect(lambda ok: inject_scrollbar_css() if ok else None)
        self.view.load(QUrl(url))
        self.view.show()

        def on_close(event):
            event.ignore()
            config = load_config()
            if config["close_to_tray"]:
                self.view.hide()
            else:
                self.app.quit()
            save_config(url=url, window_geo=self.view.geometry())
        self.view.closeEvent = on_close

    def run(self):
        sys.exit(self.app.exec())


if __name__ == "__main__":
    client = MemosClient()
    client.run()