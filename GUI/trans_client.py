# coding:utf-8
"""
UDP客户端，尝试连接服务端。
当建立连接后发送指定数据。
"""
import os
import threading
import random
import hashlib
import asyncio
import json


class FilePart:
    """文件信息类"""
    def __init__(self, name, size, part, total, data):
        self.name = name
        self.size = size
        self.part = part
        self.total = total
        self.data = data


def display_file_length(file_size):
    """格式化文件长度"""
    if file_size < 1024:
        return '{0:.1f}B'.format(file_size)
    elif 1024 <= file_size < 1048576:
        return '{0:.1f}kB'.format(file_size / 1024)
    elif 1048576 <= file_size < 1073741824:
        return '{0:.1f}MB'.format(file_size / 1048576)
    else:
        return '{0:.1f}GB'.format(file_size / 1073741824)


def file_spliter(fstream):
    """包装并返回数据块的生成器（单块限定64K）"""
    size = os.path.getsize(fstream.name)
    total = size // 65000 + 1
    data = (FilePart(os.path.split(fstream.name)[1], size, i, total, fstream.read(65000)) for i in range(total))
    return data


class ClientProtocol:
    """
    客户端主控制类。
    """
    def __init__(self, gener, path, que, tc, loop):
        self.gener = gener
        self.path = path
        self.que = que
        self.tc = tc
        self.loop = loop
        self.now = next(gener)
        self.md5 = None
        self.transport = None
        self.on_con_lost = loop.create_future()
        self.time_counter = self.loop.call_later(10, self.on_con_lost.set_result, True)

    def connection_made(self, transport):
        """
        连接建立时的行为：
        发送带文件名的建立连接包并开始计算MD5值
        """
        self.transport = transport
        msg = json.dumps({'type': 'message', 'data': 'established', 'name': os.path.split(self.path)[1]}).encode()
        self.message_sender(msg)
        self.thread_md5 = threading.Thread(target=self.md5_gener)
        self.thread_md5.start()

    def datagram_received(self, message):
        """
        接收数据报时的行为：
        依据传递的信息执行响应。
        """
        message = json.loads(message)
        if message['type'] == 'message':
            if message['data'] == 'complete' and message['name'] == self.now.name:
                # 文件传输完成后接收complete信息并清除定时器
                self.time_counter.cancel()
                print('\nTransmission complete.')
            elif message['data'] == 'MD5_passed':
                # 向主进程传递MD5信息并释放锁
                self.que.put({'type': 'info', 'name': message['name'], 'message': 'MD5_passed'})
                msg = json.dumps({'type': 'message', 'data': 'terminated'}).encode()
                self.transport.sendto(msg)
                self.tc.release()
                print('\nMD5 checking passed.')
            elif message['data'] == 'MD5_failed':
                self.que.put({'type': 'info', 'name': message['name'], 'message': 'MD5_failed'})
                msg = json.dumps({'type': 'message', 'data': 'terminated'}).encode()
                self.transport.sendto(msg)
                self.tc.release()
                print('\nMD5 checking failed.')
            elif message['data'] == 'get' and message['part'] == self.now.part and message['name'] == self.now.name:
                # 接收到成功回包则更新进度条消息并发送下一个包
                self.time_counter.cancel()
                self.que.put({'type': 'prog', 'name': message['name'], 'part': message['part']})
                try:
                    self.file_sender()
                    self.now = next(self.gener)
                except StopIteration:
                    pass

    def error_received(self, exc):
        """异常处理函数，先忽略"""
        pass
        
    def connection_lost(self, exc):
        """连接断开时的行为：现在不会调用"""
        pass
        
    def file_sender(self):
        """数据报的发送行为"""
        # 判定MD5是否计算完成
        if self.md5:
            raw_msg = {'type': 'data', 'name': self.now.name, 'size': self.now.size, 'part': self.now.part,
                       'all': self.now.total, 'md5': self.md5}
            fdata = json.dumps(raw_msg).encode() + b'---+++data+++---' + self.now.data
        else:
            # MD5未计算完成则判定当前是否为末块，是则等待MD5计算，不是则继续发送
            if self.now.part + 1 == self.now.total:
                self.thread_md5.join()
                raw_msg = {'type': 'data', 'name': self.now.name, 'size': self.now.size, 'part': self.now.part,
                           'all': self.now.total, 'md5': self.md5}
                fdata = json.dumps(raw_msg).encode() + b'---+++data+++---' + self.now.data
            else:
                raw_msg = {'type': 'data', 'name': self.now.name, 'size': self.now.size, 'part': self.now.part,
                           'all': self.now.total}
                fdata = json.dumps(raw_msg).encode() + b'---+++data+++---' + self.now.data
        print('Sending file:{0} (Part {1}/{2})...'.format(self.now.name, self.now.part + 1, self.now.total), end='')
        self.message_sender(fdata)
        print('Done.', end='\n')
    
    def message_sender(self, message):
        """
        自带随机秒重发机制的消息回发(至少0.2s)
        注意此处传入的参数必须是用json打包好的
        """
        self.time_counter.cancel()
        self.transport.sendto(message)
        self.time_counter = self.loop.call_later(0.2 + random.random(), self.message_sender, message)
    
    def md5_gener(self):
        """计算MD5值"""
        md5 = hashlib.md5()
        with open(self.path, 'rb') as f:
            for line in f:
                md5.update(line)
        self.md5 = md5.hexdigest()


async def file_main(host, port, path, threading_controller, que):
    """
    传输控制类实例构造函数，传输端点在此关闭。
    """
    threading_controller.acquire()
    loop = asyncio.get_running_loop()
    with open(path, 'rb') as fstream:
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: ClientProtocol(file_spliter(fstream), fstream.name, que, threading_controller, loop),
            remote_addr=(host, port))
        try:
            await protocol.on_con_lost
        finally:
            transport.close()


def file_thread(host, port, file, file_at_same_time, que):
    """
    传输线程启动函数。
    """
    threading_controller = threading.BoundedSemaphore(value=file_at_same_time)
    for path in file:
        thread_asyncio = threading.Thread(target=asyncio.run,
                                          args=(file_main(host, port, path, threading_controller, que),))
        thread_asyncio.start()
    thread_asyncio.join()
