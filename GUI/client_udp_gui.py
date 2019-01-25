# coding:utf-8
'''
UDP客户端GUI版
改进1：添加文件进度条；
改进2：文件传输完成后提示完成；
解决3：添加时不清除已添加，有按钮可清除；
改进4：MD5检查错误的文件提示；
解决5：选择文件时记住上次位置；
解决6：按照屏幕分辨率动态设置窗口尺寸；
改进7：可选是否成功传完后删除原文件；
'''
import os, sys, functools
import clientudp
from multiprocessing import Process
from PyQt5.QtCore import Qt, QCoreApplication, QSettings, QRegExp
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QWidget, QDesktopWidget, QGridLayout, QFormLayout, QHBoxLayout, QVBoxLayout, QFrame, QMainWindow, QApplication, QSpinBox
from PyQt5.QtWidgets import QPushButton, QLabel, QDialog, QFileDialog, QInputDialog, QLineEdit, QAction, QMessageBox

class FilePart:
    def __init__(self, name, size, part, all, data):
        self.name = name
        self.size = size
        self.part = part
        self.all = all
        self.data = data

class ClientWindow(QMainWindow):
    '''Qt5窗体类'''
    def __init__(self):
        self.file = []
        self.Bcancel = []
        self.Lfile = []
        super().__init__()
        self.settings = QSettings(os.path.join(os.path.abspath('.'), 'settings.ini'), QSettings.IniFormat)
        self.initUI()
        
    def initUI(self):
        self.setFont(QFont('Arial', 10))
        # 按屏幕分辨率调整窗口大小
        self.resolution = QDesktopWidget().availableGeometry()
        self.height = self.resolution.height()
        self.width = self.resolution.width()
        self.resize(self.width/6.4, self.height/2.7)
        self.center()
        
        # 添加菜单栏
        menubar = self.menuBar()
        fileMenu = menubar.addMenu('文件(&F)')
        chooseAct = QAction('选择文件(&C)', self)
        sendAct = QAction('发送(&S)', self)
        exitAct = QAction('退出(&Q)', self)
        
        fileMenu.addAction(chooseAct)
        fileMenu.addAction(sendAct)
        fileMenu.addSeparator()
        fileMenu.addAction(exitAct)
        chooseAct.triggered.connect(self.fileDialog)
        sendAct.triggered.connect(self.fileChecker)
        exitAct.triggered.connect(QCoreApplication.instance().quit)
        
        settingMenu = menubar.addMenu('设置(&S)')
        netAct = QAction('网络设置(&N)', self)
        fileAct = QAction('传输设置(&F)', self)
        
        settingMenu.addAction(netAct)
        settingMenu.addAction(fileAct)
        netAct.triggered.connect(self.netSettingDialog)
        fileAct.triggered.connect(self.fileSettingDialog)

        self.Bselector = QPushButton('选择文件', self)
        flist = self.Bselector.clicked.connect(self.fileDialog)
        # 文件为空时的控件
        self.Lfile_empty = (QLabel('未选中文件'))
        self.Lfile_empty.setAlignment(Qt.AlignTop)
        self.Bsend = QPushButton('发送', self)

        self.Bsend.clicked.connect(self.fileChecker)
        
        # 设置布局
        self.widget = QWidget()
        self.setCentralWidget(self.widget)
        self.grid = QGridLayout()
        self.grid.setSpacing(30)
        self.grid.addWidget(self.Bselector, 1, 1, 1, 1)
        self.grid.addWidget(self.Lfile_empty, 2, 1)
        self.grid.addWidget(self.Bsend, 3, 1, 1, 1)
        self.widget.setLayout(self.grid)
        # 文件列表用
        self.form = QFormLayout()
        self.form.setSpacing(0)
        self.grid.addLayout(self.form, 2, 1)
        
        self.setWindowTitle('FileTransfer')
        self.show()
        
    # 选择要发送的文件且显示文件名列表
    def fileDialog(self):
        self.settings.beginGroup('Misc')
        setting_path_history = self.settings.value('path_history', '.')
        fname = QFileDialog.getOpenFileNames(self, '请选择文件', setting_path_history)
        # 做排列文件需要的组件列表
        if fname[0]:
            self.Lfile_empty.hide()
            for f in fname[0]:
                if f not in self.file:
                    btn = QPushButton(self)
                    # 显示用的文件名需要缩短：前7字符后7字符+扩展名（用位计算长度）
                    label = QLabel(os.path.split(f)[1])
                    self.file.append(f)
                    btn.clicked.connect(functools.partial(self.del_file, f))
                    self.form.addRow(btn, label)
            self.settings.setValue('path_history', os.path.split(fname[0][-1])[0])
        self.settings.sync()
        self.settings.endGroup()
        
    def del_file(self, name):
        index = self.file.index(name)
        self.form.removeRow(index)
        self.file.pop(index)
        if not self.file:
            self.Lfile_empty.show()
        else:
            self.Lfile_empty.hide()
        
    # 测试有没有选中文件
    def fileChecker(self):
        if not self.file:
            msgBox = QMessageBox()
            msgBox.setWindowTitle('错误')
            msgBox.setIcon(QMessageBox.Warning)
            msgBox.setText('未选择文件！')
            msgBox.addButton('确定', QMessageBox.AcceptRole)
            msgBox.exec()
        else:
            self.settings.beginGroup('TransSetting')
            setting_file_at_same_time = int(self.settings.value('file_at_same_time', 2))
            self.settings.endGroup()
            self.settings.beginGroup('NetSetting')
            setting_host = self.settings.value('host', '127.0.0.1')
            setting_port = int(self.settings.value('port', 12345))
            self.settings.endGroup()
            sender = Process(target=clientudp.thread_starter, args=(setting_host, setting_port, self.file, setting_file_at_same_time))
            sender.start()
    
    def netSettingDialog(self):
        self.netsetting = NetDialog()
        self.netsetting.show()
    
    def fileSettingDialog(self):
        self.transsetting = TransDialog()
        self.transsetting.show()
    
    # 打开窗体时位于屏幕中心
    def center(self):
        qr = self.frameGeometry()
        cp = self.resolution.center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    # 按ESC时关闭窗体
    def keyPressEvent(self, k):
        if k.key() == Qt.Key_Escape:
            self.close()

