'''
UDP服务端，等待客户端的连接。
有连接呼入时接收文件并保存。
解决1：块数增多(超千)时组装文件时间过长；
问题2：检查MD5时的回显混乱；
'''
import os, time, json, asyncio, hashlib
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

def write_data(info, data):
    # 状态变量中没有记录的新建记录
    if info['name'] not in status:
        status[info['name']] = {'_part': [], '_error':[]}
    # 检查块的MD5后写入文件，添加全局块信息
    md5 = hashlib.md5()
    md5.update(data)
    if md5.hexdigest() == info['md5']:
        # 打开文件对象并附加数据
        with open(info['name'], 'ab') as filedata:
            filedata.write(data)
        status[info['name']]['_part'].append(info['part'])
        print('{0}(part {1}/{2}) complete.'.format(info['name'], len(status[info['name']]['_part']), info['all']), end='\r')
        return True
    else:
        print('MD5 checking failed.')
        status[info['name']]['_error'].append(info['part'])
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
            write_data(info, data)
            # 分块未全收完才回送收到消息
            if info['all'] != len(status[info['name']]['_part']) + len(status[info['name']]['_error']):
                self.transport.sendto(json.dumps({'type':'message','data':'get'}).encode(), addr)
            else:
                # 否则发送MD5检查情况
                if len(status[info['name']]['_error']) == 0:
                    self.transport.sendto(json.dumps({'type':'message','data':'MD5_passed'}).encode(), addr)
                else:
                    self.transport.sendto(json.dumps({'type':'message','data':'MD5_failed','name':info['name'],'list':status[info['name']]['_error']}).encode(), addr)
                # 从状态字典中删除该key，以便传送同名文件
                status.pop(info['name'])
                print('\nFile: {0}({1}) transmission complete.\n'.format(info['name'], display_file_length(info['size'])))
                # 传送完一个文件后，状态变量为空则发送关闭客户端消息
                if not status:
                    self.transport.sendto(json.dumps({'type':'message','data':'complete'}).encode(), addr)
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
