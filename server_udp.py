'''
UDP服务端，等待客户端的连接。
有连接呼入时接收文件并保存。
解决1：块数增多(超千)时组装文件时间过长；
解决2：检查MD5用子进程检查以避免阻塞，减少客户端超时；
解决3：收到块后检查是否在status中，若在则丢弃块以避免客户端丢包导致的多次接收；
解决4：写入文件函数子进程化；
'''
import os, time, multiprocessing, json, asyncio, hashlib
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
    # 保证子进程的执行顺序
    while True:
        if info['part'] == len(status[info['name']]):
            with open(info['name'], 'ab') as filedata:
                filedata.write(data)
            print('{0}(part {1}/{2}) complete.'.format(info['name'], info['part'] + 1, info['all']), end='\n')
            break
        time.sleep(0.1)

class ServerProtocol:
    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        info = json.loads(data.split(b'---+++data+++---')[0])
        # 处理消息
        if info['type'] == 'message':
            if info['data'] == 'established':
                self.transport.sendto(json.dumps({'type':'message','data':'get'}).encode(), addr)
        # 处理数据
        elif info['type'] == 'data':
            data = data.split(b'---+++data+++---')[1]
            # 状态变量中没有记录的新建记录
            if info['name'] not in status:
                status[info['name']] = []
            # 分块若等于控制器长度则写入并回送收到消息
            if info['part'] == len(status[info['name']]):
                wd = multiprocessing.Process(target=write_data, args=(info, data))
                wd.start()
                status[info['name']].append(info['part'])
                self.transport.sendto(json.dumps({'type':'message','data':'get'}).encode(), addr)
                # 全部块都已经接收则删除记录并发送完成信息
                if len(status[info['name']]) == info['all']:
                    status.pop(info['name'])
                    wd.join()
                    checker = multiprocessing.Process(target=self.MD5_checker, args=(info, addr))
                    checker.start()
                    self.transport.sendto(json.dumps({'type':'message','data':'complete'}).encode(), addr)
                    print('\nFile: {0}({1}) transmission complete.\n'.format(info['name'], display_file_length(info['size'])))
                    
    def connection_lost(self, exc):
        print('Server terminated.')

    def MD5_checker(self, info, addr):
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
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: ServerProtocol(),
        local_addr=('0.0.0.0', 12345))
    print('Waiting for incoming transmission...')
    try:
        await asyncio.sleep(6000)
    finally:
        transport.close()

asyncio.run(main())
