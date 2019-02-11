# coding:utf-8
'''
UDP客户端，尝试连接服务端。
当建立连接后发送指定数据。
'''

import os, threading, random, hashlib, asyncio, json
from multiprocessing import Queue

class FilePart:
    def __init__(self, name, size, part, all, data):
        self.name = name
        self.size = size
        self.part = part
        self.all = all
        self.data = data

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

def file_spliter(fstream):
    '''返回数据块的生成器（单块限定64K）'''
    size = os.path.getsize(fstream.name)
    all = size // 65000 + 1
    data = (FilePart(os.path.split(fstream.name)[1], size, i, all, fstream.read(65000)) for i in range(all))
    return data

class ClientProtocol:

    def __init__(self, gener, path, que, tc, loop):
        self.gener = gener
        self.path = path
        self.que = que
        self.tc = tc
        self.loop = loop
        self.now = next(gener)
        self.md5 = None
        self.thread_md5 = None
        self.transport = None
        self.on_con_lost = loop.create_future()
        self.time_counter = self.loop.call_later(30, self.on_con_lost.set_result, True)

    def connection_made(self, transport):
        self.transport = transport
        self.message_sender(json.dumps({'type':'message','data':'established','name':os.path.split(self.path)[1]}).encode())
        self.thread_md5 = threading.Thread(target=self.md5_gener)
        self.thread_md5.start()

    def datagram_received(self, message, addr):
        message = json.loads(message)
        if message['type'] == 'message':
            # 文件传输完成后接收complete信息并清除定时器，然后接收MD5信息后发送结束信息后关闭
            if message['data'] == 'complete' and message['name'] == self.now.name:
                self.time_counter.cancel()
                print('\nTransmission complete.')
            elif message['data'] == 'MD5_passed':
                self.que.put({'type':'info', 'name':message['name'], 'message':'MD5_passed'})
                self.transport.sendto(json.dumps({'type':'message','data':'terminated'}).encode())
                #self.transport.close()
                self.tc.release()
                print('\nMD5 checking passed.')
            elif message['data'] == 'MD5_failed':
                self.que.put({'type':'info', 'name':message['name'], 'message':'MD5_failed'})
                self.transport.sendto(json.dumps({'type':'message','data':'terminated'}).encode())
                #self.transport.close()
                self.tc.release()
                print('\nMD5 checking failed.')
            elif message['data'] == 'get' and message['part'] == self.now.part and message['name'] == self.now.name:
                self.time_counter.cancel()
                # 队列中放入进度条的值
                self.que.put({'type':'prog', 'name':message['name'], 'part':message['part']})
                try:
                    self.file_sender()
                    self.now = next(self.gener)
                except StopIteration:
                    pass

    def error_received(self, exc):
        # 异常处理函数，先忽略
        pass
        
    def connection_lost(self, exc):
        print('File:{0}({1}) transmission complete.\n'.format(self.now.name, display_file_length(self.now.size)))
        self.on_con_lost.set_result(True)
        
    def file_sender(self):
        '''发送文件分块'''
        # 判定MD5存在性，不存在时判定末块，是末块就等待MD5
        if self.md5:
            fdata = json.dumps({'type':'data','name':self.now.name,'size':self.now.size,'part':self.now.part,'all':self.now.all,'md5':self.md5}).encode() + b'---+++data+++---' + self.now.data
        else:
            if self.now.part + 1 == self.now.all:
                self.thread_md5.join()
                fdata = json.dumps({'type':'data','name':self.now.name,'size':self.now.size,'part':self.now.part,'all':self.now.all,'md5':self.md5}).encode() + b'---+++data+++---' + self.now.data
            else:
                fdata = json.dumps({'type':'data','name':self.now.name,'size':self.now.size,'part':self.now.part,'all':self.now.all}).encode() + b'---+++data+++---' + self.now.data
        print('Sending file:{0} (Part {1}/{2})...'.format(self.now.name, self.now.part + 1, self.now.all), end='')
        self.message_sender(fdata)
        print('Done.', end='\n')
    
    def message_sender(self, message):
        '''
        自带随机秒重发机制的消息回发(至少0.1s)
        注意此处传入的参数必须是打包好的
        '''
        self.time_counter.cancel()
        self.transport.sendto(message)
        self.time_counter = self.loop.call_later(0.2 + random.random(), self.message_sender, message)
    
    def md5_gener(self):
        '''计算MD5值'''
        md5 = hashlib.md5()
        with open(self.path, 'rb') as f:
            for line in f:
                md5.update(line)
        self.md5 = md5.hexdigest()

async def main(host, port, path, threading_controller, que):
    '''客户端主函数'''
    threading_controller.acquire()
    loop = asyncio.get_running_loop()
    with open(path, 'rb') as fstream:
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: ClientProtocol(file_spliter(fstream), fstream.name, que, threading_controller, loop),
            remote_addr=(host, port))
        try:
            await protocol.on_con_lost
        finally:
            #threading_controller.release()
            transport.close()

def thread_starter(host, port, file, file_at_same_time, que):
    '''客户端启动函数'''
    threading_controller = threading.BoundedSemaphore(value=file_at_same_time)
    for path in file:
        thread_asyncio = threading.Thread(target=asyncio.run, args=(main(host, port, path, threading_controller, que),))
        thread_asyncio.start()
    thread_asyncio.join()
