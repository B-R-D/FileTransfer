# coding:utf-8
'''
UDP客户端GUI版
解决1：添加文件进度条；
改进2：文件传输完成后提示完成；
解决3：添加时不清除已添加，有按钮可清除；
改进4：MD5检查错误的文件提示（图标状态变化）；
解决5：选择文件时记住上次位置；
解决6：按照屏幕分辨率动态设置窗口尺寸；
改进7：可选是否成功传完后删除原文件；
改进8：文件名显示后加文件大小（可从选项切换是否显示）；
改进9：表格化视图——可切换简约视图和详细视图；
'''
import os, sys, functools, queue, time
import clientudp
from multiprocessing import Process, Queue

from PyQt5.QtCore import Qt, QCoreApplication, QSettings, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QFontMetrics, QIcon
from PyQt5.QtWidgets import QWidget, QDesktopWidget, QFormLayout, QHBoxLayout, QVBoxLayout, QFrame, QMainWindow, QApplication, QSizePolicy, QStackedLayout
from PyQt5.QtWidgets import QPushButton, QLabel, QDialog, QFileDialog, QInputDialog, QLineEdit, QAction, QMessageBox, QToolTip, QScrollArea, QSpinBox, QProgressBar

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
        self.prog = []
        self.que = Queue()
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
        self.setMinimumWidth(self.width/7.68)
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
        exitAct.triggered.connect(self.safeClose)
        
        settingMenu = menubar.addMenu('设置(&S)')
        netAct = QAction('网络设置(&N)', self)
        fileAct = QAction('传输设置(&F)', self)
        
        settingMenu.addAction(netAct)
        settingMenu.addAction(fileAct)
        netAct.triggered.connect(self.netSettingDialog)
        fileAct.triggered.connect(self.fileSettingDialog)

        self.Bselector = QPushButton('选择文件', self)
        flist = self.Bselector.clicked.connect(self.fileDialog)
                                  
        self.Lfile_empty = QLabel('未选中文件')
        self.Lfile_empty.setAlignment(Qt.AlignTop)
        self.Bsend = QPushButton('发送', self)
        self.Bsend.clicked.connect(self.fileChecker)
        
        # 设置布局
        self.widget = QWidget()
        self.setCentralWidget(self.widget)
        self.vbox = QVBoxLayout()
        self.vbox.setSpacing(30)
        self.vbox.addWidget(self.Bselector)
        
        self.file_widget = QWidget()
        self.scroll_vbox = QVBoxLayout()
        self.scroll_vbox.addWidget(self.Lfile_empty)

        self.form = QFormLayout()
        self.form.setSpacing(0)
        self.scroll_vbox.addLayout(self.form)
        self.scroll_vbox.setContentsMargins(8,8,8,8)
        self.file_widget.setLayout(self.scroll_vbox)
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.file_widget)
        self.scroll.setWidgetResizable(True)
        
        self.vbox.addWidget(self.scroll)
        self.vbox.addWidget(self.Bsend)
        self.widget.setLayout(self.vbox)
        
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
                    btn = QPushButton(QIcon('pending.png'), '', self)
                    btn.setFlat(True)
                    prog = QProgressBar()
                    prog.setTextVisible(False)
                    prog.setRange(0, os.path.getsize(f) // 65000 + 1)
                    label = QLabel(self.shorten_filename(os.path.split(f)[1], self.geometry().width()))
                    label.setToolTip(os.path.split(f)[1])
                    
                    # 堆栈式布局解决标签与进度条重合问题
                    prog_widget = QWidget()
                    prog_stack = QStackedLayout()
                    prog_stack.addWidget(prog)
                    prog_stack.addWidget(label)
                    prog_widget.setLayout(prog_stack)
                    prog_stack.setStackingMode(QStackedLayout.StackAll)
                    
                    self.file.append(f)
                    self.prog.append((os.path.split(f)[1], prog))
                    btn.clicked.connect(functools.partial(self.del_file, f))
                    self.form.addRow(btn, prog_widget)
            self.settings.setValue('path_history', os.path.split(fname[0][-1])[0])
        self.settings.sync()
        self.settings.endGroup()
        
    # 文件名宽度大于指定宽度（不含边框）时缩短
    def shorten_filename(self, name, width):
        metrics = QFontMetrics(self.font())
        if metrics.width(name) > width - 180:
            for i in range(12, len(name)):
                if metrics.width(name[:i]) > width - 200:
                    return name[:i] + '...'
        return name

    def del_file(self, name):
        index = self.file.index(name)
        self.form.removeRow(index)
        self.file.pop(index)
        self.prog.pop(index)
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
            # 启动传输子进程
            self.sender = Process(target=clientudp.thread_starter, args=(setting_host, setting_port, self.file, setting_file_at_same_time, self.que))
            self.sender.start()
            # 启动进度条
            self.timer = QTimer()
            self.timer.timeout.connect(self.updateProg)
            self.timer.start(5)
            
    def updateProg(self):
        # 需要一个安全退出的方案而不能通过超时（完成一个文件pop一个，为空则退出）
        try:
            message = self.que.get(timeout=5)
            if message['type'] == 'info':
                if message['message'] == 'MD5_passed':
                    # 图标变绿色对勾
                    pass
                elif message['message'] == 'MD5_failed':
                    # 图标变红色叉
                    pass
            elif message['type'] == 'prog':
                for tup in self.prog:
                    if tup[0] == message['name']:
                        tup[1].setValue(message['part'] + 1)
        except queue.Empty:
            # 避免阻塞，是否可尝试自调用？（退出条件是接收MD5信息，超过一定递归深度抛错退出即发送无响应）
            self.sender.terminate()
            while self.sender.is_alive():
                time.sleep(0.1)
            self.sender.close()
            self.timer.stop()
            del self.timer
            print('Empty.')

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
    
    def safeClose(self):
        self.sender.terminate()
        while self.sender.is_alive():
            time.sleep(0.1)
        self.sender.close()
        self.timer.stop()
        del self.timer
        QCoreApplication.instance().quit
        self.close()
    
    # 按ESC时关闭窗体
    def keyPressEvent(self, k):
        if k.key() == Qt.Key_Escape:
            self.safeClose()
    
    # 随窗口宽度调整截断文件名
    def resizeEvent(self, event):
        for i in range(self.form.rowCount()):
            form_prog = self.form.itemAt(i, QFormLayout.FieldRole)
            changed_text = self.shorten_filename(os.path.split(self.file[i])[1], event.size().width())
            form_prog.widget().findChild(QLabel).setText(changed_text)

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