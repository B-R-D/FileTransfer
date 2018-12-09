'''
服务端，等待客户端的连接。
有连接呼入时接收文件并保存。
'''

import socket, time, json
from multiprocessing import Process
# 导入第三方库
import datatrans, exceptions
from exceptions import *

addr = '0.0.0.0'
soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
soc.bind((addr, 12345))
soc.listen(3)
print('Waiting for incoming tranmission...')

# 先确保建立连接
while True:
    try:
        connection, adr = soc.accept()
        msg = connection.recv(50)
        if msg.decode('utf-8') == 'Established file transmission control, stand by...':
            print('Incoming transmission from {0}:{1}.'.format(adr[0], adr[1]))
            connection.send(b'Connection confirmed.')
            # 获取文件信息
            info = connection.recv(128)
            file_info = json.loads(info.decode('utf-8'))
            print('File: {0}('.format(file_info['name']) + datatrans.display_file_length(file_info['size']) + ')')
            # 开始传输数据
            proc = Process(target = datatrans.save_data, args = (connection, adr, file_info['name'], file_info['size']))
            proc.start()
        else:
            raise ConnectionFailed(addr, port)
    except ConnectionFailed:
        print('Connection from {0}:{1} failed.'.format(adr[0], adr[1]))
	

