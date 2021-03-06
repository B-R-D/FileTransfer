# coding:utf-8
"""
UDP服务端，等待客户端的连接。
有连接呼入时接收文件并保存。
"""
import asyncio
import hashlib
import json
import os
import random
import threading


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


class ServerProtocol(asyncio.DatagramProtocol):
    """服务端主控类"""

    def __init__(self, save_dir, que, loop):
        self.save_dir = save_dir
        self.que = que  # 服务端消息队列
        self.loop = loop
        self.aborted = False  # 中断标志位
        self.transport = None

        self.time_counter = {}  # 计数器字典：{name1: {part1: counter, ...}, ...}
        self.rename = {}  # 重命名字典：{true_name: fake_name}

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        info = json.loads(data.split(b'---+++data+++---')[0])
        if info['type'] == 'message':
            if info['data'] == 'established':
                if info['name'] not in self.time_counter:
                    self.aborted = False  # 清除中断标志位
                    self.rename[info['name']] = self.name_checker(info['name'])
                    self.time_counter[info['name']] = {}  # 新建计时器记录
                    self.que.put({'type': 'server_info', 'message': 'started', 'name': info['name']})
                    self.message_sender({'type': 'message', 'data': 'get', 'name': info['name'], 'part': 0}, addr)
            elif info['data'] == 'terminated':
                print('\nConnection terminated successfully.\n')
            elif info['data'] == 'abort':
                if not self.aborted:  # 只接收一次中断消息
                    self.aborted = True
                    self.transport.sendto(json.dumps({'type': 'message', 'data': 'aborted'}).encode(), addr)
                    for name in self.time_counter:  # 删除队列中的文件
                        try:
                            os.remove(os.path.join(self.save_dir, self.rename[name]))
                        except OSError as e:
                            self.que.put({'type': 'server_info', 'message': 'error', 'detail': repr(e)})
                        self.que.put({'type': 'server_info', 'message': 'aborted'})
                        index = len(self.time_counter[name]) - 1
                        self.time_counter[name][index].cancel()
                    self.time_counter = {}
                    self.rename = {}
        elif info['type'] == 'data':
            data = data.split(b'---+++data+++---')[1]
            if info['name'] in self.time_counter and info['part'] == len(self.time_counter[info['name']]) - 1:
                self.time_counter[info['name']][info['part']].cancel()
                self.time_counter[info['name']][info['part'] + 1] = None  # 插入新值，不接收重复块
                wd = threading.Thread(target=self.write_data, args=(info, data, addr))
                wd.start()
                if len(self.time_counter[info['name']]) - 1 == info['all']:  # 末块行为
                    wd.join()
                    checker = threading.Thread(target=self.md5_checker, args=(info, addr))
                    checker.start()
                    msg = json.dumps({'type': 'message', 'data': 'complete', 'name': info['name']}).encode()
                    self.transport.sendto(msg, addr)
                    self.time_counter.pop(info['name'])
                    self.rename.pop(info['name'])
        elif info['type'] == 'chat':
            self.que.put({'type': 'chat', 'status': 'received', 'message': info['message'], 'from': addr})
            msg = json.dumps({'type': 'chat', 'message': info['message'], 'data': 'get'}).encode()
            self.transport.sendto(msg, addr)

    def connection_lost(self, exc):
        print('Server terminated.')

    def write_data(self, info, data, addr):
        """写入本地数据并调用get消息回发函数。"""
        with open(os.path.join(self.save_dir, self.rename[info['name']]), 'ab') as filedata:
            filedata.write(data)
        if not len(self.time_counter[info['name']]) - 1 == info['all']:  # 非末块则有回送操作
            message = {'type': 'message', 'data': 'get', 'name': info['name'], 'part': info['part'] + 1}
            self.message_sender(message, addr)

    def message_sender(self, message, addr):
        """自带随机秒重发机制的消息回发。"""
        self.transport.sendto(json.dumps(message).encode(), addr)
        self.time_counter[message['name']][message['part']] = \
            self.loop.call_later(random.uniform(0.2, 0.4), self.message_sender, message, addr)

    def md5_checker(self, info, addr):
        """不带重发机制的MD5检查函数。"""
        with open(os.path.join(self.save_dir, self.rename[info['name']]), 'rb') as filedata:
            md5 = hashlib.md5()
            for line in filedata:
                md5.update(line)
        if md5.hexdigest() == info['md5']:
            msg = json.dumps({'type': 'message', 'name': info['name'], 'data': 'MD5_passed'}).encode()
            self.transport.sendto(msg, addr)
            self.que.put({'type': 'server_info', 'message': 'MD5_passed', 'name': info['name']})
        else:
            msg = json.dumps({'type': 'message', 'name': info['name'], 'data': 'MD5_failed'}).encode()
            self.transport.sendto(msg, addr)
            self.que.put({'type': 'server_info', 'message': 'MD5_failed', 'name': info['name']})

    def name_checker(self, name, count=1):
        """
        同名文件检查函数。
        有同名文件就在原名后加序号直到不重名，返回新文件名
        """
        if name in os.listdir(self.save_dir):
            fname, ext = os.path.splitext(name)
            fn = fname.rsplit('_', 1)[0]
            rename = fn + '_' + str(count) + ext
            return self.name_checker(rename, count + 1)
        else:
            return name


async def main(incoming_ip, bind_port, save_dir, que):
    """服务端主函数"""
    loop = asyncio.get_running_loop()
    try:
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: ServerProtocol(save_dir, que, loop),
            local_addr=(incoming_ip, bind_port))
        que.put({'type': 'server_info', 'message': 'ready'})
        await asyncio.sleep(99999999)
    except Exception as e:
        que.put({'type': 'server_info', 'message': 'error', 'detail': repr(e)})
    else:
        transport.close()


def starter(incoming_ip, bind_port, save_dir, que):
    asyncio.run(main(incoming_ip, bind_port, save_dir, que))
