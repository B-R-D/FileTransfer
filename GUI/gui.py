# coding:utf-8
'''
UDP客户端GUI版
'''
import os, sys, functools, queue, time
from multiprocessing import Process, Queue
import client, server

from PyQt5.QtCore import Qt, QCoreApplication, QSettings, QTimer
from PyQt5.QtGui import QFont, QFontMetrics, QIcon, QGuiApplication
from PyQt5.QtWidgets import QWidget, QFormLayout, QHBoxLayout, QVBoxLayout, QMainWindow, QApplication, QStackedLayout, QTableWidget
from PyQt5.QtWidgets import QPushButton, QLabel, QDialog, QFileDialog, QLineEdit, QAction, QMessageBox, QToolTip, QSpinBox, QProgressBar, QCheckBox, QTableWidgetItem, QAbstractItemView, QHeaderView, QGroupBox

class FileStatus:
    '''
    定义所需的基本文件信息类。
    可获取信息：文件路径，文件名，文件大小，当前状态；
    可获取绑定对象：状态按钮，进度条，显示文件名标签；
    包含方法：七个获取对象/信息方法，一个设置当前状态的方法。
    '''
    def __init__(self, path):
        self._path = path
        self._name = os.path.split(self._path)[1]
        self._size = os.path.getsize(self._path)
        self._all = self._size // 65000 + 1
        self._status = 'pending'
        
        # 按钮样式：状态图片+状态说明文字+无按钮边框
        self._button = QPushButton(QIcon(os.path.join('icon', 'pending.png')), '')
        self._button.setToolTip('等待传输')
        self._button.setFlat(True)
        # 进度条样式：不显示百分比
        self._prog = QProgressBar()
        self._prog.setTextVisible(False)
        self._prog.setRange(0, self._all)
        # 文件名标签样式：tooltip为文件全名
        self._label = QLabel(self._name)
        self._label.setToolTip(self._name)
    
    def getFilePath(self):
        return self._path
    def getFileName(self):
        return self._name
    def getFileSize(self):
        return client.display_file_length(self._size)
    def getFileStatus(self):
        return self._status
    def getFileButton(self):
        return self._button
    def getFileProg(self):
        return self._prog
    def getFileLabel(self):
        return self._label
    
    def setFileStatus(self, new_status):
        '''根据新设置的状态切换按钮图片及tooltip'''
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
            self._button.setToolTip('传输中')

