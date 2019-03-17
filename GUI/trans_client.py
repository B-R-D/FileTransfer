# coding:utf-8
"""
UDP客户端，尝试连接服务端。
当建立连接后发送指定数据。
"""
import asyncio
import hashlib
import json
import os
import random
import threading
import time


class FilePart:
    """文件信息类"""

    def __init__(self, name, size, part, total, data):
        self.name = name
        self.size = size
        self.part = part
        self.total = total
        self.data = data


class ClientProtocol(asyncio.DatagramProtocol):
    """客户端主控类。"""

    def __init__(self, fstream, que, tc, loop):
        self.fstream = fstream  # 文件流
        self.que = que  # 客户端消息队列
        self.tc = tc  # 多线程控制
        self.loop = loop

        self.transport = None
        self.on_con_lost = loop.create_future()
        self.time_counter = self.loop.call_later(10, self.on_con_lost.set_result, True)
        if fstream and tc:  # 判定是否发送中断消息
            self.path = fstream.name
            size = os.path.getsize(self.path)
            total = size // 65000 + 1
            self.gener = (FilePart(os.path.split(self.path)[1], size, i, total, fstream.read(65000))
                          for i in range(total))
            self.now = next(self.gener)
            self.md5 = None
            self.thread_md5 = None  # MD5计算线程

    def connection_made(self, transport):
        """连接建立时的行为。"""
        self.transport = transport
        if self.fstream and self.tc:  # 发送文件时开始计算MD5值
            msg = json.dumps({'type': 'message', 'data': 'established', 'name': os.path.split(self.path)[1]}).encode()
            self.thread_md5 = threading.Thread(target=self.md5_gener)
            self.thread_md5.start()
        else:  # 发送中断包
            msg = json.dumps({'type': 'message', 'data': 'abort'}).encode()
            time.sleep(0.5)  # 防止服务端还没新建计时器实例
        self.message_sender(msg)

    def datagram_received(self, data, addr):
        """接收数据报时的行为。"""
        message = json.loads(data)
        if message['type'] == 'message':
            if message['data'] == 'complete':
                if message['name'] == self.now.name:
                    self.time_counter.cancel()
            elif message['data'] == 'MD5_passed':  # 向主进程传递MD5信息并释放锁
                self.que.put({'type': 'info', 'name': message['name'], 'message': 'MD5_passed'})
                msg = json.dumps({'type': 'message', 'data': 'terminated'}).encode()
                self.transport.sendto(msg)
                self.tc.release()
                self.fstream.close()
            elif message['data'] == 'MD5_failed':
                self.que.put({'type': 'info', 'name': message['name'], 'message': 'MD5_failed'})
                msg = json.dumps({'type': 'message', 'data': 'terminated'}).encode()
                self.transport.sendto(msg)
                self.tc.release()
                self.fstream.close()
            elif message['data'] == 'get':
                if message['part'] == self.now.part and message['name'] == self.now.name:
                    # 接收到成功回包则更新进度条消息并发送下一个包
                    self.time_counter.cancel()
                    self.que.put({'type': 'prog', 'name': message['name'], 'part': message['part']})
                    try:
                        self.file_sender()
                        self.now = next(self.gener)
                    except StopIteration:
                        self.fstream.close()
            elif message['data'] == 'aborted':
                self.time_counter.cancel()
                self.que.put({'type': 'info', 'message': 'aborted', 'name': 'None'})
                self.transport.close()

    def connection_lost(self, exc):
        """连接断开时的行为。"""
        if self.fstream:
            self.fstream.close()
        self.on_con_lost.set_result(True)

    def file_sender(self):
        """数据报的发送行为。"""
        if self.md5:
            raw_msg = {'type': 'data', 'name': self.now.name, 'size': self.now.size, 'part': self.now.part,
                       'all': self.now.total, 'md5': self.md5}
        else:
            # MD5未计算完成则判定当前是否为末块：
            # 是则等待MD5计算，不是则继续发送
            if self.now.part + 1 == self.now.total:
                self.thread_md5.join()
                raw_msg = {'type': 'data', 'name': self.now.name, 'size': self.now.size, 'part': self.now.part,
                           'all': self.now.total, 'md5': self.md5}
            else:
                raw_msg = {'type': 'data', 'name': self.now.name, 'size': self.now.size, 'part': self.now.part,
                           'all': self.now.total}
        fdata = json.dumps(raw_msg).encode() + b'---+++data+++---' + self.now.data
        self.message_sender(fdata)

    def message_sender(self, message):
        """
        自带随机秒重发机制的消息回发(0.1-0.3s)。
        传入参数必须用json打包
        """
        self.time_counter.cancel()
        self.transport.sendto(message)
        self.time_counter = self.loop.call_later(random.uniform(0.1, 0.3), self.message_sender, message)

    def md5_gener(self):
        md5 = hashlib.md5()
        with open(self.path, 'rb') as f:
            for line in f:
                md5.update(line)
        self.md5 = md5.hexdigest()


async def main(host, port, path, threading_controller, que):
    """传输控制主函数，传输端点在此关闭。"""
    loop = asyncio.get_running_loop()
    if path and threading_controller:  # 正常传输
        threading_controller.acquire()
        fstream = open(path, 'rb')
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: ClientProtocol(fstream, que, threading_controller, loop),
            remote_addr=(host, port))
    else:  # 中断传输
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: ClientProtocol(None, que, None, loop),
            remote_addr=(host, port))
    try:
        await protocol.on_con_lost
    finally:
        transport.close()


def starter(host, port, file, file_at_same_time, que):
    """传输线程启动函数。"""
    if file and file_at_same_time:
        threading_controller = threading.BoundedSemaphore(value=file_at_same_time)
        for path in file:
            thread_asyncio = threading.Thread(target=asyncio.run,
                                              args=(main(host, port, path, threading_controller, que),))
            thread_asyncio.start()
    else:
        thread_asyncio = threading.Thread(target=asyncio.run,
                                          args=(main(host, port, [], None, que),))
        thread_asyncio.start()
    thread_asyncio.join()
