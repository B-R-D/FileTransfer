# coding:utf-8
'''
UDP客户端GUI版
改进1：添加文件进度条；
改进2：文件传输完成后提示完成；
改进3：添加时不清除已添加，有按钮可清除；
改进4：MD5检查错误的文件提示；
改进5：选择文件时记住上次位置；
解决6：按照屏幕分辨率动态设置窗口尺寸；
'''
import os, sys
import clientudp
from multiprocessing import Process
from PyQt5.QtCore import Qt, QCoreApplication, QSettings
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QWidget, QDesktopWidget, QGridLayout, QFrame, QMainWindow, QApplication
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
        super().__init__()
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
        chooseAct = QAction('选择(&C)', self)
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
        fileAct = QAction('文件设置(&F)', self)
        
        settingMenu.addAction(netAct)
        settingMenu.addAction(fileAct)
        netAct.triggered.connect(self.netSettingDialog)
        fileAct.triggered.connect(self.fileSettingDialog)

        self.Bselector = QPushButton('选择文件', self)    
        flist = self.Bselector.clicked.connect(self.fileDialog)
        self.Lfile = QLabel('未选中文件')
        self.Lfile.setFrameStyle(QFrame.Box)
        self.Lfile.setAlignment(Qt.AlignTop)
        self.Bsend = QPushButton('发送', self)

        self.Bsend.clicked.connect(self.fileChecker)
        
        # 设置布局
        widget = QWidget()
        self.setCentralWidget(widget)
        grid = QGridLayout()
        grid.setSpacing(30)
        grid.addWidget(self.Bselector, 1, 1, 1, 1)
        grid.addWidget(self.Lfile, 2, 1)
        grid.addWidget(self.Bsend, 3, 1, 1, 1)
        widget.setLayout(grid)
        
        self.setWindowTitle('FileTransfer')       
        self.show()
        
    # 选择要发送的文件且显示文件名列表
    def fileDialog(self):
        fname = QFileDialog.getOpenFileNames(self, '请选择文件')
        flist = ''
        if fname[0]:
            for f in fname[0]:
                flist += os.path.split(f)[1] + '\n'
                file.append(f)
            flist = flist[:-1]
            self.Lfile.setText(flist)
    
    # 测试有没有选中文件
    def fileChecker(self):
        if not file:
            QMessageBox.warning(self, '错误', '未选择文件', QMessageBox.Ok)
        else:
            sender = Process(target=clientudp.thread_starter, args=(file_at_same_time, file, host))
            sender.start()
            #sender.join()
    
    def netSettingDialog(self):
        self.netsetting = NetDialog()
        self.netsetting.show()
    
    def fileSettingDialog(self):
        file_at_same_time, ok = QInputDialog.getInt(self, '文件设置', '同时传送的文件数(1-3)', max=3, min=1)
    
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
        self.resize(800, 600)
        
        self.Lip = QLabel('服务器IP')
        self.Eip = QLineEdit(self)
        self.Lport = QLabel('端口号(1024-65535)')
        self.Eport = QLineEdit(self)
        
        self.Bconfirm = QPushButton('确定', self)
        self.Bcancel = QPushButton('取消', self)
        
        grid = QGridLayout()
        grid.setSpacing(30)
        grid.addWidget(self.Lip, 1, 1)
        grid.addWidget(self.Eip, 1, 2)
        grid.addWidget(self.Lport, 2, 1)
        grid.addWidget(self.Eport, 2, 2)
        grid.addWidget(self.Bconfirm, 4, 1)
        grid.addWidget(self.Bcancel, 4, 2)
        self.setLayout(grid)
        
        self.setWindowTitle('设置')
    
    def keyPressEvent(self, k):
        if k.key() == Qt.Key_Escape:
            self.close()
    
if __name__ == '__main__':
    file = []
    file_at_same_time = 2
    error = []
    host = '192.168.1.3'
    port = 12345
    app = QApplication(sys.argv)
    window = ClientWindow()
    sys.exit(app.exec())