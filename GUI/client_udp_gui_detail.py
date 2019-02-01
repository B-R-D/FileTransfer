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
from PyQt5.QtWidgets import QPushButton, QLabel, QDialog, QFileDialog, QInputDialog, QLineEdit, QAction, QMessageBox, QToolTip, QScrollArea, QSpinBox, QProgressBar, QCheckBox

class FileStatus:
    '''文件信息类'''
    def __init__(self, path):
        self._path = path
        self._name = os.path.split(self._path)[1]
        self._size = os.path.getsize(self._path)
        self._all = self._size // 65000 + 1
        self._status = 'pending'
        
        self._button = QPushButton(QIcon(os.path.join('icon', 'pending.png')), '')
        self._button.setFlat(True)
        self._prog = QProgressBar()
        self._prog.setTextVisible(False)
        self._prog.setRange(0, self._all)
        self._label = QLabel(self._name)
        self._label.setToolTip(self._name)
    
    def getFileButton(self):
        return self._button
    def getFileProg(self):
        return self._prog
    def getFileLabel(self):
        return self._label
    def getFilePath(self):
        return self._path
    def getFileName(self):
        return self._name
    def getFileStatus(self):
        return self._status
    
    def setFileStatus(self, new_status):
        self._status = new_status
        if self._status == 'pending':
            self._button.setIcon(QIcon(os.path.join('icon', 'pending.png')))
            self._button.setToolTip('等待传输')
        elif self._status == 'error':
            self._button.setIcon(QIcon(os.path.join('icon', 'error.png')))
            self._button.setToolTip('传输错误')
        elif self._status == 'complete':
            self._button.setIcon(QIcon(os.path.join('icon', 'complete.png')))
            self._button.setToolTip('传输完成')
        elif self._status == 'uploading':
            self._button.setIcon(QIcon(os.path.join('icon', 'uploading.png')))
            self._button.setToolTip('传送中')
        
