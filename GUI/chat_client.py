# coding:utf-8
"""聊天客户端"""

import random
import asyncio
import json


class ClientProtocol:
    """聊天客户端主控制类。"""
    def __init__(self, message, que, loop):
        self.message = message
        self.que = que
        self.loop = loop
        self.transport = None
        self.on_con_lost = loop.create_future()
        self.time_counter = self.loop.call_later(10, self.on_con_lost.set_result, True)

    def connection_made(self, transport):
        """连接建立并发送"""
        self.transport = transport
        cdata = json.dumps({'type': 'chat', 'message': self.message}).encode()
        self.chat_sender(cdata)

    def datagram_received(self, message):
        """
        接收数据报时的行为：
        依据传递的信息执行响应。
        """
        message = json.loads(message)
        if message['type'] == 'chat':
            if message['data'] == 'get' and message['message'] == self.message:
                # 接收到成功回包则回传成功消息
                self.time_counter.cancel()
                self.que.put({'type': 'chat', 'status': 'success'})

    def error_received(self, exc):
        """异常处理函数，先忽略"""
        pass
        
    def connection_lost(self):
        """断开连接的行为"""
        self.que.put({'type': 'chat', 'status': 'failed'})
        
    def chat_sender(self, cdata):
        """数据报的发送行为"""
        self.time_counter.cancel()
        self.transport.sendto(cdata)
        self.time_counter = self.loop.call_later(0.2 + random.random(), self.chat_sender, cdata)


async def chat_main(host, port, message, que):
    """
    传输控制类实例构造函数，传输端点在此关闭。
    控制变量：同时运行的线程数
    数据变量：文件流
    """
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: ClientProtocol(message, que, loop),
        remote_addr=(host, port))
    try:
        await protocol.on_con_lost
    finally:
        transport.close()


def chat_starter(host, port, message, que):
    """
    传输线程启动函数。
    控制变量：同时运行的线程数
    数据变量：消息
    """
    asyncio.run(chat_main(host, port, message, que),)
