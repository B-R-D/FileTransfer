import os, sys, threading, json, asyncio, hashlib
from multiprocessing import Process
from PyQt5.QtCore import Qt, QCoreApplication
from PyQt5.QtWidgets import QWidget, QPushButton, QApplication, QDesktopWidget, QLabel, QGridLayout, QFileDialog, QFrame, QMainWindow, QAction, QMessageBox
from PyQt5.QtGui import QFont


# 声明一个管理类记录所传送文件的信息
class FilePart:
    def __init__(self, name, size, part, all, data):
        # 传入文件信息
        self.name = name
        self.size = size
        self.part = part
        self.all = all
        self.data = data

class ClientProtocol:
    # 传入构造函数:发送的内容及asyncio循环实例
    def __init__(self, gener, path, loop):
        self.gener = gener
        self.now = path
        self.loop = loop
        self.md5 = None
        self.thread_md5 = None
        self.transport = None
        self.on_con_lost = loop.create_future()
        self.time_counter = self.loop.call_later(30, self.on_con_lost.set_result, True)

    def connection_made(self, transport):
        self.transport = transport
        self.message_sender(json.dumps({'type':'message','data':'established'}).encode())
        self.thread_md5 = threading.Thread(target=self.md5_gener)
        self.thread_md5.start()

    def datagram_received(self, message, addr):
        self.time_counter.cancel()
        message = json.loads(message)
        if message['type'] == 'message':
            # 文件传输完成后接收complete信息并清除定时器，然后接收MD5信息后发送结束信息后关闭
            if message['data'] == 'complete':
                self.time_counter.cancel()
                print('\nTransmission complete.')
            elif message['data'] == 'MD5_passed':
                self.transport.sendto(json.dumps({'type':'message','data':'terminated'}).encode())
                self.transport.close()
                print('\nMD5 checking passed.')
            elif message['data'] == 'MD5_failed':
                error.append(message['name'])
                self.transport.sendto(json.dumps({'type':'message','data':'terminated'}).encode())
                self.transport.close()
                print('\nMD5 checking failed.')
            elif message['data'] == 'get':
                # 已经pop空了就等待MD5信息
                try:
                    self.now = next(self.gener)
                    self.file_sender()
                except StopIteration:
                    pass

    def error_received(self, exc):
        # 异常处理函数，先忽略
        pass
        
    def connection_lost(self, exc):
        print('File:{0}({1}) transmission complete.\n'.format(self.now.name, display_file_length(self.now.size)))
        self.on_con_lost.set_result(True)
        
    def file_sender(self):
        '''发送文件分块（1秒重发）'''
        # 判定MD5存在性，不存在时判定末块，是末块就等待MD5
        if self.md5:
            fdata = json.dumps({'type':'data','name':self.now.name,'size':self.now.size,'part':self.now.part,'all':self.now.all,'md5':self.md5}).encode() + b'---+++data+++---' + self.now.data
        else:
            if self.now.part + 1 == self.now.all:
                self.thread_md5.join()
                fdata = json.dumps({'type':'data','name':self.now.name,'size':self.now.size,'part':self.now.part,'all':self.now.all,'md5':self.md5}).encode() + b'---+++data+++---' + self.now.data
            else:
                fdata = json.dumps({'type':'data','name':self.now.name,'size':self.now.size,'part':self.now.part,'all':self.now.all}).encode() + b'---+++data+++---' + self.now.data
        print('Sending file:{0} (Part {1}/{2})...'.format(self.now.name, self.now.part + 1, self.now.all), end='')
        self.message_sender(fdata)
        print('Done.', end='\n')
    
    def message_sender(self, message):
        '''
        自带1秒重发机制的消息回发
        注意此处传入的参数必须是打包好的
        '''
        self.time_counter.cancel()
        self.transport.sendto(message)
        self.time_counter = self.loop.call_later(1, self.message_sender, message)
    
    def md5_gener(self):
        '''计算MD5值'''
        md5 = hashlib.md5()
        with open(self.now, 'rb') as f:
            for line in f:
                md5.update(line)
        self.md5 = md5.hexdigest()

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
        self.Lfile = QLabel('未选中文件')
        self.Lfile.setFrameStyle(QFrame.Box)
        self.Lfile.setAlignment(Qt.AlignTop)
        Bsend = QPushButton('发送', self)

        Bsend.clicked.connect(self.fileChecker)
        
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
                file.append(f)
            flist = flist[:-1]
            self.Lfile.setText(flist)

    def fileChecker(self):
        if not file:
            QMessageBox.warning(self, '错误', '未选择文件', QMessageBox.Ok)
        else:
            sender = Process(target=thread_starter, args=(file_at_same_time, file, host))
            sender.start()
    
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

def display_file_length(file_size):
    '''格式化文件长度'''
    if file_size < 1024:
        return '{0:.1f}B'.format(file_size)
    elif 1024 <= file_size < 1048576:
        return '{0:.1f}kB'.format(file_size/1024)
    elif 1048576 <= file_size < 1073741824:
        return '{0:.1f}MB'.format(file_size/1048576)
    else:
        return '{0:.1f}GB'.format(file_size/1073741824)

def file_spliter(f):
    '''返回数据块的生成器'''
    size = os.path.getsize(f.name)
    # 单块限定64K
    all = size // 65000 + 1
    data = (FilePart(os.path.split(f.name)[1], size, i, all, f.read(65000)) for i in range(all))
    return data

async def main(threading_controller, name, host):
    '''单个文件主函数'''
    threading_controller.acquire()
    loop = asyncio.get_running_loop()
    with open(name, 'rb') as fstream:
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: ClientProtocol(file_spliter(fstream), fstream.name, loop),
            remote_addr=(host, 12345))
        try:
            await protocol.on_con_lost
        finally:
            threading_controller.release()
            transport.close()

def thread_starter(file_at_same_time, file, host):
    '''客户端发送文件主函数'''
    threading_controller = threading.BoundedSemaphore(value=file_at_same_time)
    for name in file:
        thread_asyncio = threading.Thread(target=asyncio.run, args=(main(threading_controller, name, host),))
        thread_asyncio.start()
    thread_asyncio.join()

if __name__ == '__main__':
    file = []
    file_at_same_time = 3
    error = []
    host = '192.168.1.3'
    app = QApplication(sys.argv)
    window = ClientWindow()
    sys.exit(app.exec())