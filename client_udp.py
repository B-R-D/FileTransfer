'''
UDP客户端，尝试连接服务端。
当建立连接后发送指定数据。
解决1：多文件发送；
问题2：发送时可直接放入send中；
问题3：超时则自动重发；
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

def file_sender(transport, data):
    fdata = json.dumps({'type':'data','name':data.name,'size':data.size,'part':data.part,'all':data.all,'md5':data.md5}).encode() + b'---+++data+++---' + data.data
    print('Sending file:{0} (Part {1}/{2})...'.format(data.name, data.part + 1, data.all), end='')
    transport.sendto(fdata)
    print('Done.', end='\r')

class EchoClientProtocol:
    # 传入构造函数:发送的内容及asyncio循环实例
    def __init__(self, data, loop):
        self.data = data
        self.count = 0
        self.all = data[0].all
        self.loop = loop
        self.transport = None
        self.on_con_lost = loop.create_future()

    def connection_made(self, transport):
        self.transport = transport
        # 只有第一块时才发送建立连接消息
        if self.data[self.count].part == 0:
            self.transport.sendto(json.dumps({'type':'message','data':'established'}).encode())

    def datagram_received(self, message, addr):
        message = json.loads(message)
        if message['type'] == 'message':
            # 全部文件传输完成后接收complete信息后关闭
            if message['data'] == 'complete':
                print('\nTransmission complete.')
                self.transport.close()
            # 最后一块发送完后等待MD5
            elif message['data'] == 'MD5_passed':
                print('\nMD5 checking passed.')
            elif message['data'] == 'MD5_failed':
                print('\nMD5 checking failed.')
            # 非最后一块就发送数据(1秒超时重发)
            elif message['data'] == 'get':
                file_sender(self.transport, self.data[self.count])
                self.count += 1
                
    def error_received(self, exc):
        # 异常处理函数，先忽略
        pass
    def connection_lost(self, exc):
        self.on_con_lost.set_result(True)

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