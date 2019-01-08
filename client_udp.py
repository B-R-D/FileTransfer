'''
UDP客户端，尝试连接服务端。
当建立连接后发送指定数据。
解决1：多文件发送；
改进2：发送时可直接放入send中；
解决3：完善自动重发功能；
问题4：多次连接服务器失败后退出程序；
改进5：报错抛出异常化；
'''

import os, json, asyncio, hashlib

file = os.listdir('send')
# 同时传输的文件数限制
limit = 3
ip = '192.168.1.9'

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

class EchoClientProtocol:
    # 传入构造函数:发送的内容及asyncio循环实例
    def __init__(self, data, loop):
        self.data = data
        # 重试次数计数，考虑首次正常+1
        self.retry = -1
        self.now = None
        self.all = data[0].all
        self.loop = loop
        self.tc = self.loop.call_later(10, self.connection_lost)
        self.transport = None
        self.on_con_lost = loop.create_future()

    def connection_made(self, transport):
        self.transport = transport
        # 只有第一块时才发送建立连接消息(这条消息丢失会导致文件无法传输)
        self.connection_sender()

    def datagram_received(self, message, addr):
        self.tc.cancel()
        message = json.loads(message)
        if message['type'] == 'message':
            # 全部文件传输完成后接收complete信息后关闭
            if message['data'] == 'complete':
                print('\nTransmission complete.')
                self.transport.close()
            elif message['data'] == 'MD5_passed':
                print('\nMD5 checking passed, retry {0} time(s).'.format(self.retry))
            elif message['data'] == 'MD5_failed':
                print('\nMD5 checking failed, retry {0} time(s).'.format(self.retry))
            elif message['data'] == 'get':
                self.now = self.data.pop(0)
                self.file_sender()
                self.tc = self.loop.call_later(1, self.file_resender)
                
    def error_received(self, exc):
        # 异常处理函数，先忽略
        pass
    def connection_lost(self, exc):
        self.on_con_lost.set_result(True)
    
    def connection_sender(self):
        self.tc.cancel()
        self.transport.sendto(json.dumps({'type':'message','data':'established'}).encode())
        self.retry += 1
        self.tc = self.loop.call_later(1, self.connection_sender)
    
    def file_sender(self):
        fdata = json.dumps({'type':'data','name':self.now.name,'size':self.now.size,'part':self.now.part,'all':self.now.all,'md5':self.now.md5}).encode() + b'---+++data+++---' + self.now.data
        print('Sending file:{0} (Part {1}/{2})...'.format(self.now.name, self.now.part + 1, self.now.all), end='')
        self.transport.sendto(fdata)
        print('Done.', end='\n')
    
    # 重试函数
    def file_resender(self):
        self.retry += 1
        self.file_sender()

async def main():
    loop = asyncio.get_running_loop()
    for f in file:
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: EchoClientProtocol(file_spliter(f), loop),
            remote_addr=(ip, 12345))
        try:
            await protocol.on_con_lost
        finally:
            transport.close()

asyncio.run(main())