class ClientWindow(QMainWindow):
    '''
    GUI主窗口类。
    包含控件：菜单栏，文件列表区域，文件选择对话框，三项设置对话框
    包含成员方法：简明/详细视图，
    '''
    def __init__(self):
        # 初始化文件列表：存放待发送文件的绝对路径
        self.files = []
        # 初始化进程间通信队列
        self.que = Queue()
        super().__init__()
        # 初始化设置ini文件
        self.settings = QSettings(os.path.join(os.path.abspath('.'), 'settings.ini'), QSettings.IniFormat)
        self.initUI()
        
    def initUI(self):
        self.setFont(QFont('Arial', 10))
        # 收集屏幕分辨率信息
        self.resolution = QGuiApplication.primaryScreen().availableGeometry()
        self.height = self.resolution.height()
        self.width = self.resolution.width()
        # 恢复上次关闭时的窗口尺寸
        self.settings.beginGroup('Misc')
        setting_window_size = self.settings.value('window_size', (self.width / 6.4, self.height / 2.7))
        self.settings.endGroup()
        self.resize(setting_window_size[0], setting_window_size[1])
        # 在屏幕中央(不含开始菜单栏)打开窗口
        self.frameGeometry().moveCenter(self.resolution.center())
        
        # 定义菜单栏：文件，设置
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
        clientAct = QAction('发送端设置(&C)', self)
        serverAct = QAction('接收端设置(&S)', self)
        uiAct = QAction('界面设置(&U)', self)
        
        settingMenu.addAction(clientAct)
        settingMenu.addAction(serverAct)
        settingMenu.addAction(uiAct)
        clientAct.triggered.connect(self.clientSettingDialog)
        serverAct.triggered.connect(self.serverSettingDialog)
        uiAct.triggered.connect(self.uiSettingDialog)

        # 定义控件：选择按钮(默认按钮)，空区域(左上对齐)，文件列表(单元格不可选择)，发送按钮
        self.Bselector = QPushButton('选择文件', self)
        self.Bselector.setDefault(True)
        self.Bselector.clicked.connect(self.fileDialog)
        self.Lfile_empty = QLabel('未选中文件')
        self.Lfile_empty.setAlignment(Qt.AlignTop)
        self.file_table = QTableWidget()
        self.file_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.file_table.hide()
        self.Bsend = QPushButton('发送', self)
        self.Bsend.clicked.connect(self.fileChecker)
        
        # 定义垂直布局的窗口主控件
        self.widget = QWidget()
        self.setCentralWidget(self.widget)
        self.vbox = QVBoxLayout()
        self.vbox.setSpacing(self.height / 70)
        self.vbox.addWidget(self.Bselector)
        self.vbox.addWidget(self.file_table)
        self.vbox.addWidget(self.Lfile_empty)
        self.vbox.addWidget(self.Bsend)
        self.widget.setLayout(self.vbox)

        # 从设置中读取视图设定并设定窗口最小值
        self.settings.beginGroup('UISetting')
        self.setting_detail_view = int(self.settings.value('detail_view', False))
        self.settings.endGroup()
        if not self.setting_detail_view:
            self.setMinimumWidth(self.width / 7.68)
        else:
            self.setMinimumWidth(self.width / 6.18)
        
        self.setWindowTitle('FileTransfer')
        self.show()
        
        # 按设置启动服务端
        self.settings.beginGroup('ServerSetting')
        setting_open_server = int(self.settings.value('open_server', True))
        self.settings.endGroup()
        if setting_open_server:
            self.settings.beginGroup('ServerSetting')
            setting_incoming_ip = self.settings.value('incoming_ip', '0.0.0.0')
            setting_bind_port = int(self.settings.value('bind_port', 54321))
            setting_receive_dir = self.settings.value('receive_dir', os.path.abspath('.'))
            self.settings.endGroup()
            self.server_starter = Process(target=server.starter, args=(setting_incoming_ip, setting_bind_port, setting_receive_dir, self.que))
            self.server_starter.start()
    
    def simple_viewer(self):
        '''简明视图构建：包含按钮及进度条'''

        # 通过文件名的tooltip生成视图中现有的文件名列表
        if self.file_table.rowCount():
            file_name = [self.file_table.cellWidget(i, 1).layout().widget(1).toolTip() for i in range(self.file_table.rowCount())]
        else:
            file_name = []

        # 设置简明视图样式：无框线，水平抬头不可见，按钮列自适应，文件名列宽自适应留白
        self.file_table.setColumnCount(2)
        self.file_table.setRowCount(len(self.files))
        self.file_table.setShowGrid(False)
        self.file_table.horizontalHeader().setVisible(False)
        self.file_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.file_table.resizeColumnToContents(0)

        # 针对新选择的文件在列表中增加新增文件的行
        for inst in self.files:
            if inst.getFileName() not in file_name:
                prog_widget = QWidget()
                prog_stack = QStackedLayout()
                prog_stack.addWidget(inst.getFileProg())
                prog_stack.addWidget(inst.getFileLabel())
                prog_stack.setStackingMode(QStackedLayout.StackAll)
                prog_widget.setLayout(prog_stack)

                inst.getFileLabel().setText(inst.getFileName())
                inst.getFileButton().clicked.connect(functools.partial(self.del_file, inst))
                self.file_table.setCellWidget(self.files.index(inst), 0, inst.getFileButton())
                self.file_table.setCellWidget(self.files.index(inst), 1, prog_widget)
        self.file_table.show()
        # 表格显示后截断文件名
        for inst in self.files:
            inst.getFileLabel().setText(self.shorten_filename(inst.getFileName(), self.file_table.columnWidth(1)))

    def detail_viewer(self):
        '''详细视图构建：包括按钮、进度条、详细分片进度、文件大小、状态'''
        if self.file_table.rowCount():
            file_name = [self.file_table.cellWidget(i, 1).layout().widget(1).toolTip() for i in range(self.file_table.rowCount())]
        else:
            file_name = []
        self.file_table.setColumnCount(5)
        self.file_table.setRowCount(len(self.files))
        self.file_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.file_table.setHorizontalHeaderLabels(['', '文件名', '传输进度', '文件大小', '状态'])
        for inst in self.files:
            if inst.getFileName() not in file_name:
                prog_widget = QWidget()
                prog_stack = QStackedLayout()
                prog_stack.addWidget(inst.getFileProg())
                prog_stack.addWidget(inst.getFileLabel())
                prog_stack.setStackingMode(QStackedLayout.StackAll)
                prog_widget.setLayout(prog_stack)
                inst.getFileLabel().setText(inst.getFileName())
                inst.getFileButton().clicked.connect(functools.partial(self.del_file, inst))

                # 设置各单元格样式：不可选中且VH居中
                file_prog = QTableWidgetItem('0.00 %')
                file_prog.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                file_prog.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
                file_size = QTableWidgetItem(inst.getFileSize())
                file_size.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
                file_size.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                file_status = QTableWidgetItem(inst.getFileButton().toolTip())
                file_status.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
                file_status.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

                # 用文件列表变量中的索引排列文件
                index = self.files.index(inst)
                self.file_table.setCellWidget(index, 0, inst.getFileButton())
                self.file_table.setCellWidget(index, 1, prog_widget)
                self.file_table.setItem(index, 2, file_prog)
                self.file_table.setItem(index, 3, file_size)
                self.file_table.setItem(index, 4, file_status)
        self.file_table.resizeColumnsToContents()
        self.file_table.show()
        for inst in self.files:
            inst.getFileLabel().setText(self.shorten_filename(inst.getFileName(), self.file_table.columnWidth(1)))

    def shorten_filename(self, name, width):
        '''根据给定的宽度截断文件名并添加...，返回截断后的文件名'''
        # 从第n个字符开始计算长度并添加...
        metrics = QFontMetrics(self.font())
        if metrics.width(name) > width - self.width / 128:
            for i in range(4, len(name)):
                if metrics.width(name[:i]) > width - self.width / 128:
                    return name[:i] + '...'
        return name
    
    def del_file(self, inst):
        '''按钮上绑定的删除事件：从当前表格中找到行索引并删除以及删除文件列表中的实例。'''
        index = self.findIndexByName(inst.getFileName())
        self.file_table.removeRow(index)
        self.files.remove(inst)
        if not self.files:
            self.file_table.hide()
            self.Lfile_empty.show()

    def fileChecker(self):
        '''文件列表检查及客户端传输进程开启'''
        if not self.files:
            msgBox = QMessageBox(self)
            msgBox.setWindowTitle('错误')
            msgBox.setIcon(QMessageBox.Warning)
            msgBox.setText('未选择文件！')
            msgBox.addButton('确定', QMessageBox.AcceptRole)
            msgBox.exec()
        else:
            # 从传输设置中调用同时传输的文件数及网络设定
            self.settings.beginGroup('ClientSetting')
            setting_file_at_same_time = int(self.settings.value('file_at_same_time', 2))
            setting_host = self.settings.value('host', '127.0.0.1')
            setting_port = int(self.settings.value('server_port', 12345))
            self.settings.endGroup()
            # 更改表格中文件行的状态
            for inst in self.files:
                inst.setFileStatus('uploading')
                index = self.findIndexByName(inst.getFileName())
                self.file_table.item(index, 4).setText('传输中')
            # 构建绝对路径列表并启动传输子进程
            path_list = [inst.getFilePath() for inst in self.files]
            self.file_sender = Process(target=client.thread_starter, args=(setting_host, setting_port, path_list, setting_file_at_same_time, self.que))
            self.file_sender.start()
            # 启动进度条更新
            self.timer = QTimer()
            self.timer.timeout.connect(self.updateProg)
            self.timer.start(5)
            
    def updateProg(self):
        '''传输过程管理及进度条更新'''
        try:
            # 无阻塞读取信息队列
            message = self.que.get(block=False)
            if message['type'] == 'info':
                # 从传输设置中调用是否删除源文件
                self.settings.beginGroup('ClientSetting')
                setting_del_source = int(self.settings.value('del_source', False))
                self.settings.endGroup()

                # 信息队列：依据MD5检查结果设置文件状态
                if message['message'] == 'MD5_passed':
                    self.findInstanceByName(message['name']).setFileStatus('complete')
                    self.file_table.item(self.findIndexByName(message['name']), 4).setText('传输完成')
                    if setting_del_source:
                        os.remove(self.findInstanceByName(message['name']).getFilePath())
                elif message['message'] == 'MD5_failed':
                    self.findInstanceByName(message['name']).setFileStatus('error')
                    self.file_table.item(self.findIndexByName(message['name']), 4).setText('传输错误')
                self.file_table.item(self.findIndexByName(message['name']), 2).setText('100 %')

                # 若无上传中的文件，关闭传输进程且提示完成结果
                if not self.findInstanceByStatus('uploading'):
                    self.file_sender.terminate()
                    while self.file_sender.is_alive():
                        time.sleep(0.1)
                    self.file_sender.close()
                    self.timer.stop()
                    if not self.findInstanceByStatus('error'):
                        msgBox = QMessageBox(self)
                        msgBox.setWindowTitle('成功')
                        msgBox.setIcon(QMessageBox.Information)
                        msgBox.setText('传输成功完成！')
                        msgBox.addButton('确定', QMessageBox.AcceptRole)
                        msgBox.exec()
                    else:
                        msgBox = QMessageBox(self)
                        msgBox.setWindowTitle('信息')
                        msgBox.setIcon(QMessageBox.Warning)
                        msgBox.setText('传输完成，但有文件传输出错！')
                        msgBox.addButton('确定', QMessageBox.AcceptRole)
                        msgBox.exec()
            elif message['type'] == 'prog':
                # 信息队列：更新进度条进度
                for inst in self.files:
                    if inst.getFileName() == message['name']:
                        inst.getFileProg().setValue(message['part'] + 1)
                        # 详细视图时还要更新进度百分比
                        if self.setting_detail_view:
                            file_prog = message['part'] / inst.getFileProg().maximum() * 100
                            index = self.findIndexByName(inst.getFileName())
                            self.file_table.item(index, 2).setText('{0:.2f} %'.format(file_prog))
        except queue.Empty:
            # 忽略空队列异常
            pass
    
    def safeClose(self):
        '''程序的关闭行为，触发closeEvent事件'''
        QCoreApplication.instance().quit
        self.close()
    
    def findInstanceByName(self, name):
        '''按文件名在文件列表中查找实例，没有返回None'''
        for inst in self.files:
            if inst.getFileName() == name:
                return inst
        return None

    def findInstanceByStatus(self, status):
        '''按文件状态在文件列表中查找实例，没有返回空列表'''
        inst_list = []
        for inst in self.files:
            if inst.getFileStatus() == status:
                inst_list.append(inst)
        return inst_list

    def findIndexByName(self, name):
        '''按文件名在表格视图中查找索引，没有返回None'''
        for i in range(self.file_table.rowCount()):
            if self.file_table.cellWidget(i, 1).layout().widget(1).toolTip() == name:
                return i
        return None

    def fileDialog(self):
        '''文件选择对话框，制作文件实例'''
        # 从配置文件中读取历史路径
        self.settings.beginGroup('Misc')
        setting_path_history = self.settings.value('path_history', '.')
        self.settings.endGroup()
        fname = QFileDialog.getOpenFileNames(self, '请选择文件', setting_path_history)
        if fname[0]:
            # 获取当前文件列表变量中的路径列表，排除相同文件
            path_list = [inst.getFilePath() for inst in self.files]
            for path in fname[0]:
                if path not in path_list:
                    self.files.append(FileStatus(path))
            self.Lfile_empty.hide()
            # 根据设置构建不同视图
            if not self.setting_detail_view:
                self.simple_viewer()
            else:
                self.detail_viewer()
            # 记录历史路径
            self.settings.beginGroup('Misc')
            self.settings.setValue('path_history', os.path.split(fname[0][-1])[0])
            self.settings.endGroup()
        self.settings.sync()

    def clientSettingDialog(self):
        '''客户端设置对话框'''
        self.clientsetting = ClientSettingDialog(self)
        self.clientsetting.show()
 
    def serverSettingDialog(self):
        '''服务端设置对话框'''
        self.serversetting = ServerSettingDialog(self)
        self.serversetting.show()

    def uiSettingDialog(self):
        '''UI设置对话框'''
        self.uisetting = UIDialog(self)
        self.uisetting.show()

    def closeEvent(self, event):
        '''程序关闭时触发'''
        # 记录关闭时的窗口尺寸
        self.settings.beginGroup('Misc')
        self.settings.setValue('window_size', (self.geometry().width(), self.geometry().height()))
        self.settings.endGroup()
        try:
            # 关闭服务器，进度计时器和传输子进程
            self.server_starter.kill()
            self.timer.stop()
            del self.timer
            self.file_sender.terminate()
            while self.file_sender.is_alive():
                time.sleep(0.1)
            self.file_sender.close()
        except ValueError:
            # 忽略传输子进程已关闭时的异常
            pass
        except AttributeError:
            # 忽略还未声明变量时的异常
            pass

    def keyPressEvent(self, k):
        '''按ESC时触发的关闭行为'''
        if k.key() == Qt.Key_Escape:
            self.safeClose()

    def resizeEvent(self, event):
        '''调整窗口尺寸时触发'''
        for inst in self.files:
            # 根据表格列宽调整截断文件名
            changed_text = self.shorten_filename(inst.getFileName(), self.file_table.columnWidth(1))
            inst.getFileLabel().setText(changed_text)

