'''
UDP客户端，尝试连接服务端。
当建立连接后发送指定数据。
'''

import os, time, json, asyncio, hashlib

file = os.listdir('send')
ip = '192.168.1.9'

# 声明一个管理类管理所传送文件的信息
class FilePart:
    def __init__(self, name, size, part, all, data):
        # 传入文件信息
        self.name = name
        self.size = size
        self.part = part
        self.all = all
        self.data = data
        # 每块文件md5信息
        _md5 = hashlib.md5()
        _md5.update(self.data)
        self.md5 = _md5.hexdigest()

# 各数据块管理类实例
def file_spliter(name):
    size = os.path.getsize(name)
    # 块总数(单块限定64K)
    all = size // 65400 + 1
    with open(name, 'rb') as f:
        data = [FilePart(name, size, i, all, f.read(65400)) for i in range(all)]
    return data

class EchoClientProtocol:
    # 传入构造函数:发送的内容及asyncio循环实例
    def __init__(self, data, loop):
        self.data = data
        self.loop = loop
        self.transport = None
        self.on_con_lost = loop.create_future()
    def connection_made(self, transport):
        self.transport = transport
        # 只有第一块时才发送建立连接消息
        if self.data.part == 0:
            self.transport.sendto(json.dumps({'type':'message','data':'established'}).encode())
    def datagram_received(self, message, addr):
        # 等待返回是否收到，情况一说明单块收到，情况二说明MD5情况
        # 若情况种类繁多可以考虑独立为函数，解析头部获取数据报头部与数据
        message = json.loads(message)
        print(message)
        if message['type'] == 'message':
            print({'type':'data','name':self.data.name,'size':self.data.size,'part':self.data.part,'all':self.data.all,'md5':self.data.md5})
            # 建立连接就发送数据
            if message['data'] == 'established':
                fdata = json.dumps({'type':'data','name':self.data.name,'size':self.data.size,'part':self.data.part,'all':self.data.all,'md5':self.data.md5}).encode() + b'---+++data+++---' + self.data.data
                print('Sending file:{0} (Part {1}/{2})...'.format(self.data.name, self.data.part + 1, self.data.all), end='')
                self.transport.sendto(fdata)
                print('Done.')
                '''
                # 进行到最后一块时等待MD5消息(需要新开一个数据报接收才行)
                if self.data.part + 1 == self.data.all:
                    while True:
                        if message['data'] == 'MD5_passed':
                            print('Transmission complete.')
                            break
                        elif message['data'] == 'MD5_failed':
                            print('Transmission failed, MD5 checking failed.')
                            break
                        else:
                            print(message['data'], 'Waiting for response...', end='\r')
                            time.sleep(0.1)
                '''
        self.transport.close()
    def error_received(self, exc):
        # 异常处理函数，先忽略
        pass
    def connection_lost(self, exc):
        self.on_con_lost.set_result(True)

async def main():
    loop = asyncio.get_running_loop()
    for f in file:
        for part in file_spliter(f):
            transport, protocol = await loop.create_datagram_endpoint(
                lambda: EchoClientProtocol(part, loop),
                remote_addr=(ip, 12345))
    try:
        await protocol.on_con_lost
    finally:
        transport.close()

asyncio.run(main())