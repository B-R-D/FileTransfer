# coding:utf-8
'''
UDP服务端，等待客户端的连接。
有连接呼入时接收文件并保存。
解决1：块数增多(超千)时组装文件时间过长；
解决2：检查MD5用子进程检查以避免阻塞，减少客户端超时；
解决3：收到块后检查是否在status中，若在则丢弃块以避免客户端丢包导致的多次接收；
解决4：写入文件函数子线程化；
'''
import os, time, threading, json, asyncio, hashlib

status = {}

def display_file_length(file_size):
    '''格式化文件长度'''
    if file_size < 1024:
        return '{0:.1f}B'.format(file_size)
    elif 1024 <= file_size < 1048576:
        return '{0:.1f}kB'.format(file_size/1024)
    elif 1048576 <= file_size < 1073741824:
        return '{0:.1f}MB'.format(file_size/1048576)
    else:
        return '{0:.1f}GB'.format(file_size/1073741824)

class ServerProtocol:
    def __init__(self, loop):
        self.loop = loop
        self.time_counter = self.loop.call_later(30, print, 'No connection in 30 seconds.')
    
    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        self.time_counter.cancel()
        info = json.loads(data.split(b'---+++data+++---')[0])
        if info['type'] == 'message':
            if info['data'] == 'established':
                self.message_sender({'type':'message','data':'get'}, addr)
            elif info['data'] == 'terminated':
                print('\nConnection terminated successfully.\n')
                self.time_counter.cancel()
        elif info['type'] == 'data':
            data = data.split(b'---+++data+++---')[1]
            # 状态变量中没有记录的新建记录
            if info['name'] not in status:
                status[info['name']] = []
            # 分块若等于控制器长度则写入并回送收到消息
            if info['part'] == len(status[info['name']]):
                status[info['name']].append(info['part'])
                wd = threading.Thread(target=self.write_data, args=(info, data, addr))
                wd.start()
                # 全部块都已经接收则删除记录并发送完成信息
                if len(status[info['name']]) == info['all']:
                    status.pop(info['name'])
                    wd.join()
                    checker = threading.Thread(target=self.MD5_checker, args=(info, addr))
                    checker.start()
                    self.transport.sendto(json.dumps({'type':'message','data':'complete'}).encode(), addr)
                    print('\nFile: {0}({1}) transmission complete.\n'.format(info['name'], display_file_length(info['size'])))
                    
    def connection_lost(self, exc):
        print('Server terminated.')
    
    def write_data(self, info, data, addr):
        '''写入本地数据并回发get消息'''
        with open(info['name'], 'ab') as filedata:
            filedata.write(data)
        print('{0}(part {1}/{2}) complete.'.format(info['name'], info['part'] + 1, info['all']), end='\n')
        self.message_sender({'type':'message','data':'get'}, addr)
        
    def message_sender(self, message, addr):
        '''自带1秒重发机制的消息回发'''
        self.time_counter.cancel()
        self.transport.sendto(json.dumps(message).encode(), addr)
        self.time_counter = self.loop.call_later(1, self.message_sender, message, addr)

    def MD5_checker(self, info, addr):
        '''MD5检查函数，不带重发机制'''
        with open(info['name'], 'rb') as filedata:
            md5 = hashlib.md5()
            for line in filedata:
                md5.update(line)
        if md5.hexdigest() == info['md5']:
            self.transport.sendto(json.dumps({'type':'message','data':'MD5_passed'}).encode(), addr)
            print('\n', info['name'], 'MD5 checking passed.\n')
        else:
            self.transport.sendto(json.dumps({'type':'message','data':'MD5_failed','name':info['name']}).encode(), addr)
            print('\n', info['name'], 'MD5 checking failed.\n')
        
async def main():
    '''服务端主函数'''
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: ServerProtocol(loop),
        local_addr=('0.0.0.0', 12345))
    print('Waiting for incoming transmission...')
    try:
        await asyncio.sleep(6000)
    finally:
        transport.close()

asyncio.run(main())