# 自定义网络设置对话框
class NetDialog(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QSettings(os.path.join(os.path.abspath('.'), 'settings.ini'), QSettings.IniFormat)
        self.initUI()

    def initUI(self):
        self.resolution = QDesktopWidget().availableGeometry()
        self.height = self.resolution.height()
        self.width = self.resolution.width()
        self.resize(self.width/7.68, self.height/10.8)
        
        self.settings.beginGroup('NetSetting')
        self.Lip = QLabel('服务器IP')
        self.Eip = QLineEdit(self)
        setting_host = self.settings.value('host', '127.0.0.1')
        self.Eip.setText(setting_host)
        self.Lport = QLabel('端口号(1024-65535)')
        self.Sport = QSpinBox(self)
        self.Sport.setRange(1024, 65535)
        self.Sport.setWrapping(True)
        setting_port = int(self.settings.value('port', 12345))
        self.Sport.setValue(setting_port)
        self.settings.endGroup()
        
        self.Bconfirm = QPushButton('确定', self)
        self.Bcancel = QPushButton('取消', self)
        self.Bconfirm.clicked.connect(self.store)
        self.Bcancel.clicked.connect(self.close)
        
        # 窗口布局
        form = QFormLayout()
        form.setSpacing(30)
        form.addRow(self.Lip, self.Eip)
        form.addRow(self.Lport, self.Sport)
        hbox = QHBoxLayout()
        hbox.addStretch(1)
        hbox.addWidget(self.Bconfirm)
        hbox.addWidget(self.Bcancel)
        hbox.addStretch(1)
        form.addRow(hbox)
        self.setLayout(form)
        
        self.setWindowTitle('网络设置')
    
    def store(self):
        self.settings.beginGroup('NetSetting')
        self.settings.setValue('host', self.Eip.text())
        self.settings.setValue('port', self.Sport.value())
        self.settings.sync()
        self.settings.endGroup()
        self.close()
        
    def keyPressEvent(self, k):
        if k.key() == Qt.Key_Escape:
            self.close()

# 自定义传输设置对话框
class TransDialog(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QSettings(os.path.join(os.path.abspath('.'), 'settings.ini'), QSettings.IniFormat)
        self.initUI()

    def initUI(self):
        self.resolution = QDesktopWidget().availableGeometry()
        self.height = self.resolution.height()
        self.width = self.resolution.width()
        self.resize(self.width/8.5, 0)
        
        self.settings.beginGroup('TransSetting')
        self.Lfile_num = QLabel('同时传送的文件数(1-3)')
        self.Sfile_num = QSpinBox(self)
        self.Sfile_num.setRange(1, 3)
        self.Sfile_num.setWrapping(True)
        setting_file_num = int(self.settings.value('file_at_same_time', 2))
        self.Sfile_num.setValue(setting_file_num)
        self.settings.endGroup()
        
        self.Bconfirm = QPushButton('确定', self)
        self.Bcancel = QPushButton('取消', self)
        
        self.Bconfirm.clicked.connect(self.store)
        self.Bcancel.clicked.connect(self.close)
        
        # 窗口布局
        form = QFormLayout()
        form.setSpacing(30)
        form.addRow(self.Lfile_num, self.Sfile_num)
        hbox = QHBoxLayout()
        hbox.addStretch(1)
        hbox.addWidget(self.Bconfirm)
        hbox.addWidget(self.Bcancel)
        hbox.addStretch(1)
        form.addRow(hbox)
        self.setLayout(form)
        
        self.setWindowTitle('传输设置')
    
    def store(self):
        self.settings.beginGroup('TransSetting')
        self.settings.setValue('file_at_same_time', self.Sfile_num.value())
        self.settings.sync()
        self.settings.endGroup()
        self.close()
        
    def keyPressEvent(self, k):
        if k.key() == Qt.Key_Escape:
            self.close()

if __name__ == '__main__':
    error = []
    app = QApplication(sys.argv)
    window = ClientWindow()
    sys.exit(app.exec())