class ClientSettingDialog(QWidget):
    '''
    发送端设置对话框(模态)。
    包含设置：
    接收端网络IP和端口号设置；
    同时传输的文件数设置；
    是否删除源文件设置。
    '''
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.settings = QSettings(os.path.join(os.path.abspath('.'), 'settings.ini'), QSettings.IniFormat)
        self.initUI()

    def initUI(self):
        self.setWindowModality(Qt.ApplicationModal)
        self.resolution = QGuiApplication.primaryScreen().availableGeometry()
        self.height = self.resolution.height()
        self.width = self.resolution.width()
        self.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowCloseButtonHint)
        self.setFixedSize(self.width / 8, self.height / 5.4)
        qr = self.frameGeometry()
        qr.moveCenter(self.parent.geometry().center())
        self.move(qr.topLeft())
        
        self.settings.beginGroup('ClientSetting')
        self.Lserver_ip = QLabel('接收端IP')
        self.Eserver_ip = QLineEdit(self)
        setting_host = self.settings.value('host', '127.0.0.1')
        self.Eserver_ip.setText(setting_host)
        self.Eserver_ip.setContextMenuPolicy(Qt.NoContextMenu)
        self.Lserver_port = QLabel('端口号            ')
        self.Sserver_port = QSpinBox(self)
        self.Sserver_port.setRange(1024, 65535)
        self.Sserver_port.setWrapping(True)
        self.Sserver_port.setContextMenuPolicy(Qt.NoContextMenu)
        setting_server_port = int(self.settings.value('server_port', 12345))
        self.Sserver_port.setValue(setting_server_port)
        
        self.Gnet = QGroupBox('网络设置')
        net_form = QFormLayout()
        net_form.setSpacing(10)
        net_form.addRow(self.Lserver_ip, self.Eserver_ip)
        net_form.addRow(self.Lserver_port, self.Sserver_port)
        self.Gnet.setLayout(net_form)
        
        self.Lfile_num = QLabel('同时传输的文件数  ')
        self.Sfile_num = QSpinBox(self)
        self.Sfile_num.setRange(1, 3)
        self.Sfile_num.setWrapping(True)
        self.Sfile_num.setContextMenuPolicy(Qt.NoContextMenu)
        setting_file_num = int(self.settings.value('file_at_same_time', 2))
        self.Sfile_num.setValue(setting_file_num)
        self.Ldel_source = QLabel('完成后删除源文件')
        self.Cdel_source = QCheckBox(self)
        setting_del_source = int(self.settings.value('del_source', False))
        self.Cdel_source.setChecked(setting_del_source)
        self.settings.endGroup()
        
        self.Gtrans = QGroupBox('传输设置')
        trans_form = QFormLayout()
        trans_form.setSpacing(10)
        trans_form.addRow(self.Lfile_num, self.Sfile_num)
        trans_form.addRow(self.Ldel_source, self.Cdel_source)
        self.Gtrans.setLayout(trans_form)
        
        self.Bconfirm = QPushButton('确定', self)
        self.Bconfirm.setDefault(True)
        self.Bcancel = QPushButton('取消', self)
        self.Bconfirm.clicked.connect(self.store)
        self.Bcancel.clicked.connect(self.close)
        hbox = QHBoxLayout()
        hbox.addStretch(1)
        hbox.addWidget(self.Bconfirm)
        hbox.addWidget(self.Bcancel)
        hbox.addStretch(1)
        
        vbox = QVBoxLayout()
        vbox.setSpacing(20)
        vbox.addWidget(self.Gnet)
        vbox.addWidget(self.Gtrans)
        vbox.addLayout(hbox)
        self.setLayout(vbox)
        self.setWindowTitle('发送端设置')
    
    def store(self):
        # 双端端口号设置不能相同
        self.settings.beginGroup('ServerSetting')
        setting_bind_port = int(self.settings.value('bind_port', 54321))
        self.settings.endGroup()
        if self.Sserver_port.value() == setting_bind_port:
            msgBox = QMessageBox(self)
            msgBox.setWindowTitle('错误')
            msgBox.setIcon(QMessageBox.Warning)
            msgBox.setText('端口号冲突！\n请设置与接收端不同的端口号！')
            msgBox.addButton('确定', QMessageBox.AcceptRole)
            msgBox.exec()
        else:
            self.settings.beginGroup('ClientSetting')
            self.settings.setValue('host', self.Eserver_ip.text())
            self.settings.setValue('server_port', self.Sserver_port.value())
            self.settings.setValue('file_at_same_time', self.Sfile_num.value())
            self.settings.setValue('del_source', int(self.Cdel_source.isChecked()))
            self.settings.sync()
            self.settings.endGroup()
            self.close()
        
    def keyPressEvent(self, k):
        if k.key() == Qt.Key_Escape:
            self.close()

