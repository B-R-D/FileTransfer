# coding:utf-8
"""
自定义的QT控件集
聊天显示/输入框；
"""
import os

from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtWidgets import QMessageBox, QSpinBox, QCheckBox, QGroupBox, QDoubleSpinBox
from PyQt5.QtWidgets import QPushButton, QLabel, QFileDialog, QLineEdit, QTextEdit, QMenu
from PyQt5.QtWidgets import QWidget, QFormLayout, QHBoxLayout, QVBoxLayout


class MessageDisplayEdit(QTextEdit):
    def __init__(self, parent):
        super().__init__(parent)
        self.copy_flag = False

    def copy_controller(self, yes):
        """复制状态记录函数"""
        self.copy_flag = yes

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        act_select_all = menu.addAction('全选')
        act_copy = menu.addAction('复制')
        menu.addSeparator()
        act_clear = menu.addAction('清空')
        # 将是否可以复制的状态记录到类变量中
        self.copyAvailable.connect(self.copy_controller)
        if not self.toPlainText():
            act_select_all.setEnabled(False)
            act_copy.setEnabled(False)
            act_clear.setEnabled(False)
        else:
            act_copy.setEnabled(self.copy_flag)
        action = menu.exec(self.mapToGlobal(event.pos()))
        # 选择行为
        if action == act_copy:
            self.copy()
        elif action == act_select_all:
            self.selectAll()
        elif action == act_clear:
            self.clear()


class MessageWriter(QLineEdit):
    def __init__(self, parent):
        super().__init__(parent)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        act_select_all = menu.addAction('全选')
        act_cut = menu.addAction('剪切')
        act_copy = menu.addAction('复制')
        act_paste = menu.addAction('粘贴')
        if not self.text():
            act_select_all.setEnabled(False)
            act_cut.setEnabled(False)
            act_copy.setEnabled(False)
        else:
            act_cut.setEnabled(self.hasSelectedText())
            act_copy.setEnabled(self.hasSelectedText())
        action = menu.exec(self.mapToGlobal(event.pos()))
        # 选择行为
        if action == act_cut:
            self.cut()
        elif action == act_copy:
            self.copy()
        elif action == act_select_all:
            self.selectAll()
        elif action == act_paste:
            self.paste()


class ClientSettingDialog(QWidget):
    """
    发送端设置对话框(模态)
    """

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.settings = QSettings(os.path.join(os.path.abspath('.'), 'settings.ini'), QSettings.IniFormat)
        self.resolution = QGuiApplication.primaryScreen().availableGeometry()
        self.reso_height = self.resolution.height()
        self.reso_width = self.resolution.width()
        self.init_ui()

    def init_ui(self):
        # 模态对话框且只有关闭按钮
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowCloseButtonHint)
        # 对话框位置及尺寸
        self.setFixedSize(self.reso_width / 8, 0)
        parent_geo = self.parent.geometry()
        self.move(parent_geo.x() + (parent_geo.width() - self.width()) / 2,
                  parent_geo.y() + (parent_geo.height() - self.width()) / 2)

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
        self.Ldel_timeout = QLabel('长按清空延时(秒)')
        self.Sdel_timeout = QDoubleSpinBox(self)
        self.Sdel_timeout.setRange(0.5, 3)
        self.Sdel_timeout.setSingleStep(0.1)
        self.Sdel_timeout.setDecimals(1)
        self.Sdel_timeout.setWrapping(True)
        self.Sdel_timeout.setContextMenuPolicy(Qt.NoContextMenu)
        setting_del_timeout = float(self.settings.value('del_timeout', 1))
        self.Sdel_timeout.setValue(setting_del_timeout)
        self.settings.endGroup()

        self.Gtrans = QGroupBox('传输设置')
        trans_form = QFormLayout()
        trans_form.setSpacing(10)
        trans_form.addRow(self.Lfile_num, self.Sfile_num)
        trans_form.addRow(self.Ldel_timeout, self.Sdel_timeout)
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
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle('错误')
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setText('端口号冲突！\n请设置与接收端不同的端口号！')
            msg_box.addButton('确定', QMessageBox.AcceptRole)
            msg_box.exec()
        else:
            self.settings.beginGroup('ClientSetting')
            self.settings.setValue('host', self.Eserver_ip.text())
            self.settings.setValue('server_port', self.Sserver_port.value())
            self.settings.setValue('file_at_same_time', self.Sfile_num.value())
            self.settings.setValue('del_source', int(self.Cdel_source.isChecked()))
            self.settings.setValue('del_timeout', self.Sdel_timeout.value())
            self.settings.sync()
            self.settings.endGroup()
            self.close()

    def keyPressEvent(self, k):
        if k.key() == Qt.Key_Escape:
            self.close()


