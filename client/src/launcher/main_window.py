import sys
import webbrowser

from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QApplication, QMessageBox
from qt_material import apply_stylesheet

from .login_window import LoginWindow
from ..consts.asset_paths import Path
from ..consts.urls import URLS
from .. import run_game


class LauncherView(QWidget):
    def __init__(self):
        self.app = QApplication(sys.argv)
        super().__init__()
        apply_stylesheet(self.app, theme='dark_teal.xml')
        self.setMinimumSize(500, 0)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.setWindowTitle('OTS')
        self.setWindowIcon(QIcon(QPixmap(Path.tetris_image)))

        self.single_btn = QPushButton("Single play")
        self.single_btn.clicked.connect(self.on_single_btn_clicked)
        self.layout.addWidget(self.single_btn)


        self.online_btn = QPushButton("Online play")
        self.online_btn.clicked.connect(self.on_online_btn_clicked)
        self.layout.addWidget(self.online_btn)

        self.signup_btn = QPushButton("Sign up")
        self.signup_btn.clicked.connect(self.on_signup_btn_clicked)
        self.layout.addWidget(self.signup_btn)

        self.help_btn = QPushButton("Help")
        self.help_btn.clicked.connect(self.on_help_btn_clicked)
        self.layout.addWidget(self.help_btn)

        self.dual_btn = QPushButton("GitHub")
        self.dual_btn.clicked.connect(self.on_github_btn_clicked)
        self.layout.addWidget(self.dual_btn)


        self.show()

    def on_single_btn_clicked(self):  # override
        pass

    def on_github_btn_clicked(self):  # override
        pass

    def on_online_btn_clicked(self):  # override
        pass

    def on_signup_btn_clicked(self):  # override
        pass

    def on_help_btn_clicked(self):
        pass


class Launcher(LauncherView):
    def __init__(self):
        super().__init__()
        self.lw = LoginWindow()

    def on_single_btn_clicked(self):
        self.close()
        run_game.run_single()

    def on_github_btn_clicked(self):
        webbrowser.open(URLS.github_url)

    def on_online_btn_clicked(self):
        self.close()
        self.lw.show()

    def on_signup_btn_clicked(self):
        webbrowser.open(URLS.signup_url)

    def on_help_btn_clicked(self):
        webbrowser.open(URLS.help_image_url)

    def run_launcher(self):
        self.app.exec_()