class ServerSettingDialog(QWidget):
    '''
    服务端设置对话框(模态)。
    包含设置：
    服务端IP及端口绑定；
    接收文件的保存位置。
    '''
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.settings = QSettings(os.path.join(os.path.abspath('.'), 'settings.ini'), QSettings.IniFormat)
        self.initUI()

    def initUI(self):
        self.setWindowModality(Qt.ApplicationModal)
        self.resolution = QGuiApplication.primaryScreen().availableGeometry()
        self.height = self.resolution.height()
        self.width = self.resolution.width()
        self.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowCloseButtonHint)
        self.setFixedSize(self.width / 8, self.height / 4.8)
        qr = self.frameGeometry()
        qr.moveCenter(self.parent.geometry().center())
        self.move(qr.topLeft())
        
        self.settings.beginGroup('ServerSetting')
        self.Lincoming_ip = QLabel('呼入IP')
        self.Eincoming_ip = QLineEdit(self)
        self.Eincoming_ip.setContextMenuPolicy(Qt.NoContextMenu)
        setting_incoming_ip = self.settings.value('incoming_ip', '0.0.0.0')
        self.Eincoming_ip.setText(setting_incoming_ip)
        self.Lbind_port = QLabel('绑定端口          ')
        self.Sbind_port = QSpinBox(self)
        self.Sbind_port.setRange(1024, 65535)
        self.Sbind_port.setWrapping(True)
        self.Sbind_port.setContextMenuPolicy(Qt.NoContextMenu)
        setting_bind_port = int(self.settings.value('bind_port', 54321))
        self.Sbind_port.setValue(setting_bind_port)

        self.Gnet = QGroupBox('网络设置')
        net_form = QFormLayout()
        net_form.setSpacing(10)
        net_form.addRow(self.Lincoming_ip, self.Eincoming_ip)
        net_form.addRow(self.Lbind_port, self.Sbind_port)
        self.Gnet.setLayout(net_form)
        
        self.Lopen_server = QLabel('接收端自启动      ')
        self.Copen_server = QCheckBox(self)
        setting_open_server = int(self.settings.value('open_server', True))
        self.Copen_server.setChecked(setting_open_server)
        self.Lreceive_dir = QLabel('文件保存目录')
        self.Breceive_dir = QPushButton('浏览')
        self.Breceive_dir.clicked.connect(self.chooseDir)
        self.Ereceive_dir = QLineEdit(self)
        self.Ereceive_dir.setReadOnly(True)
        self.Ereceive_dir.setContextMenuPolicy(Qt.NoContextMenu)
        setting_receive_dir = self.settings.value('receive_dir', os.path.abspath('.'))
        self.Ereceive_dir.setText(setting_receive_dir)
        self.settings.endGroup()
        
        self.Gtrans = QGroupBox('传输设置')
        trans_form = QFormLayout()
        trans_form.setSpacing(10)
        trans_form.addRow(self.Lopen_server, self.Copen_server)
        trans_form.addRow(self.Lreceive_dir, self.Breceive_dir)
        trans_form.addRow(self.Ereceive_dir)
        self.Gtrans.setLayout(trans_form)
        
        self.Bconfirm = QPushButton('确定', self)
        self.Bconfirm.setDefault(True)
        self.Bcancel = QPushButton('取消', self)
        self.Bconfirm.clicked.connect(self.store)
        self.Bcancel.clicked.connect(self.close)
        hbox = QHBoxLayout()
        hbox.addStretch(1)
        hbox.addWidget(self.Bconfirm)
        hbox.addWidget(self.Bcancel)
        hbox.addStretch(1)
        
        vbox = QVBoxLayout()
        vbox.setSpacing(20)
        vbox.addWidget(self.Gnet)
        vbox.addWidget(self.Gtrans)
        vbox.addLayout(hbox)
        self.setLayout(vbox)
        self.setWindowTitle('接收端设置')
    
    def store(self):
        self.settings.beginGroup('ClientSetting')
        setting_server_port = int(self.settings.value('server_port', 12345))
        self.settings.endGroup()
        if self.Sbind_port.value() == setting_server_port:
            msgBox = QMessageBox(self)
            msgBox.setWindowTitle('错误')
            msgBox.setIcon(QMessageBox.Warning)
            msgBox.setText('端口号冲突！\n请设置与发送端不同的端口号！')
            msgBox.addButton('确定', QMessageBox.AcceptRole)
            msgBox.exec()
        else:
            self.settings.beginGroup('ServerSetting')
            self.settings.setValue('incoming_ip', self.Eincoming_ip.text())
            self.settings.setValue('bind_port', self.Sbind_port.value())
            self.settings.setValue('open_server', int(self.Copen_server.isChecked()))
            self.settings.setValue('receive_dir', self.Ereceive_dir.text())
            self.settings.sync()
            self.settings.endGroup()
            self.close()
    
    def chooseDir(self):
        self.settings.beginGroup('ServerSetting')
        path = QFileDialog.getExistingDirectory(self, '选择目录', self.Ereceive_dir.text())
        if path:
            self.Ereceive_dir.setText(path)
        self.settings.endGroup()
    
    def keyPressEvent(self, k):
        if k.key() == Qt.Key_Escape:
            self.close()

