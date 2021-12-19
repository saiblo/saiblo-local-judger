import json
import random
from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QDialog, QGridLayout, QSpinBox, QLineEdit, QPushButton, QLabel, QFileDialog, QMessageBox

from core.judger import Judger
from gui import glob_var


class StartDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("启动本地评测机")

        # Init input components
        self.player_count = QSpinBox()
        self.player_count.setMinimum(1)
        self.player_count.setValue(2)

        self.judger_host = QLineEdit()
        self.judger_host.setPlaceholderText("留空为 localhost")
        self.judger_port = QLineEdit()
        self.judger_port.setPlaceholderText("留空则随机生成")

        self.confirm_btn = QPushButton("Let's GO!")
        self.confirm_btn.clicked.connect(self.launchJudger)
        self.help_btn = QPushButton("Help")

        self.logic_path = QLineEdit()
        self.logic_path_btn = QPushButton("...")
        self.logic_path_btn.clicked.connect(self.browseForLogicPath)

        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("可选")
        self.output_path_btn = QPushButton("...")
        self.output_path_btn.clicked.connect(self.browseForOutputPath)

        self.config_path = QLineEdit()
        self.config_path.setPlaceholderText("可选")
        self.config_path_btn = QPushButton("...")
        self.config_path_btn.clicked.connect(self.browseForConfigFile)

        # Layout
        layout = QGridLayout(self)

        layout.addWidget(QLabel("玩家人数"), 0, 0)
        layout.addWidget(self.player_count, 0, 1)
        layout.addWidget(QLabel("监听端口"), 0, 2)
        layout.addWidget(self.judger_port, 0, 3)
        layout.addWidget(self.confirm_btn, 0, 4)
        layout.addWidget(self.help_btn, 0, 5)

        layout.addWidget(QLabel("逻辑启动脚本路径："), 1, 0)
        layout.addWidget(self.logic_path, 1, 1, 1, 4)
        layout.addWidget(self.logic_path_btn, 1, 5)

        layout.addWidget(QLabel("输出目录："), 2, 0)
        layout.addWidget(self.output_path, 2, 1, 1, 4)
        layout.addWidget(self.output_path_btn, 2, 5)

        layout.addWidget(QLabel("对局配置文件路径："), 3, 0)
        layout.addWidget(self.config_path, 3, 1, 1, 4)
        layout.addWidget(self.config_path_btn, 3, 5)

    @Slot()
    def launchJudger(self):
        player_count = self.player_count.value()

        judger_host = self.judger_host.text()
        if not judger_host:
            judger_host = "localhost"

        judger_port = 0
        if len(self.judger_port.text()) != 0:
            try:
                judger_port = int(self.judger_port.text())
                if judger_port < 1024 or judger_port > 65535:
                    raise ValueError
            except ValueError:
                QMessageBox.critical(self, "输入无效", "监听端口应为1024到65535之间的整数")
                return

        logic_path = Path(self.logic_path.text())
        if not logic_path.exists() or not logic_path.is_file():
            QMessageBox.critical(self, "输入无效", "逻辑启动脚本不存在")
            return

        if len(self.output_path.text()) == 0:
            output = "res-{:010d}".format(random.randrange(0, 10000000000))
            output_path = Path.cwd() / output
        else:
            output_path = Path(self.output_path.text())
        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except OSError:
            QMessageBox.critical(self, "输入无效", "无法创建输出目录")
            return

        if len(self.config_path.text()) == 0:
            config = {}
        else:
            config_path = Path(self.config_path)
            if not config_path.exists() or not config_path.is_file():
                QMessageBox.critical(self, "输入无效", "对局配置文件不存在")
                return
            else:
                try:
                    with config_path.open("r") as f:
                        config = json.load(f)
                except json.decoder.JSONDecodeError:
                    QMessageBox.critical(self, "输入无效", "对局配置文件不是合法的JSON")
                    return
                except OSError:
                    QMessageBox.critical(self, "输入无效", "读取对局配置文件时出错")
                    return

        judger_config = {
            "port": judger_port,
            "player_count": player_count,
            "config": config,
            "output": output_path,
            "logic_path": Path.cwd() / logic_path,
            "protocol_version": 1
        }
        glob_var.judger_config = judger_config
        glob_var.judger = Judger(**judger_config)
        self.accept()

    @Slot()
    def browseForLogicPath(self):
        file_name = QFileDialog.getOpenFileName(self, "选择逻辑脚本")
        if len(file_name) == 2:
            self.logic_path.setText(file_name[0])

    @Slot()
    def browseForOutputPath(self):
        dir_name = QFileDialog.getExistingDirectory(self, "选择输出目录", options=QFileDialog.ShowDirsOnly)
        self.output_path.setText(dir_name)

    @Slot()
    def browseForConfigFile(self):
        file_name = QFileDialog.getOpenFileName(self, "选择对局配置文件", filter="JSON 文件 (*.json)")
        if len(file_name) == 2:
            self.config_path.setText(file_name[0])
