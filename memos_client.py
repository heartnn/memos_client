import sys
import json
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel, QMessageBox, QComboBox
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PyQt6.QtCore import QUrl, QTimer


CONFIG_DIR = Path.home() / ".memos-client"
CONFIG_FILE = CONFIG_DIR / "config.json"


def save_config(url: str, window_geo=None):
    CONFIG_DIR.mkdir(exist_ok=True)
    data = {"memos_url": url}
    if window_geo:
        data["window"] = {
            "x": window_geo.x(),
            "y": window_geo.y(),
            "width": window_geo.width(),
            "height": window_geo.height()
        }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return None


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
        save_config(url)
        self.on_connect(url)
        self.close()


class MemosClient:
    def __init__(self):
        self.app = QApplication(sys.argv)
        config = load_config()
        if config and config.get("memos_url"):
            QTimer.singleShot(0, lambda: self.show_memo_window(config["memos_url"], config.get("window")))
        else:
            self.show_launcher()

    def show_launcher(self):
        self.launcher = LauncherWindow(self.show_memo_window)
        self.launcher.show()

    def show_memo_window(self, url, window_state=None):
        WEB_DATA_DIR = CONFIG_DIR / "web_data"
        WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)

        # 启用持久化 Profile + 内存优化
        self._profile = QWebEngineProfile("MemosProfile", self.app)
        self._profile.setPersistentStoragePath(str(WEB_DATA_DIR))
        self._profile.setHttpUserAgent(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        )
        self._profile.setHttpCacheMaximumSize(64 * 1024 * 1024)  # 64MB
        self._profile.setHttpCacheType(self._profile.HttpCacheType.DiskHttpCache)

        settings = self._profile.settings()
        # LocalStorage 必须开启（用于登录态）

        self._page = QWebEnginePage(self._profile)
        self.view = QWebEngineView()
        self.view.setPage(self._page)
        self.view.setWindowTitle("Memos Desktop")

        if window_state:
            x = max(0, window_state.get("x", 100))
            y = max(0, window_state.get("y", 100))
            w = max(600, window_state.get("width", 1000))
            h = max(400, window_state.get("height", 700))
            self.view.setGeometry(x, y, w, h)
        else:
            self.view.resize(1000, 700)

        # 滚动条美化
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

        # 保存窗口状态
        original_close = self.view.closeEvent
        def on_close(event):
            save_config(url, self.view.geometry())
            original_close(event)
        self.view.closeEvent = on_close

    def run(self):
        sys.exit(self.app.exec())


if __name__ == "__main__":
    client = MemosClient()
    client.run()