class UIDialog(QWidget):
    '''
    界面设置对话框(模态)。
    包含是否启用详细视图设置。
    '''
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.settings = QSettings(os.path.join(os.path.abspath('.'), 'settings.ini'), QSettings.IniFormat)
        self.initUI()

    def initUI(self):
        self.setWindowModality(Qt.ApplicationModal)
        self.resolution = QGuiApplication.primaryScreen().availableGeometry()
        self.height = self.resolution.height()
        self.width = self.resolution.width()
        self.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowCloseButtonHint)
        self.setFixedSize(self.width / 8, self.height / 14.4)
        qr = self.frameGeometry()
        qr.moveCenter(self.parent.geometry().center())
        self.move(qr.topLeft())
        
        self.settings.beginGroup('UISetting')
        self.Lview = QLabel('启用详细视图(重启生效)')
        self.Cview = QCheckBox(self)
        setting_view = int(self.settings.value('detail_view', False))
        self.Cview.setChecked(setting_view)
        self.settings.endGroup()
        
        self.Bconfirm = QPushButton('确定', self)
        self.Bconfirm.setDefault(True)
        self.Bcancel = QPushButton('取消', self)
        
        self.Bconfirm.clicked.connect(self.store)
        self.Bcancel.clicked.connect(self.close)
        
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
        self.settings.setValue('detail_view', int(self.Cview.isChecked()))
        self.settings.sync()
        self.settings.endGroup()
        self.close()
        
    def keyPressEvent(self, k):
        if k.key() == Qt.Key_Escape:
            self.close()
            
if __name__ == '__main__':
    # 主程序入口
    app = QApplication(sys.argv)
    window = ClientWindow()
    sys.exit(app.exec())