class ServerSettingDialog(QWidget):
    """
    服务端设置对话框(模态)
    """

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.settings = QSettings(os.path.join(os.path.abspath('.'), 'settings.ini'), QSettings.IniFormat)
        self.resolution = QGuiApplication.primaryScreen().availableGeometry()
        self.reso_height = self.resolution.height()
        self.reso_width = self.resolution.width()
        self.init_ui()

    def init_ui(self):
        # 模态对话框且只有关闭按钮
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowCloseButtonHint)
        # 对话框位置及尺寸
        self.setFixedSize(self.reso_width / 8, 0)
        parent_geo = self.parent.geometry()
        self.move(parent_geo.x() + (parent_geo.width() - self.width()) / 2,
                  parent_geo.y() + (parent_geo.height() - self.width()) / 2)

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
        self.Breceive_dir.clicked.connect(self.choose_dir)
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
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle('错误')
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setText('端口号冲突！\n请设置与发送端不同的端口号！')
            msg_box.addButton('确定', QMessageBox.AcceptRole)
            msg_box.exec()
        else:
            self.settings.beginGroup('ServerSetting')
            self.settings.setValue('incoming_ip', self.Eincoming_ip.text())
            self.settings.setValue('bind_port', self.Sbind_port.value())
            self.settings.setValue('open_server', int(self.Copen_server.isChecked()))
            self.settings.setValue('receive_dir', self.Ereceive_dir.text())
            self.settings.sync()
            self.settings.endGroup()
            self.close()

    def choose_dir(self):
        self.settings.beginGroup('ServerSetting')
        path = QFileDialog.getExistingDirectory(self, '选择目录', self.Ereceive_dir.text())
        if path:
            self.Ereceive_dir.setText(path)
        self.settings.endGroup()

    def keyPressEvent(self, k):
        if k.key() == Qt.Key_Escape:
            self.close()


class UIDialog(QWidget):
    """
    界面设置对话框(模态)
    """

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.settings = QSettings(os.path.join(os.path.abspath('.'), 'settings.ini'), QSettings.IniFormat)
        self.resolution = QGuiApplication.primaryScreen().availableGeometry()
        self.reso_height = self.resolution.height()
        self.reso_width = self.resolution.width()
        self.init_ui()

    def init_ui(self):
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowCloseButtonHint)
        self.setFixedSize(self.reso_width / 8, 0)
        parent_geo = self.parent.geometry()
        self.move(parent_geo.x() + (parent_geo.width() - self.width()) / 2,
                  parent_geo.y() + (parent_geo.height() - self.width()) / 2)

        self.settings.beginGroup('UISetting')
        self.Lview = QLabel('启用详细视图(重启生效)')
        self.Cview = QCheckBox(self)
        setting_view = int(self.settings.value('detail_view', False))
        self.Cview.setChecked(setting_view)
        self.Lstatus_bar = QLabel('启用状态栏')
        self.Cstatus_bar = QCheckBox(self)
        setting_status_bar = int(self.settings.value('status_bar', True))
        self.Cstatus_bar.setChecked(setting_status_bar)

        self.Lchat_frame = QLabel('启用聊天栏')
        self.Cchat_frame = QCheckBox(self)
        setting_chat_frame = int(self.settings.value('chat_frame', True))
        self.Cchat_frame.setChecked(setting_chat_frame)
        self.settings.endGroup()

        self.Bconfirm = QPushButton('确定', self)
        self.Bconfirm.setDefault(True)
        self.Bcancel = QPushButton('取消', self)

        self.Bconfirm.clicked.connect(self.store)
        self.Bcancel.clicked.connect(self.close)

        form = QFormLayout()
        form.setSpacing(30)
        form.addRow(self.Lview, self.Cview)
        form.addRow(self.Lstatus_bar, self.Cstatus_bar)
        form.addRow(self.Lchat_frame, self.Cchat_frame)
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
        self.settings.setValue('status_bar', int(self.Cstatus_bar.isChecked()))
        self.settings.setValue('chat_frame', int(self.Cchat_frame.isChecked()))
        self.settings.sync()
        self.settings.endGroup()
        self.close()

    def keyPressEvent(self, k):
        if k.key() == Qt.Key_Escape:
            self.close()
