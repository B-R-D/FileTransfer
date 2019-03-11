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


class ServerProtocol(object):
    def __init__(self, save_dir, que, loop):
        self.save_dir = save_dir
        self.que = que
        self.loop = loop
        self.transport = None
        # 计数器字典：{name1: {part1: counter, ...}, ...}
        self.time_counter = {}

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        info = json.loads(data.split(b'---+++data+++---')[0])
        if info['type'] == 'message':
            if info['data'] == 'established':
                # 新建计时器记录
                if info['name'] not in self.time_counter:
                    self.time_counter[info['name']] = {}
                    self.que.put({'type': 'server_info', 'message': 'started', 'name': info['name']})
                    self.message_sender({'type': 'message', 'data': 'get', 'name': info['name'], 'part': 0}, addr)
            elif info['data'] == 'terminated':
                pass
                print('\nConnection terminated successfully.\n')
            elif info['data'] == 'abort':
                for name in self.time_counter:
                    index = len(self.time_counter[name]) - 1
                    self.time_counter[name][index].cancel()
                    os.remove(os.path.join(self.save_dir, name))
                self.time_counter = {}
                message = {'type': 'message', 'data': 'aborted'}
                self.transport.sendto(json.dumps(message).encode(), addr)
                print('\nTransmission aborted by client.\n')
        elif info['type'] == 'data':
            data = data.split(b'---+++data+++---')[1]
            if info['name'] in self.time_counter and info['part'] == len(self.time_counter[info['name']]) - 1:
                self.time_counter[info['name']][info['part']].cancel()
                self.time_counter[info['name']][info['part'] + 1] = None
                wd = threading.Thread(target=self.write_data, args=(info, data, addr))
                wd.start()
                if len(self.time_counter[info['name']]) - 1 == info['all']:
                    wd.join()
                    self.time_counter.pop(info['name'])
                    checker = threading.Thread(target=self.md5_checker, args=(info, addr))
                    checker.start()
                    msg = json.dumps({'type': 'message', 'data': 'complete', 'name': info['name']}).encode()
                    self.transport.sendto(msg, addr)
                    print('\nFile: {0}({1}) transmission complete.\n'
                          .format(info['name'], display_file_length(info['size'])))
        elif info['type'] == 'chat':
            self.que.put({'type': 'chat', 'status': 'received', 'message': info['message'], 'from': addr})
            msg = json.dumps({'type': 'chat', 'message': info['message'], 'data': 'get'}).encode()
            self.transport.sendto(msg, addr)

    def connection_lost(self):
        print('Server terminated.')

    def write_data(self, info, data, addr):
        """写入本地数据并调用get消息回发函数"""
        with open(os.path.join(self.save_dir, info['name']), 'ab') as filedata:
            filedata.write(data)
        # 非末块则有回送操作(这里是用插入新值封住了接收重复块)
        if not len(self.time_counter[info['name']]) - 1 == info['all']:
            message = {'type': 'message', 'data': 'get', 'name': info['name'], 'part': info['part'] + 1}
            self.message_sender(message, addr)

    def message_sender(self, message, addr):
        """自带随机秒重发机制的消息回发"""
        self.transport.sendto(json.dumps(message).encode(), addr)
        self.time_counter[message['name']][message['part']] = \
            self.loop.call_later(random.uniform(0.2, 0.5), self.message_sender, message, addr)

    def md5_checker(self, info, addr):
        """MD5检查函数，不带重发机制"""
        with open(os.path.join(self.save_dir, info['name']), 'rb') as filedata:
            md5 = hashlib.md5()
            for line in filedata:
                md5.update(line)
        if md5.hexdigest() == info['md5']:
            msg = json.dumps({'type': 'message', 'name': info['name'], 'data': 'MD5_passed'}).encode()
            self.transport.sendto(msg, addr)
            self.que.put({'type': 'server_info', 'message': 'MD5_passed', 'name': info['name']})
            # print('\n', info['name'], 'MD5 checking passed.\n')
        else:
            msg = json.dumps({'type': 'message', 'name': info['name'], 'data': 'MD5_failed'}).encode()
            self.transport.sendto(msg, addr)
            self.que.put({'type': 'server_info', 'message': 'MD5_failed', 'name': info['name']})
            # print('\n', info['name'], 'MD5 checking failed.\n')


async def main(incoming_ip, bind_port, save_dir, que):
    """服务端主函数"""
    loop = asyncio.get_running_loop()
    try:
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: ServerProtocol(save_dir, que, loop),
            local_addr=(incoming_ip, bind_port))
        que.put({'type': 'server_info', 'message': 'ready'})
        # print('Waiting for incoming transmission...')
        await asyncio.sleep(99999999)
    except Exception as e:
        que.put({'type': 'server_info', 'message': 'error', 'detail': repr(e)})
    else:
        transport.close()


def starter(incoming_ip, bind_port, save_dir, que):
    asyncio.run(main(incoming_ip, bind_port, save_dir, que))
