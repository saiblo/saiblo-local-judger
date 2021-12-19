import sys

from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QApplication

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
        self.start_dialog.open()

    @Slot()
    def openRunningDialog(self):
        self.running_dialog.open()
        self.running_dialog.launch_judger()

    @Slot()
    def closeApp(self):
        self.app.quit()
