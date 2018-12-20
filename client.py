'''
客户端，尝试连接服务端。
当建立连接后发送指定数据。
'''

import os, json, asyncio, hashlib
file = ['test1', 'test2']
part = 40

# 生成数据头和各数据分组
def file_spliter(file_name, p):
    file_size = os.path.getsize(file_name)
    # 3M以下文件不分块
    if file_size <= 3145728:
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

# 代替socket建立连接
async def send_data(data):
    reader, writer = await asyncio.open_connection('192.168.1.9', 12345)
    writer.write(data)
    await writer.drain()
    info = json.loads(data.split(b'---+++header+++---')[0])
    print('Sending file:{0} (Part {1}/{2})... Done.'.format(info['name'], info['part'], part), end='\r')

loop = asyncio.get_event_loop()
tasks = []
for f in file:
    data = file_spliter(f, part)
    for d in data:
        tasks.append(send_data(d))
loop.run_until_complete(asyncio.wait(tasks))
loop.close()
