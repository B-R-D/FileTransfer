# coding:utf-8
"""UDP客户端GUI版"""
# 改进：增加传输中和程序退出前提示取消功能
import functools
import os
import queue
import sys
from multiprocessing import Process, Queue

from PyQt5.QtCore import Qt, QSettings, QTimer
from PyQt5.QtGui import QFont, QFontMetrics, QIcon, QGuiApplication, QTextCursor
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QStackedLayout, QMainWindow, QApplication
from PyQt5.QtWidgets import QPushButton, QLabel, QFileDialog, QAction, QMessageBox, QProgressBar, QFrame, QSplitter
from PyQt5.QtWidgets import QWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QTableWidget

import chat_client
import def_widget
import server
import trans_client


class FileStatus:
    """
    定义所需的基本文件信息类。
    可获取类属性：文件路径，文件名，状态按钮，进度条，文件名标签；
    包含属性装饰器：文件大小（只读），文件状态（读写）。
    """

    def __init__(self, path):
        self.path = path
        self.name = os.path.split(self.path)[1]
        self._size = os.path.getsize(self.path)
        self._all = self._size // 65000 + 1
        self._status = ['pending', '等待传输']

        picname = self._status[0] + '.png'
        self.button = QPushButton(QIcon(os.path.join('icon', picname)), '')
        self.button.setToolTip(self._status[1])
        self.button.setFlat(True)

        self.prog = QProgressBar()
        self.prog.setTextVisible(False)
        self.prog.setRange(0, self._all)

        self.label = QLabel(self.name)
        self.label.setToolTip(self.name)

    @property
    def size(self):
        return trans_client.display_file_length(self._size)

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, new_status):
        """根据新设置的状态切换按钮图片及tooltip"""
        status = {'pending': '等待传输', 'error': '传输错误', 'complete': '传输完成', 'uploading': '传输中'}
        self._status[0] = new_status
        self._status[1] = status[self._status[0]]
        picname = self._status[0] + '.png'
        self.button.setIcon(QIcon(os.path.join('icon', picname)))
        self.button.setToolTip(self._status[1])


