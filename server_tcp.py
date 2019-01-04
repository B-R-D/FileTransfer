'''
服务端，等待客户端的连接。
有连接呼入时接收文件并保存。
'''

import os, re, json, asyncio, hashlib
# 全局状态
status = {}

def display_file_length(file_size):
    if file_size < 1024:
        return '{0:.1f}B'.format(file_size)
    elif 1024 <= file_size < 1048576:
        return '{0:.1f}kB'.format(file_size/1024)
    elif 1048576 <= file_size < 1073741824:
        return '{0:.1f}MB'.format(file_size/1048576)
    else:
        return '{0:.1f}GB'.format(file_size/1073741824)

async def trans_data(reader, writer):
    data = b''
    chunk = b'empty'
    while chunk:
        #print(chunk, '\n', data)
        chunk = await reader.read(1450)
        data += chunk
    # 接收完一块后发送已接受信号
    #writer.write(b'---+++received+++---')
    info = json.loads(data.split(b'---+++header+++---')[0])
    with open(info['name'] + '.part' + str(info['part']), 'wb') as transchunk:
        transchunk.write(data.split(b'---+++header+++---')[1])
    if info['name'] not in status:
        status[info['name']] = []
    status[info['name']].append(info['part'])
    print('{0}(part {1}/{2}) complete.'.format(info['name'], len(status[info['name']]), info['all']), end='\r')
    return info

async def create_file(info):
    print('\nCreating file...', end='')
    # 当所有块都完成时拼装
    temp_file, p = b'', 0
    while p < info['all']:
        if os.access(info['name'] + '.part' + str(p), os.R_OK):
            with open(info['name'] + '.part' + str(p), 'rb') as chunk:
                temp_file += chunk.read()
            p += 1
    with open(info['name'], 'wb') as last_file:
        last_file.write(temp_file)
    print('Complete.')
    return temp_file

async def check_md5(md5_info, data):
    print('Checking MD5...', end='')
    # 对比MD5值
    md5 = hashlib.md5()
    md5.update(data)
    if md5.hexdigest() == md5_info:
        print('Passed.')
    else:
        # 以后改为抛出异常
        print('Failed.')

async def receive_data(reader, writer):
    info = await trans_data(reader, writer)
    if info['all'] == len(status[info['name']]):
        temp_file = await create_file(info)
        await check_md5(info['md5'], temp_file)
        # 拼装完成后从状态字典中删除该key和part文件，以便传送同名文件
        status.pop(info['name'])
        for f in os.listdir(os.path.abspath('.')):
            # regex = re.match('(' + info['name'] + '.part\d{1,3})', f)
            if f[:len(info['name']) + 5] == info['name'] + '.part':
                os.remove(f)
        print('File: {0}({1}) transmission complete.\n'.format(info['name'], display_file_length(info['size'])))

loop = asyncio.get_event_loop()
coro = asyncio.start_server(receive_data, '0.0.0.0', 12345)
print('Waiting for incoming tranmission...')
server = loop.run_until_complete(coro)
# 键盘中断时关闭服务器
try:
    loop.run_forever()
except KeyboardInterrupt:
    pass
print('\nShutting down...')
server.close()
loop.run_until_complete(server.wait_closed())
loop.close()
