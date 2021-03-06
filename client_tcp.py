'''
客户端，尝试连接服务端。
当建立连接后发送指定数据。
'''
import os, time, json, asyncio, hashlib

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

# 建立连接
async def send_data(data):
    info = json.loads(data.split(b'---+++header+++---')[0])
    print('Sending file:{0} (Part {1}/{2})...'.format(info['name'], info['part'], info['all']), end='')
    reader, writer = await asyncio.open_connection(ip, 12345)
    writer.write(data)
    await writer.drain()

def file_transfer_client():
    tasks = []
    for f in file:
        status = Status(part, f)
        data = file_spliter(f, status.get_part())
        counter = len(data)
        for d in data:
            tasks.append(send_data(d))
            counter -= 1
            if len(tasks) % 5 == 0 or counter == 0:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(asyncio.wait(tasks))
                time.sleep(status.get_sleep_time())
                loop.close()
                tasks = []

file_transfer_client()