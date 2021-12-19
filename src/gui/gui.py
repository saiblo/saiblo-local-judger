import sys

from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QApplication, QMessageBox

from . import glob_var
from .running_dialog import RunningDialog
from .start_dialog import StartDialog


class Main(QObject):
    def __init__(self):
        super().__init__()
        self.app = QApplication(sys.argv)

        self.start_dialog = StartDialog()
        self.running_dialog = RunningDialog()

        self.start_dialog.accepted.connect(self.openRunningDialog)
        self.running_dialog.accepted.connect(self.openStartDialog)

        self.start_dialog.rejected.connect(self.closeApp)
        self.running_dialog.rejected.connect(self.closeApp)

        self.start_dialog.open()
        self.app.exec()

    @Slot()
    def openStartDialog(self):
        QMessageBox.information(None, "评测完成", f"评测完成\n请查看{glob_var.judger_config.get('output')}文件夹获取详细信息")
        self.start_dialog.open()

    @Slot()
    def openRunningDialog(self):
        self.running_dialog.open()
        self.running_dialog.launch_judger()

    @Slot()
    def closeApp(self):
        self.app.quit()


def main():
    Main()
