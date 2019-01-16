import os, sys, threading, json, asyncio, hashlib
from PyQt5.QtCore import Qt, QCoreApplication
from PyQt5.QtWidgets import QWidget, QPushButton, QApplication, QDesktopWidget, QLabel, QTextEdit, QGridLayout, QFileDialog, QFrame, QMainWindow, QAction
from PyQt5.QtGui import QFont

'''
----------------Qt5的GUI部分----------------
'''

class ClientWindow(QMainWindow):
    '''Qt5窗体类'''
    def __init__(self):
        super().__init__()
        self.initUI()
        
    def initUI(self):
        self.setFont(QFont('Arial', 10))
        # 是否可以按照屏幕分辨率动态设置窗口尺寸？
        self.resize(600, 800)
        self.center()
        
        # 添加菜单栏
        menubar = self.menuBar()
        settingMenu = menubar.addMenu('设置(&S)')
        partAct = QAction('分块(&P)', self)
        exitAct = QAction('退出(&Q)', self)
        exitAct.triggered.connect(QCoreApplication.instance().quit)
        settingMenu.addAction(partAct)
        settingMenu.addSeparator()
        settingMenu.addAction(exitAct)
        
        Bselector = QPushButton('选择文件', self)    
        flist = Bselector.clicked.connect(self.fileDialog)
        self.Lfile = QLabel('没有选中的文件')
        self.Lfile.setFrameStyle(QFrame.Box)
        self.Lfile.setAlignment(Qt.AlignTop)
        Bsend = QPushButton('发送', self)

        # Bsend.clicked.connect(self.ftc)
        
        # 设置布局
        widget = QWidget()
        self.setCentralWidget(widget)
        grid = QGridLayout()
        grid.setSpacing(30)
        grid.addWidget(Bselector, 1, 1, 1, 1)
        grid.addWidget(self.Lfile, 2, 1)
        grid.addWidget(Bsend, 3, 1, 1, 1)
        widget.setLayout(grid)
        
        self.setWindowTitle('FileTransfer')       
        self.show()
        
    # 选择要发送的文件且显示文件名列表
    def fileDialog(self):
        fname = QFileDialog.getOpenFileNames(self, '请选择要发送的文件', os.path.abspath('.'))
        flist = ''
        if fname[0]:
            for f in fname[0]:
                flist += os.path.split(f)[1] + '\n'
            flist = flist[:-1]
            self.Lfile.setText(flist)
            return fname[0]
    
    # 执行客户端发送操作
    
    # 打开窗体时位于屏幕中心
    def center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    # 按ESC时关闭窗体
    def keyPressEvent(self, k):
        if k.key() == Qt.Key_Escape:
            self.close()

'''
----------------主程序部分----------------
'''



if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ClientWindow()
    sys.exit(app.exec())