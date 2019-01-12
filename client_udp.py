# coding:utf-8
'''
UDP客户端，尝试连接服务端。
当建立连接后发送指定数据。
解决1：多文件发送；
解决2：增加全局错误存储；
解决3：完善自动重发功能；
改进4：pause_writing功能；
改进5：报错抛出异常化；
'''
import os, threading, json, asyncio, hashlib

file = os.listdir('send')
error = []
ip = '192.168.1.9'

def display_file_length(file_size):
    if file_size < 1024:
        return '{0:.1f}B'.format(file_size)
    elif 1024 <= file_size < 1048576:
        return '{0:.1f}kB'.format(file_size/1024)
    elif 1048576 <= file_size < 1073741824:
        return '{0:.1f}MB'.format(file_size/1048576)
    else:
        return '{0:.1f}GB'.format(file_size/1073741824)

# 声明一个管理类记录所传送文件的信息
class FilePart:
    def __init__(self, name, size, md5, part, all, data):
        # 传入文件信息
        self.name = name
        self.size = size
        self.md5 = md5
        self.part = part
        self.all = all
        self.data = data

# 各数据块管理类实例
def file_spliter(name):
    size = os.path.getsize(name)
    # 块总数(单块限定64K)
    all = size // 65000 + 1
    with open(name, 'rb') as f:
        md5 = hashlib.md5()
        for line in f:
            md5.update(line)
        fmd5 = md5.hexdigest() 
        f.seek(0)
        data = [FilePart(name, size, fmd5, i, all, f.read(65000)) for i in range(all)]
    return data

class ClientProtocol:
    # 传入构造函数:发送的内容及asyncio循环实例
    def __init__(self, data, loop):
        self.data = data
        self.now = None
        self.all = data[0].all
        self.loop = loop
        self.on_con_lost = loop.create_future()
        self.tc = self.loop.call_later(30, self.on_con_lost.set_result, True)
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        self.connection_sender()

    def datagram_received(self, message, addr):
        self.tc.cancel()
        message = json.loads(message)
        if message['type'] == 'message':
            # 全部文件传输完成后接收complete信息并清除定时器，然后接收MD5信息后关闭
            if message['data'] == 'complete':
                self.tc.cancel()
                print('\nTransmission complete.')
            elif message['data'] == 'MD5_passed':
                self.transport.close()
                print('\nMD5 checking passed.')
            elif message['data'] == 'MD5_failed':
                error.append(message['name'])
                self.transport.close()
                print('\nMD5 checking failed.')
            elif message['data'] == 'get':
                # 已经pop空了就等待MD5信息
                if self.data:
                    self.now = self.data.pop(0)
                    self.file_sender()
                    self.tc = self.loop.call_later(1, self.file_sender)
                
    def error_received(self, exc):
        # 异常处理函数，先忽略
        pass
        
    def connection_lost(self, exc):
        print('File:{0}({1}) transmission complete.\n'.format(self.now.name, display_file_length(self.now.size)))
        self.on_con_lost.set_result(True)
    
    def connection_sender(self):
        self.tc.cancel()
        self.transport.sendto(json.dumps({'type':'message','data':'established'}).encode())
        self.tc = self.loop.call_later(1, self.connection_sender)
    
    def file_sender(self):
        self.tc.cancel()
        fdata = json.dumps({'type':'data','name':self.now.name,'size':self.now.size,'part':self.now.part,'all':self.now.all,'md5':self.now.md5}).encode() + b'---+++data+++---' + self.now.data
        print('Sending file:{0} (Part {1}/{2})...'.format(self.now.name, self.now.part + 1, self.now.all), end='')
        self.transport.sendto(fdata)
        print('Done.', end='\n')
        self.tc = self.loop.call_later(1, self.file_sender)

async def main(f):
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: ClientProtocol(file_spliter(f), loop),
        remote_addr=(ip, 12345))
    try:
        await protocol.on_con_lost
    finally:
        transport.close()

# 只能针对每个文件一个线程了
for f in file:
    th = threading.Thread(target=asyncio.run, args=(main(f),))
    th.start()
th.join()
if error:
    print('以下文件MD5检查出错：\n')
    for f in error:
        print(f)
