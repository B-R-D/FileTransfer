# coding:utf-8
'''
聊天客户端
'''
import os, threading, random, hashlib, asyncio, json
from multiprocessing import Queue

class ClientProtocol:
    '''
    客户端主控制类。
    数据变量：文件生成器，文件路径；
    控制变量：与主进程的消息队列，同时传输文件数控制，消息循环，传输端点，自动重发。
    '''
    def __init__(self, message, que, loop):
        self.message = message
        self.que = que
        self.loop = loop
        self.transport = None
        self.on_con_lost = loop.create_future()
        self.time_counter = self.loop.call_later(10, self.on_con_lost.set_result, True)

    def connection_made(self, transport):
        '''连接建立并发送'''
        self.transport = transport
        self.chat_sender()

    def datagram_received(self, message, addr):
        '''
        接收数据报时的行为：
        依据传递的信息执行响应。
        '''
        message = json.loads(message)
        if message['type'] == 'chat':
            if message['data'] == 'get' and message['message'] == self.message:
                # 接收到成功回包则回传成功消息
                self.time_counter.cancel()
                self.que.put({'type':'chat', 'status':'success'})

    def error_received(self, exc):
        '''异常处理函数，先忽略'''
        pass
        
    def connection_lost(self, exc):
        '''连接断开时的行为'''
        self.que.put({'type':'chat', 'status':'failed'})
        
    def chat_sender(self):
        '''数据报的发送行为'''
        cdata = json.dumps({'type':'chat','message':self.message}).encode()
        print('Sending message to {0}: {1}...'.format(self.transport.get_extra_info('peername'), self.message), end='')
        self.transport.sendto(cdata)
    
async def chat_main(host, port, message, que):
    '''
    传输控制类实例构造函数，传输端点在此关闭。
    控制变量：同时运行的线程数
    数据变量：文件流
    '''
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: ClientProtocol(message, que, loop),
        remote_addr=(host, port))
    try:
        await protocol.on_con_lost
    finally:
        transport.close()

def chat_starter(host, port, message, que):
    '''
    传输线程启动函数。
    控制变量：同时运行的线程数
    数据变量：文件路径列表
    '''
    asyncio.run(chat_main(host, port, message, que),)