# coding:utf-8
"""UDP聊天客户端。"""
import asyncio
import json
import random


class ClientProtocol(asyncio.DatagramProtocol):
    """聊天客户端主控制类。"""

    def __init__(self, message, que, loop):
        self.message = message
        self.que = que  # 服务端消息队列
        self.loop = loop
        self.transport = None
        self.on_con_lost = loop.create_future()
        self.time_counter = self.loop.call_later(10, self.on_con_lost.set_result, True)

    def connection_made(self, transport):
        """连接建立并发送消息。"""
        self.transport = transport
        cdata = json.dumps({'type': 'chat', 'message': self.message}).encode()
        self.chat_sender(cdata)

    def datagram_received(self, message, addr):
        message = json.loads(message)
        if message['type'] == 'chat':
            if message['data'] == 'get' and message['message'] == self.message:
                self.time_counter.cancel()
                self.que.put({'type': 'chat', 'status': 'success'})

    def connection_lost(self, exc):
        """断开连接时向队列发送失败消息。"""
        self.que.put({'type': 'chat', 'status': 'failed'})

    def chat_sender(self, cdata):
        """"""
        self.time_counter.cancel()
        self.transport.sendto(cdata)
        self.time_counter = self.loop.call_later(random.uniform(0.2, 0.5), self.chat_sender, cdata)


async def chat_main(host, port, message, que):
    """传输控制类实例构造函数，传输端点在此关闭。"""
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: ClientProtocol(message, que, loop),
        remote_addr=(host, port))
    try:
        await protocol.on_con_lost
    finally:
        transport.close()


def chat_starter(host, port, message, que):
    """传输线程启动函数。"""
    asyncio.run(chat_main(host, port, message, que), )
