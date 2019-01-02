'''
UDP客户端，尝试连接服务端。
当建立连接后发送指定数据。
'''
import os, json, asyncio, hashlib

file = os.listdir('send')
part = 0
# 网速M/s
net = 4
ip = '192.168.1.9'

# 声明一个管理类管理所传送文件的信息
class Status:
    def __init__(self, part, name):
        self.part = part
        # 传入文件绝对路径
        self.name = name
        self._size = os.path.getsize(name)
        # 相邻两块组之间间隔时间，10块为一组
        self._sleep_time = 0
        # 当part设置为0时采用自动确定块数策略
        if self.part == 0:
            # 单块不超过每秒网速
            self.part = round(self._size / 1048576 / net)
            # 大于10块时间隔时间就是块数
            if self.part > 10:
                self._sleep_time = 5
        else:
            # 手动设置块数策略后期增加
            pass
    def get_part(self):
        return self.part
    def get_sleep_time(self):
        return self._sleep_time

# 生成数据头和各数据分组
def file_spliter(file_name, p):
    file_size = os.path.getsize(file_name)
    # 5M以下文件不分块
    if file_size <= 5242880:
        p = 1
    md5 = hashlib.md5()
    with open(file_name, 'rb') as f:
        md5.update(f.read())
        file_md5 = md5.hexdigest()
        f.seek(0)
        data = [f.read(file_size // p + 1) for i in range(p)]
    # 为每个part加上头信息
    for i in range(len(data)):
        part_info = {'name': file_name, 'size': file_size, 'md5': file_md5, 'part': i, 'all': p}
        data[i] = json.dumps(part_info).encode() + b'---+++header+++---' + data[i]
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
        # 建立连接后发送数据
        info = json.loads(self.data.split(b'---+++header+++---')[0])
        print('Sending file:{0} (Part {1}/{2})...'.format(info['name'], info['part'], info['all']), end='')
        self.transport.sendto(self.data)
    def datagram_received(self, message, addr):
        # 回显接收的数据
        print(message.decode())
        self.transport.close()
    def error_received(self, exc):
        # 异常处理函数，先忽略
        pass
    def connection_lost(self, exc):
        self.on_con_lost.set_result(True)

async def main():
    loop = asyncio.get_running_loop()
    # 欲发送的内容，应提前准备好
    for f in file:
        status = Status(part, f)
        data = file_spliter(f, status.get_part())
        for d in data:
            transport, protocol = await loop.create_datagram_endpoint(
                lambda: EchoClientProtocol(d, loop),
                remote_addr=('127.0.0.1', 12345))
    try:
        await protocol.on_con_lost
    finally:
        transport.close()

asyncio.run(main())