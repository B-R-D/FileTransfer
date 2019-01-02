'''
UDP服务端，等待客户端的连接。
有连接呼入时接收文件并保存。
'''
import os, time, json, asyncio, hashlib

class ServerProtocol:
    def connection_made(self, transport):
        self.transport = transport
    def datagram_received(self, data, addr):
        message = data.decode()
        print(message)
        # 发送数据
        self.transport.sendto(b'Done', addr)

async def main():
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: ServerProtocol(),
        local_addr=('0.0.0.0', 12345))
    print('Waiting for incoming transmission...')
    try:
        await asyncio.sleep(3600)
    finally:
        transport.close()

asyncio.run(main())