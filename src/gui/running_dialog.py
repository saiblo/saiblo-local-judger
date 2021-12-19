from typing import List

from PySide6.QtCore import Qt, Signal, Slot, QObject, QThread
from PySide6.QtGui import QFont, QCloseEvent
from PySide6.QtWidgets import QDialog, QVBoxLayout, QProgressBar, QLabel, QMessageBox

from core.judger import JudgerEvent
from core.logger import set_log_output_file
from gui import glob_var


class JudgerRunner(QObject):
    finished = Signal()
    crashed = Signal(Exception)

    @Slot()
    def run(self):
        try:
            set_log_output_file(glob_var.judger_config.get("output"))
            glob_var.summary = glob_var.judger.start()
            glob_var.judger.set_event_handler(None)
            self.finished.emit()
        except Exception as e:
            self.crashed.emit(e)


class RunningDialog(QDialog):
    need_refresh = Signal()

    def __init__(self):
        super().__init__()
        self.setFixedSize(450, 200)

        # States
        self.listen_addr = None
        self.current_player_count = 0
        self.current_round = 0
        self.judger_exited = False
        self.judger_log_text = ""
        self.judger_runner = None
        self.judger_thread = None
        self.need_refresh.connect(self.refresh)

        # Components
        self.main_state = QLabel()
        self.main_state.setAlignment(Qt.AlignCenter)
        main_state_font: QFont = self.main_state.font()
        main_state_font.setPointSize(15)
        main_state_font.setBold(True)
        self.main_state.setFont(main_state_font)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)

        self.port_info = QLabel()
        self.port_info.setAlignment(Qt.AlignCenter)

        self.player_info = QLabel()
        self.player_info.setAlignment(Qt.AlignCenter)

        self.round_info = QLabel()
        self.round_info.setAlignment(Qt.AlignCenter)

        self.refresh()

        # Layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.main_state)
        layout.addWidget(self.progress)
        layout.addWidget(self.port_info)
        layout.addWidget(self.player_info)
        layout.addWidget(self.round_info)

    def launch_judger(self):
        glob_var.judger.set_event_handler(self.handle_judger_event)
        self.judger_runner = JudgerRunner()
        self.judger_thread = QThread(self)
        self.judger_thread.started.connect(self.judger_runner.run)
        self.judger_thread.finished.connect(self.judger_thread.deleteLater)
        self.judger_runner.moveToThread(self.judger_thread)
        self.judger_runner.finished.connect(self.judge_finished)
        self.judger_runner.crashed.connect(self.judge_crashed)
        self.judger_thread.start()

    @Slot()
    def judge_finished(self):
        self.judger_thread.quit()
        self.judger_thread.wait()
        self.accept()

    @Slot(Exception)
    def judge_crashed(self, e: Exception):
        QMessageBox.critical(self, "评测机异常退出", "评测机崩溃，请向Saiblo维护人员汇报此问题：\n" + str(e))
        self.judger_thread.quit()
        self.judger_thread.wait()
        self.reject()

    def handle_judger_event(self, **kwargs):
        type: JudgerEvent = kwargs.get("type")
        if type == JudgerEvent.TCP_SERVER_STARTED:
            self.listen_addr = kwargs.get("addr")
        elif type == JudgerEvent.AI_CONNECTED:
            self.current_player_count = self.current_player_count + 1
        elif type == JudgerEvent.NEW_ROUND:
            self.current_round = self.current_round + 1
        elif type == JudgerEvent.GAME_OVER:
            self.judger_exited = True
        else:
            return
        self.need_refresh.emit()

    def closeEvent(self, event: QCloseEvent) -> None:
        btn = QMessageBox.warning(self, "确认关闭", "是否停止正在运行的本地评测机？", QMessageBox.Yes | QMessageBox.Cancel,
                                  QMessageBox.Cancel)
        if btn == QMessageBox.Yes:
            try:
                glob_var.judger.shutdown()
            except:
                pass
            self.judger_thread.quit()
            self.judger_thread.wait()
            event.accept()
        else:
            event.ignore()

    @Slot()
    def refresh(self):
        text: List[str] = ["", "", "", ""]
        labels: List[QLabel] = [self.main_state, self.port_info, self.player_info, self.round_info]
        if self.listen_addr is None:
            text[0] = "等待评测机启动"
        elif self.judger_exited:
            text[0] = "评测结束"
            self.progress.setRange(0, 1)
            self.progress.setValue(1)
        else:
            text[0] = "正在评测"
            text[1] = f"评测机监听地址：{self.listen_addr}"
            max_player_count = glob_var.judger_config["player_count"]
            if self.current_player_count < max_player_count:
                text[2] = f"等待AI连接：{self.current_player_count}/{max_player_count}"
            else:
                text[2] = f"全部{max_player_count}位AI选手已经连接"
                text[3] = f"当前回合数：{self.current_round}"
        for i in range(4):
            labels[i].setText(text[i])
