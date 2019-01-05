'''
UDP服务端，等待客户端的连接。
有连接呼入时接收文件并保存。
解决1：块数增多(超千)时组装文件时间过长；
问题2：检查MD5时的回显混乱；
'''
import os, time, json, asyncio, hashlib
# 全局状态
status = {'__error':[]}

def display_file_length(file_size):
    if file_size < 1024:
        return '{0:.1f}B'.format(file_size)
    elif 1024 <= file_size < 1048576:
        return '{0:.1f}kB'.format(file_size/1024)
    elif 1048576 <= file_size < 1073741824:
        return '{0:.1f}MB'.format(file_size/1048576)
    else:
        return '{0:.1f}GB'.format(file_size/1073741824)

def write_data(info, data):
    # 检查块的MD5后写入文件，添加全局块信息
    print('Checking MD5...', end='')
    md5 = hashlib.md5()
    md5.update(data)
    if md5.hexdigest() == info['md5']:
        print('Passed.')
        # 打开文件对象并附加数据
        with open(info['name'], 'ab') as filedata:
            filedata.write(data)
        if info['name'] not in status:
            status[info['name']] = []
        status[info['name']].append(info['part'])
        print('{0}(part {1}/{2}) complete.'.format(info['name'], len(status[info['name']]), info['all']), end='\r')
        return True
    else:
        print('Failed.')
        status['__error'].append(info['part'])
        # 以后改为抛出异常
        return False

class ServerProtocol:
    def connection_made(self, transport):
        self.transport = transport
    def datagram_received(self, data, addr):
        info = json.loads(data.split(b'---+++data+++---')[0])
        if info['type'] == 'message':
            # 回应客户端的呼入
            if info['data'] == 'established':
                self.transport.sendto(json.dumps({'type':'message','data':'get'}).encode(), addr)
        elif info['type'] == 'data':
            data = data.split(b'---+++data+++---')[1]
            # 写入文件
            write_data(info, data)
            # 未全收完才回送收到消息
            if info['all'] != len(status[info['name']]):
                self.transport.sendto(json.dumps({'type':'message','data':'get'}).encode(), addr)
            else:
                if len(status['__error']) == 0:
                    self.transport.sendto(json.dumps({'type':'message','data':'MD5_passed'}).encode(), addr)
                else:
                    # 以后发送的内容中附上MD5出错的块列表error_part
                    error_part = status.pop('__error')
                    self.transport.sendto(json.dumps({'type':'message','data':'MD5_failed'}).encode(), addr)
                    status['__error'] = []
                # 从状态字典中删除该key，以便传送同名文件
                status.pop(info['name'])
                print('\nFile: {0}({1}) transmission complete.\n'.format(info['name'], display_file_length(info['size'])))
    def connection_lost(self, exc):
        print('Server terminated.')

async def main():
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: ServerProtocol(),
        local_addr=('0.0.0.0', 12345))
    print('Waiting for incoming transmission...')
    try:
        await asyncio.sleep(300)
    finally:
        transport.close()

asyncio.run(main())