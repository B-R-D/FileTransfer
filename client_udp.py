# coding:utf-8
'''
UDP客户端，尝试连接服务端。
当建立连接后发送指定数据。
'''
import os, threading, json, asyncio, hashlib, random
file = os.listdir('send')
file_at_same_time = 2
error = []
ip = '192.168.1.4'

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

def file_spliter(f):
    '''返回数据块的生成器（单块限定64K）'''
    size = os.path.getsize(f.name)
    all = size // 65000 + 1
    data = (FilePart(f.name, size, i, all, f.read(65000)) for i in range(all))
    return data

class ClientProtocol:

    def __init__(self, gener, name, loop):
        self.gener = gener
        self.name = name
        self.loop = loop
        self.now = next(gener)
        self.md5 = None
        self.thread_md5 = None
        self.transport = None
        self.on_con_lost = loop.create_future()
        self.time_counter = self.loop.call_later(30, self.on_con_lost.set_result, True)

    def connection_made(self, transport):
        self.transport = transport
        self.thread_md5 = threading.Thread(target=self.md5_gener)
        self.thread_md5.start()
        self.message_sender(json.dumps({'type':'message','data':'established','name':self.name}).encode())

    def datagram_received(self, message, addr):
        message = json.loads(message)
        if message['type'] == 'message':
            # 文件传输完成后接收complete信息并清除定时器，然后接收MD5信息后发送结束信息后关闭
            if message['data'] == 'complete' and message['name'] == self.now.name:
                self.time_counter.cancel()
                print('\nTransmission complete.')
            elif message['data'] == 'MD5_passed':
                self.transport.sendto(json.dumps({'type':'message','data':'terminated'}).encode())
                self.transport.close()
                print('\nMD5 checking passed.')
            elif message['data'] == 'MD5_failed':
                error.append(message['name'])
                self.transport.sendto(json.dumps({'type':'message','data':'terminated'}).encode())
                self.transport.close()
                print('\nMD5 checking failed.')
            elif message['data'] == 'get' and message['part'] == self.now.part and message['name'] == self.now.name:
                self.time_counter.cancel()
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
        自带随机秒重发机制的消息回发
        注意此处传入的参数必须是打包好的
        '''
        self.time_counter.cancel()
        self.transport.sendto(message)
        self.time_counter = self.loop.call_later(random.random() + 0.5, self.message_sender, message)
    
    def md5_gener(self):
        '''计算MD5值'''
        md5 = hashlib.md5()
        with open(self.name, 'rb') as f:
            for line in f:
                md5.update(line)
        self.md5 = md5.hexdigest()

async def main(name):
    '''客户端主函数'''
    threading_controller.acquire()
    loop = asyncio.get_running_loop()
    with open(name, 'rb') as fstream:
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: ClientProtocol(file_spliter(fstream), fstream.name, loop),
            remote_addr=(ip, 12345))
        try:
            await protocol.on_con_lost
        finally:
            threading_controller.release()
            transport.close()

# 每个文件一个线程，同时运行线程不超过设定值
threading_controller = threading.BoundedSemaphore(value=file_at_same_time)
for name in file:
    thread_asyncio = threading.Thread(target=asyncio.run, args=(main(name),))
    thread_asyncio.start()
thread_asyncio.join()

if error:
    print('以下文件MD5检查出错：\n')
    for f in error:
        print(f)
else:
    print('File transmission successfully completed without errors.\n')