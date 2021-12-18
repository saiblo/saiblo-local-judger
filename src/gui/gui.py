import sys

from PySide6.QtWidgets import QApplication

from .start_dialog import StartDialog


def main():
    app = QApplication(sys.argv)
    StartDialog().exec()
    StartDialog().exec()