class ClientWindow(QMainWindow):
    """
    GUI主窗口类。
    """

    def __init__(self):
        super().__init__()
        # 初始化发送端文件列表：待发送及待删除
        self.files = []
        self.del_list = []
        # 初始化接收端文件列表：已接收/成功/失败
        self.received_files = []
        self.succeed_files = []
        self.failed_files = []
        # 初始化进程间通信队列和传输中断标志
        self.client_que = Queue()
        self.server_que = Queue()
        self.aborted = False
        # 初始化设置文件
        self.settings = QSettings(os.path.join(os.path.abspath('.'), 'settings.ini'), QSettings.IniFormat)
        # 初始化字体
        self.setFont(QFont('Arial', 10))
        # 屏幕分辨率信息
        self.resolution = QGuiApplication.primaryScreen().availableGeometry()
        self.reso_height = self.resolution.height()
        self.reso_width = self.resolution.width()
        self.init_ui()

    def init_ui(self):
        # 恢复上次关闭时的窗口尺寸
        self.settings.beginGroup('Misc')
        setting_window_size = self.settings.value('window_size', (self.reso_height / 6.4, self.reso_width / 2.7))
        self.settings.endGroup()
        self.resize(setting_window_size[0], setting_window_size[1])
        # 在屏幕中央(不含开始菜单栏)打开窗口
        self.frameGeometry().moveCenter(self.resolution.center())

        # 定义文件传输区域及消息传输区域
        self.sender_frame = QFrame()
        self.chat_frame = QFrame()
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(self.reso_width / 384)
        self.splitter.splitterMoved.connect(self.resizeEvent)
        self.splitter.addWidget(self.sender_frame)
        self.splitter.addWidget(self.chat_frame)
        self.splitter.handle(1).setStyleSheet('QSplitterHandle{background-color: rgb(210,210,210)}')

        # 定义窗口主控件
        self.setCentralWidget(self.splitter)
        # 定义菜单栏：文件，设置
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu('文件(&F)')
        self.act_choose = QAction('选择文件(&C)', self)
        self.act_send = QAction('发送(&S)', self)
        self.act_stop_send = QAction('中止传输(&E)', self)
        self.act_exit = QAction('退出(&Q)', self)

        file_menu.addAction(self.act_choose)
        file_menu.addAction(self.act_send)
        file_menu.addAction(self.act_stop_send)
        file_menu.addSeparator()
        file_menu.addAction(self.act_exit)
        self.act_choose.triggered.connect(self.file_dialog)
        self.act_send.setDisabled(True)
        self.act_send.triggered.connect(self.file_checker)
        self.act_stop_send.setDisabled(True)
        self.act_stop_send.triggered.connect(self.abort_trans)
        self.act_exit.triggered.connect(self.close)

        setting_menu = menu_bar.addMenu('设置(&S)')
        act_client = QAction('发送端设置(&C)', self)
        act_server = QAction('接收端设置(&S)', self)
        act_ui = QAction('界面设置(&U)', self)

        setting_menu.addAction(act_client)
        setting_menu.addAction(act_server)
        setting_menu.addAction(act_ui)
        act_client.triggered.connect(self.client_setting_dialog)
        act_server.triggered.connect(self.server_setting_dialog)
        act_ui.triggered.connect(self.ui_setting_dialog)

        # 创建状态栏
        self.status_bar = self.statusBar()
        self.status_bar.setSizeGripEnabled(False)
        self.Lclient_status = QLabel('发送端已就绪')
        self.Lserver_status = QLabel('接收端未启动')
        self.status_bar.addWidget(self.Lclient_status, 1)
        self.status_bar.addWidget(self.Lserver_status, 1)

        # 定义传输控件：选择按钮(默认按钮)，空区域(左上对齐)，文件列表(单元格不可选择)，发送按钮
        self.Bselector = QPushButton('选择文件', self)
        self.Bselector.setDefault(True)
        self.Bselector.clicked.connect(self.file_dialog)
        self.Lfile_empty = QLabel('未选中文件')
        self.Lfile_empty.setAlignment(Qt.AlignTop)
        self.file_table = QTableWidget()
        self.file_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.file_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.file_table.verticalScrollBar().setStyleSheet('QScrollBar{{width:{}px;}}'.format(self.reso_width / 192))
        self.file_table.verticalScrollBar().setContextMenuPolicy(Qt.NoContextMenu)
        self.file_table.verticalHeader().setSectionsClickable(False)
        self.file_table.horizontalHeader().setSectionsClickable(False)
        self.file_table.hide()
        self.Bfile_sender = QPushButton('发送', self)
        self.Bfile_sender.setDisabled(True)
        self.Bfile_sender.clicked.connect(self.file_checker)

        # 定义传输区域垂直布局
        self.vbox = QVBoxLayout()
        self.vbox.setSpacing(self.reso_height / 70)
        self.vbox.addWidget(self.Bselector)
        self.vbox.addWidget(self.file_table)
        self.vbox.addWidget(self.Lfile_empty)
        self.vbox.addWidget(self.Bfile_sender)
        self.sender_frame.setLayout(self.vbox)

        # 定义消息控件：消息显示区域，发送文本框，发送/收起按钮
        self.Emessage_area = def_widget.MessageDisplayEdit(self)
        self.Emessage_area.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.Emessage_area.setReadOnly(True)
        self.Emessage_writer = def_widget.MessageWriter(self)
        self.Emessage_writer.setPlaceholderText('输入消息')
        self.Emessage_writer.returnPressed.connect(self.chat_checker)
        self.Bfolder = QPushButton('<< 收起', self)
        self.Bfolder.clicked.connect(functools.partial(self.splitter.setSizes, [self.geometry().width(), 0]))
        self.Bmessage_sender = QPushButton('发送', self)
        self.Bmessage_sender.clicked.connect(self.chat_checker)

        # 定义消息区域垂直布局
        self.chat_vbox = QVBoxLayout()
        self.chat_vbox.setSpacing(self.reso_height / 70)
        self.chat_vbox.addWidget(self.Emessage_area)
        self.chat_vbox.addWidget(self.Emessage_writer)
        self.chat_hbox = QHBoxLayout()
        self.chat_hbox.addWidget(self.Bfolder)
        self.chat_hbox.addStretch(1)
        self.chat_hbox.addWidget(self.Bmessage_sender)
        self.chat_vbox.addLayout(self.chat_hbox)
        self.chat_frame.setLayout(self.chat_vbox)

        # 从设置中读取视图设定并设定窗口最小值
        self.settings.beginGroup('UISetting')
        self.setting_detail_view = int(self.settings.value('detail_view', False))
        self.settings.endGroup()
        if not self.setting_detail_view:
            self.sender_frame.setMinimumWidth(self.reso_width / 7.68)
        else:
            self.sender_frame.setMinimumWidth(self.reso_width / 6)
        self.ui_setting_checker()
        self.settings.beginGroup('Misc')
        self.setting_frame_width = self.settings.value('frame_width', (self.geometry().width(), 0))
        self.settings.endGroup()
        self.splitter.setSizes([self.setting_frame_width[0], self.setting_frame_width[1]])
        self.setWindowTitle('FileTransfer')
        self.show()

        # 按设置启动服务端
        self.settings.beginGroup('ServerSetting')
        setting_open_server = int(self.settings.value('open_server', True))
        self.settings.endGroup()
        if setting_open_server:
            self.Lserver_status.setText('接收端启动中')
            self.settings.beginGroup('ServerSetting')
            setting_incoming_ip = self.settings.value('incoming_ip', '0.0.0.0')
            setting_bind_port = int(self.settings.value('bind_port', 54321))
            setting_receive_dir = self.settings.value('receive_dir', os.path.abspath('.'))
            self.settings.endGroup()
            self.server_starter = Process(target=server.starter, args=(
                setting_incoming_ip, setting_bind_port, setting_receive_dir, self.server_que))
            self.server_starter.start()
            # 循环读取服务端信息
            self.server_timer = QTimer()
            self.server_timer.timeout.connect(self.server_status)
            self.server_timer.start(100)

    def simple_viewer(self, add_files):
        """简明视图：按钮及进度条"""
        # 设置简明视图样式：无框线，水平抬头不可见，按钮列自适应，文件名列宽自适应留白
        self.file_table.setColumnCount(2)
        row = len(self.files) + len(add_files)
        self.file_table.setRowCount(row)
        self.file_table.setShowGrid(False)
        self.file_table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.file_table.horizontalHeader().setVisible(False)
        self.file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.file_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

        num = 0
        for inst in add_files:
            prog_widget = QWidget()
            prog_stack = QStackedLayout()
            prog_stack.addWidget(inst.prog)
            prog_stack.addWidget(inst.label)
            prog_stack.setStackingMode(QStackedLayout.StackAll)
            prog_widget.setLayout(prog_stack)

            inst.button.clicked.connect(functools.partial(self.del_file, inst))
            inst.button.pressed.connect(self.button_pressed)
            inst.button.released.connect(self.button_released)

            index = num + len(self.files)
            num += 1
            self.file_table.setCellWidget(index, 0, inst.button)
            self.file_table.setCellWidget(index, 1, prog_widget)
        self.files += add_files
        self.file_table.show()
        # 表格显示后截断文件名
        for inst in self.files:
            inst.label.setText(self.shorten_filename(inst.name, self.file_table.columnWidth(1)))

    def detail_viewer(self, add_files):
        """详细视图：包括按钮、进度条、详细分片进度、文件大小、状态"""
        self.file_table.setColumnCount(5)
        row = len(self.files) + len(add_files)
        self.file_table.setRowCount(row)
        self.file_table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.file_table.setHorizontalHeaderLabels(['', '文件名', '传输进度', '文件大小', '状态'])
        # 要用表头的ResizeMode函数而不能用列的ResizeMode函数
        self.file_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.file_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

        num = 0
        for inst in add_files:
            prog_stack = QStackedLayout()
            prog_stack.addWidget(inst.prog)
            prog_stack.addWidget(inst.label)
            prog_stack.setStackingMode(QStackedLayout.StackAll)
            prog_widget = QWidget()
            prog_widget.setLayout(prog_stack)
            # 定义按钮点击删除，长按全清的行为
            inst.button.clicked.connect(functools.partial(self.del_file, inst))
            inst.button.pressed.connect(self.button_pressed)
            inst.button.released.connect(self.button_released)

            # 设置各单元格样式：居中
            file_prog = QTableWidgetItem('0.00 %')
            file_prog.setTextAlignment(Qt.AlignCenter)
            file_size = QTableWidgetItem(inst.size)
            file_size.setTextAlignment(Qt.AlignCenter)
            file_status = QTableWidgetItem(inst.status[1])
            file_status.setTextAlignment(Qt.AlignCenter)

            index = num + len(self.files)
            num += 1
            self.file_table.setCellWidget(index, 0, inst.button)
            self.file_table.setCellWidget(index, 1, prog_widget)
            self.file_table.setItem(index, 2, file_prog)
            self.file_table.setItem(index, 3, file_size)
            self.file_table.setItem(index, 4, file_status)
        self.files += add_files
        self.file_table.show()
        # 计算是否出现滚动条
        # 能否优化为判断当前是否有滚动条后跳过执行？
        row_height = self.file_table.rowHeight(0) * self.file_table.rowCount()
        header_height = self.file_table.horizontalHeader().height()
        if row_height + header_height >= self.file_table.height():
            for inst in self.files:
                changed_text = self.shorten_filename(inst.name, self.file_table.columnWidth(1) - self.reso_width / 192)
                inst.label.setText(changed_text)
        else:
            for inst in self.files:
                changed_text = self.shorten_filename(inst.name, self.file_table.columnWidth(1))
                inst.label.setText(changed_text)

    def button_pressed(self):
        self.settings.beginGroup('ClientSetting')
        setting_del_timeout = float(self.settings.value('del_timeout', 1))
        self.settings.endGroup()
        self.button_timer = QTimer()
        self.button_timer.timeout.connect(self.remove_all)
        self.button_timer.setSingleShot(True)
        self.button_timer.start(setting_del_timeout * 1000)

    def button_released(self):
        self.button_timer.stop()

    def remove_all(self):
        # 批量删除时需要从末尾开始逐个删除
        for i in range(len(self.files), 0, -1):
            self.del_file(self.files[i - 1])

    def shorten_filename(self, name, width):
        """根据给定的宽度截断文件名并添加...，返回截断后的文件名"""
        # 从第n个字符开始计算长度并添加...
        metrics = QFontMetrics(self.font())
        if metrics.width(name) > width - self.reso_width / 128:
            for i in range(4, len(name)):
                if metrics.width(name[:i]) > width - self.reso_width / 128:
                    return name[:i] + '...'
        return name

    def del_file(self, inst):
        """按钮上绑定的删除事件：从当前表格中找到行索引并删除以及删除文件列表中的实例。"""
        index = self.find_index_by_name(inst.name)
        self.file_table.removeRow(index)
        self.files.remove(inst)
        if not self.files:
            self.file_table.hide()
            self.Lfile_empty.show()
            self.act_send.setDisabled(True)
            self.Bfile_sender.setDisabled(True)

    def chat_checker(self):
        if self.Emessage_writer.text():
            self.settings.beginGroup('ClientSetting')
            setting_host = self.settings.value('host', '127.0.0.1')
            setting_port = int(self.settings.value('server_port', 12345))
            self.settings.endGroup()
            # 如有上个消息没发完就发新消息则结束掉上个子进程
            try:
                if self.chat_sender.is_alive():
                    self.chat_sender.terminate()
                    self.chat_sender.join()
                    self.Emessage_area.moveCursor(QTextCursor.End)
                    self.Emessage_area.insertHtml('<font color=red>✘<font color=black> ')
            except AttributeError:
                pass
            self.Emessage_area.append('本机(localhost)：\n    {0} '.format(self.Emessage_writer.text()))
            # 由于客户端的消息队列只在发送时读取，必须传入服务器的消息队列
            self.chat_sender = Process(target=chat_client.chat_starter,
                                       args=(setting_host, setting_port, self.Emessage_writer.text(), self.server_que))
            self.chat_sender.start()
            self.Emessage_writer.clear()

    def file_checker(self):
        """文件列表检查及客户端传输进程开启"""
        self.ui_sending()
        self.aborted = False
        # 从传输设置中调用同时传输的文件数及网络设定
        self.settings.beginGroup('ClientSetting')
        setting_file_at_same_time = int(self.settings.value('file_at_same_time', 2))
        setting_host = self.settings.value('host', '127.0.0.1')
        setting_port = int(self.settings.value('server_port', 12345))
        self.settings.endGroup()
        # 更改表格中文件行的状态
        for inst in self.files:
            inst.status = 'uploading'
            inst.prog.setValue(0)
            index = self.find_index_by_name(inst.name)
            self.file_table.item(index, 4).setText('传输中')
        # 构建绝对路径列表并启动传输子进程，无法启动的异常反映在状态栏
        path_list = [inst.path for inst in self.files]
        try:
            self.file_sender = Process(target=trans_client.file_thread, args=(
                setting_host, setting_port, path_list, setting_file_at_same_time, self.client_que))
            self.file_sender.start()
            self.Lclient_status.setText(
                '''传输中：<font color=green>0<font color=black>/<font color=red>0<font color=black>/{0} 
                (<font color=green>Comp<font color=black>/<font color=red>Err<font color=black>/Up)'''.format(
                    len(self.find_instance_by_status('uploading'))))
        except Exception as e:
            self.Lclient_status.setText(repr(e))
        # 启动进度条更新
        self.prog_timer = QTimer()
        self.prog_timer.timeout.connect(self.update_prog)
        self.prog_timer.start(5)

    def ui_sending(self):
        """传输前UI处理函数"""
        self.act_choose.setDisabled(True)
        self.act_send.setDisabled(True)
        self.act_stop_send.setDisabled(False)
        self.Bselector.setDisabled(True)
        self.Bfile_sender.setText('中止传输')
        self.Bfile_sender.clicked.disconnect(self.file_checker)
        self.Bfile_sender.clicked.connect(self.abort_trans)
        # 删除按钮不可用
        for inst in self.files:
            inst.button.setDisabled(True)

    def ui_pending(self):
        self.act_choose.setDisabled(False)
        self.act_stop_send.setDisabled(True)
        self.Bselector.setDisabled(False)
        self.Bfile_sender.setText('发送')
        self.Bfile_sender.clicked.disconnect(self.abort_trans)
        self.Bfile_sender.clicked.connect(self.file_checker)
        # 删除按钮可用
        for inst in self.files:
            inst.button.setDisabled(False)

    def abort_trans(self):
        """中断传输后发送取消消息"""
        try:
            print('结束file_sender')
            self.file_sender.terminate()
            self.file_sender.join()
            self.file_sender.close()
            del self.file_sender
        except ValueError:
            pass
        except AttributeError:
            pass
        # 从传输设置中调用网络设定
        self.settings.beginGroup('ClientSetting')
        setting_host = self.settings.value('host', '127.0.0.1')
        setting_port = int(self.settings.value('server_port', 12345))
        self.settings.endGroup()
        print('开启子进程abort_sender')
        self.abort_sender = Process(target=trans_client.file_thread,
                                    args=(setting_host, setting_port, '', None, self.client_que))
        self.abort_sender.start()
        self.abort_sender.join()
        self.abort_sender.close()
        del self.abort_sender

    def update_prog(self):
        """传输过程管理及进度条更新"""
        try:
            # 无阻塞读取信息队列
            message = self.client_que.get(block=False)
            inst = self.find_instance_by_name(message['name'])
            # index不直接计算考虑了简明视图的性能
            if message['type'] == 'info':
                index = self.find_index_by_name(message['name'])
                # 信息队列：依据MD5检查结果设置文件状态
                if message['message'] == 'MD5_passed':
                    inst.status = 'complete'
                    self.file_table.item(index, 4).setText('传输完成')
                    self.file_table.item(index, 2).setText('100 %')
                    self.del_list.append(inst.path)
                elif message['message'] == 'MD5_failed':
                    inst.status = 'error'
                    self.file_table.item(index, 4).setText('传输错误')
                    self.file_table.item(index, 2).setText('100 %')
                elif message['message'] == 'aborted':
                    # 需要设置中断标志位供closeEvent检查
                    print('服务端已中断', message)
                    self.aborted = True
                    self.ui_pending()

                # 若无上传中的文件，关闭传输进程，清空上传列表且提示完成结果
                if not self.find_instance_by_status('uploading'):
                    self.Lclient_status.setText(
                        '''传输完成：<font color=green>{0}<font color=black>/<font color=red>{1}<font color=black>/0 
                        (<font color=green>Comp<font color=black>/<font color=red>Err<font color=black>/Up)'''.format(
                            len(self.find_instance_by_status('complete')), len(self.find_instance_by_status('error'))))
                    self.file_sender.terminate()
                    self.file_sender.join()
                    self.file_sender.close()
                    self.prog_timer.stop()
                    # del_list不为空则考虑是否删除源文件
                    if self.del_list:
                        self.settings.beginGroup('ClientSetting')
                        setting_del_source = int(self.settings.value('del_source', False))
                        self.settings.endGroup()
                        if setting_del_source:
                            msg_box = QMessageBox(self)
                            msg_box.setWindowTitle('成功')
                            msg_box.setIcon(QMessageBox.Information)
                            msg_box.setText('传输成功完成！\n点击确定删除源文件')
                            msg_box.addButton('确定', QMessageBox.AcceptRole)
                            msg_box.addButton('取消', QMessageBox.DestructiveRole)
                            reply = msg_box.exec()
                            if reply == QMessageBox.AcceptRole:
                                self.remove_all()
                                for path in self.del_list:
                                    try:
                                        os.remove(path)
                                    except Exception as e:
                                        msg_box = QMessageBox(self)
                                        msg_box.setWindowTitle('错误')
                                        msg_box.setIcon(QMessageBox.Critical)
                                        msg_box.setInformativeText('无法删除\n{0}'.format(path))
                                        msg_box.setText(repr(e))
                                        msg_box.addButton('确定', QMessageBox.AcceptRole)
                                        msg_box.exec()
                        else:
                            msg_box = QMessageBox(self)
                            msg_box.setWindowTitle('成功')
                            msg_box.setIcon(QMessageBox.Information)
                            msg_box.setText('传输成功完成！')
                            msg_box.addButton('确定', QMessageBox.AcceptRole)
                            msg_box.exec()
                    else:
                        msg_box = QMessageBox(self)
                        msg_box.setWindowTitle('信息')
                        msg_box.setIcon(QMessageBox.Warning)
                        msg_box.setText('传输完成，但有文件传输出错！')
                        msg_box.addButton('确定', QMessageBox.AcceptRole)
                        msg_box.exec()
                    # 恢复界面UI
                    self.ui_pending()
                else:
                    self.Lclient_status.setText(
                        '''传输中：<font color=green>{0}<font color=black>/<font color=red>{1}<font color=black>/{2} 
                        (<font color=green>Comp<font color=black>/<font color=red>Err<font color=black>/Up)'''.format(
                            len(self.find_instance_by_status('complete')), len(self.find_instance_by_status('error')),
                            len(self.find_instance_by_status('uploading'))))
            elif message['type'] == 'prog':
                inst.prog.setValue(message['part'] + 1)
                # 详细视图时还要更新进度百分比
                if self.setting_detail_view:
                    index = self.find_index_by_name(message['name'])
                    file_prog = message['part'] / inst.prog.maximum() * 100
                    self.file_table.item(index, 2).setText('{0:.2f} %'.format(file_prog))
        except queue.Empty:
            # 忽略空队列异常
            pass

    def server_status(self):
        """启动时循环读取服务端状态及更新聊天信息"""
        try:
            message = self.server_que.get(block=False)
            if message['type'] == 'server_info':
                if message['message'] == 'error':
                    self.Lserver_status.setText(message['detail'])
                elif message['message'] == 'ready':
                    self.Lserver_status.setText('服务端已就绪')
                elif message['message'] == 'MD5_passed':
                    self.succeed_files.append(message['message'])
                    self.Lserver_status.setText(
                        '''{0}=<font color=green>{1}<font color=black>+<font color=red>{2}<font color=black> 
                        (Tol=<font color=green>Comp<font color=black>+<font color=red>Err<font color=black>)'''.format(
                            len(self.received_files), len(self.succeed_files), len(self.failed_files)))
                elif message['message'] == 'MD5_failed':
                    self.failed_files.append(message['message'])
                    self.Lserver_status.setText(
                        '''{0}=<font color=green>{1}<font color=black>+<font color=red>{2}<font color=black> 
                        (Tol=<font color=green>Comp<font color=black>+<font color=red>Err<font color=black>)'''.format(
                            len(self.received_files), len(self.succeed_files), len(self.failed_files)))
                elif message['message'] == 'started':
                    self.received_files.append(message['message'])
                    self.Lserver_status.setText(
                        '''{0}=<font color=green>{1}<font color=black>+<font color=red>{2}<font color=black> 
                        (Tol=<font color=green>Comp<font color=black>+<font color=red>Err<font color=black>)'''.format(
                            len(self.received_files), len(self.succeed_files), len(self.failed_files)))
            elif message['type'] == 'chat':
                if message['status'] == 'success':
                    self.chat_sender.terminate()
                    self.chat_sender.join()
                    self.Emessage_area.moveCursor(QTextCursor.End)
                    self.Emessage_area.insertHtml('<font color=green>✓<font color=black> ')
                elif message['status'] == 'failed':
                    self.chat_sender.terminate()
                    self.chat_sender.join()
                    self.Emessage_area.moveCursor(QTextCursor.End)
                    self.Emessage_area.insertHtml('<font color=red>✘<font color=black> ')
                elif message['status'] == 'received':
                    self.Emessage_area.append(
                        '{0}:{1}：\n    {2}'.format(message['from'][0], message['from'][1], message['message']))
                    self.Lserver_status.setText('收到来自{0}:{1}的聊天消息'.format(message['from'][0], message['from'][1]))
        except queue.Empty:
            pass

    def ui_setting_checker(self):
        self.settings.beginGroup('UISetting')
        setting_status_bar = int(self.settings.value('status_bar', True))
        setting_chat_frame = int(self.settings.value('chat_frame', True))
        self.settings.endGroup()
        if setting_status_bar:
            self.status_bar.show()
        else:
            self.status_bar.hide()
        if setting_chat_frame:
            self.chat_frame.show()
        else:
            self.chat_frame.hide()

    def safe_close(self):
        """结束子进程及计时器"""
        print('进入safe_close')
        try:
            # 关闭服务器，进度计时器和传输子进程
            self.server_timer.stop()
            del self.server_timer
            self.server_starter.terminate()
            self.server_starter.join()
            self.server_starter.close()
            self.prog_timer.stop()
            del self.prog_timer
            self.file_sender.terminate()
            self.file_sender.join()
            self.file_sender.close()
        except ValueError:
            # 忽略传输子进程已关闭时的异常
            pass
        except AttributeError:
            # 忽略还未声明变量时的异常
            pass
        try:
            # 关闭聊天子进程
            self.chat_sender.terminate()
            self.chat_sender.join()
            self.chat_sender.close()
        except ValueError:
            pass
        except AttributeError:
            pass

    def find_instance_by_name(self, name):
        """按文件名在文件列表中查找实例，没有返回None"""
        for inst in self.files:
            if inst.name == name:
                return inst
        return None

    def find_instance_by_status(self, status):
        """按文件状态在文件列表中查找实例，没有返回空列表"""
        inst_list = []
        for inst in self.files:
            if inst.status[0] == status:
                inst_list.append(inst)
        return inst_list

    def find_index_by_name(self, name):
        """按文件名在表格视图中查找索引，没有返回None"""
        row = self.file_table.rowCount()
        for i in range(row):
            if self.file_table.cellWidget(i, 1).layout().widget(1).toolTip() == name:
                return i
        return None

    def file_dialog(self):
        """文件选择对话框，制作文件实例"""
        # 从配置文件中读取历史路径
        self.settings.beginGroup('Misc')
        setting_path_history = self.settings.value('path_history', '.')
        self.settings.endGroup()
        fname = QFileDialog.getOpenFileNames(self, '请选择文件', setting_path_history)
        if fname[0]:
            # 用集合set求新增文件路径列表
            new_list = set(fname[0])
            old_list = {inst.path for inst in self.files}
            add_list = new_list - old_list
            # 纯新增文件列表
            add_files = [FileStatus(path) for path in add_list]
            self.Lfile_empty.hide()
            # 根据设置构建不同视图
            if not self.setting_detail_view:
                self.simple_viewer(add_files)
            else:
                self.detail_viewer(add_files)
            # 改变发送UI
            self.Bfile_sender.setDisabled(False)
            self.act_send.setDisabled(False)
            # 记录历史路径
            self.settings.beginGroup('Misc')
            self.settings.setValue('path_history', os.path.split(fname[0][-1])[0])
            self.settings.endGroup()
        self.settings.sync()

    def client_setting_dialog(self):
        """客户端设置对话框"""
        self.client_setting = def_widget.ClientSettingDialog(self)
        self.client_setting.setAttribute(Qt.WA_DeleteOnClose)
        self.client_setting.show()

    def server_setting_dialog(self):
        """服务端设置对话框"""
        self.server_setting = def_widget.ServerSettingDialog(self)
        self.server_setting.setAttribute(Qt.WA_DeleteOnClose)
        self.server_setting.show()

    def ui_setting_dialog(self):
        """UI设置对话框"""
        self.ui_setting = def_widget.UIDialog(self)
        self.ui_setting.setAttribute(Qt.WA_DeleteOnClose)
        self.ui_setting.destroyed.connect(self.ui_setting_checker)
        self.ui_setting.show()

    def closeEvent(self, event):
        """关闭前检查是否有传输中的文件"""
        print('进关闭事件了')
        if self.find_instance_by_status('uploading'):
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle('警告')
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setText('文件传输中，是否中断并退出？')
            msg_box.addButton('确定', QMessageBox.AcceptRole)
            msg_box.addButton('取消', QMessageBox.DestructiveRole)
            reply = msg_box.exec()
            if reply == QMessageBox.AcceptRole:
                self.abort_trans()
                # 记录关闭时的窗口尺寸
                self.settings.beginGroup('Misc')
                self.settings.setValue('window_size', (self.geometry().width(), self.geometry().height()))
                self.settings.setValue('frame_width', (self.sender_frame.width(), self.chat_frame.width()))
                self.settings.endGroup()
                self.settings.sync()
                print('等待服务端中断信号')
                while self.aborted:
                    print('中断成功，退出程序')
                    self.safe_close()
                    event.accept()
            else:
                event.ignore()
        else:
            # 记录关闭时的窗口尺寸
            self.settings.beginGroup('Misc')
            self.settings.setValue('window_size', (self.geometry().width(), self.geometry().height()))
            self.settings.setValue('frame_width', (self.sender_frame.width(), self.chat_frame.width()))
            self.settings.endGroup()
            self.settings.sync()
            self.safe_close()
            event.accept()

    def keyPressEvent(self, k):
        """按ESC时触发的关闭行为"""
        if k.key() == Qt.Key_Escape:
            self.close()

    def resizeEvent(self, event):
        """调整窗口尺寸时触发"""
        for inst in self.files:
            # 根据表格列宽调整截断文件名
            changed_text = self.shorten_filename(inst.name, self.file_table.columnWidth(1))
            inst.label.setText(changed_text)


if __name__ == '__main__':
    # 主程序入口
    app = QApplication(sys.argv)
    window = ClientWindow()
    sys.exit(app.exec())