class ClientWindow(QMainWindow):
    '''Qt5窗体类'''
    def __init__(self):
        self.files = []
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
        uiAct = QAction('界面设置(&U)', self)
        
        settingMenu.addAction(netAct)
        settingMenu.addAction(fileAct)
        settingMenu.addAction(uiAct)
        netAct.triggered.connect(self.netSettingDialog)
        fileAct.triggered.connect(self.fileSettingDialog)
        uiAct.triggered.connect(self.uiSettingDialog)

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
        
    # 选择要发送的文件且做出内置文件实例列表
    def fileDialog(self):
        self.settings.beginGroup('Misc')
        setting_path_history = self.settings.value('path_history', '.')
        self.settings.endGroup()
        fname = QFileDialog.getOpenFileNames(self, '请选择文件', setting_path_history)
        # 做排列文件需要的组件列表
        if fname[0]:
            path_list = [inst.getFilePath() for inst in self.files]
            for path in fname[0]:
                if path not in path_list:
                    self.files.append(FileStatus(path))
            self.Lfile_empty.hide()
            # 从设置中切换布局（待完善）
            self.settings.beginGroup('UISetting')
            setting_detail_view = self.settings.value('detail_view', False)
            self.settings.endGroup()
            if setting_detail_view:
                self.simple_viewer()
            else:
                pass
            self.settings.beginGroup('Misc')
            self.settings.setValue('path_history', os.path.split(fname[0][-1])[0])
            self.settings.endGroup()
        self.settings.sync()
        
    # 文件名宽度大于指定宽度（不含边框）时缩短
    def shorten_filename(self, name, width):
        metrics = QFontMetrics(self.font())
        if metrics.width(name) > width - 180:
            for i in range(12, len(name)):
                if metrics.width(name[:i]) > width - 200:
                    return name[:i] + '...'
        return name
    
    # 简明视图构建（按设置调用，删除表格布局中所有列后重做列）
    def simple_viewer(self):
        for inst in self.files:
            # 堆栈式布局解决标签与进度条重合问题
            prog_widget = QWidget()
            prog_stack = QStackedLayout()
            prog_stack.addWidget(inst.getFileProg())
            prog_stack.addWidget(inst.getFileLabel())
            prog_widget.setLayout(prog_stack)
            prog_stack.setStackingMode(QStackedLayout.StackAll)

            inst.getFileButton().clicked.connect(functools.partial(self.del_file, inst))
            inst.getFileLabel().setText(self.shorten_filename(inst.getFileName(), self.geometry().width()))
            self.form.addRow(inst.getFileButton(), prog_widget)
    '''
    # 详细视图构建
    def detail_viewer(self):
        for f in files:
            if f not in self.file:
                btn = QPushButton(QIcon('cancel.png'), '', self)
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
    '''
    def del_file(self, inst):
        index = self.files.index(inst)
        self.form.removeRow(index)
        self.files.pop(index)
        if not self.files:
            self.Lfile_empty.show()
        else:
            self.Lfile_empty.hide()   

    # 测试有没有选中文件
    def fileChecker(self):
        if not self.files:
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
            for inst in self.files:
                inst.setFileStatus('uploading')
            path_list = [inst.getFilePath() for inst in self.files]
            self.file_sender = Process(target=clientudp.thread_starter, args=(setting_host, setting_port, path_list, setting_file_at_same_time, self.que))
            self.file_sender.start()
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
                    for inst in self.files:
                        if inst.getFileName() == message['name']:
                            inst.setFileStatus('complete')
                            self.files.remove(inst)
                elif message['message'] == 'MD5_failed':
                    for inst in self.files:
                        if inst.getFileName() == message['name']:
                            inst.setFileStatus('error')
                            self.files.remove(inst)
            elif message['type'] == 'prog':
                for inst in self.files:
                    if inst.getFileName() == message['name']:
                        inst.getFileProg().setValue(message['part'] + 1)
        except queue.Empty:
            self.file_sender.terminate()
            while self.file_sender.is_alive():
                time.sleep(0.1)
            self.file_sender.close()
            self.timer.stop()
            del self.timer
            msgBox = QMessageBox()
            msgBox.setWindowTitle('错误')
            msgBox.setIcon(QMessageBox.Warning)
            msgBox.setText('连接中断，传输失败！')
            msgBox.addButton('确定', QMessageBox.AcceptRole)
            msgBox.exec()

    def netSettingDialog(self):
        self.netsetting = NetDialog()
        self.netsetting.show()
    
    def fileSettingDialog(self):
        self.transsetting = TransDialog()
        self.transsetting.show()
        
    def uiSettingDialog(self):
        self.uisetting = UIDialog()
        self.uisetting.show()
    
    # 打开窗体时位于屏幕中心
    def center(self):
        qr = self.frameGeometry()
        cp = self.resolution.center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())
    
    def safeClose(self):
        if 'file_sender' in dir(self):
            self.file_sender.terminate()
            while self.file_sender.is_alive():
                time.sleep(0.1)
            self.file_sender.close()
            self.timer.stop()
            del self.timer
        QCoreApplication.instance().quit
        self.close()
    
    # 按ESC时关闭窗体
    def keyPressEvent(self, k):
        if k.key() == Qt.Key_Escape:
            self.safeClose()
    
    # 跟随显示模式随窗口宽度调整截断文件名
    def resizeEvent(self, event):
        for inst in self.files:
            changed_text = self.shorten_filename(inst.getFileName(), event.size().width())
            inst.getFileLabel().setText(changed_text)

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

# 自定义界面设置对话框
class UIDialog(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QSettings(os.path.join(os.path.abspath('.'), 'settings.ini'), QSettings.IniFormat)
        self.initUI()

    def initUI(self):
        self.resolution = QDesktopWidget().availableGeometry()
        self.height = self.resolution.height()
        self.width = self.resolution.width()
        self.resize(self.width/8.5, 0)
        
        self.settings.beginGroup('UISetting')
        self.Lview = QLabel('启用详细视图')
        self.Cview = QCheckBox(self)
        setting_view = bool(self.settings.value('detail_view', False))
        self.Cview.setChecked(setting_view)
        self.settings.endGroup()
        
        self.Bconfirm = QPushButton('确定', self)
        self.Bcancel = QPushButton('取消', self)
        
        self.Bconfirm.clicked.connect(self.store)
        self.Bcancel.clicked.connect(self.close)
        
        # 窗口布局
        form = QFormLayout()
        form.setSpacing(30)
        form.addRow(self.Lview, self.Cview)
        hbox = QHBoxLayout()
        hbox.addStretch(1)
        hbox.addWidget(self.Bconfirm)
        hbox.addWidget(self.Bcancel)
        hbox.addStretch(1)
        form.addRow(hbox)
        self.setLayout(form)
        
        self.setWindowTitle('界面设置')
    
    def store(self):
        self.settings.beginGroup('UISetting')
        self.settings.setValue('detail_view', self.Cview.isChecked())
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