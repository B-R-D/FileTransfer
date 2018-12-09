'''
客户端，尝试连接服务端。
当建立连接后发送指定数据。
'''

import socket, time, os
# 导入第三方库
import datatrans, exceptions

addr = '192.168.1.9'
soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# 建立连接
soc.connect((addr, 12345))
soc.send(b'Established file transmission control, stand by...')
# 等待消息循环
while True:	
    d = soc.recv(46)
    if d.decode('utf-8') == 'Connection confirmed.':
        break
    elif d:
        print(d.decode('utf-8'))
        d = ''

file_name = 'test'
# 获取文件大小等属性
file_data = datatrans.file_info(file_name)
print('File: {0}('.format(file_name) + datatrans.display_file_length(file_size) + ') transmission will begin within 3 seconds.')
soc.send(json.dumps(file_data).encode('utf-8'))
time.sleep(3)
print('Transfer starting...')
# 开始数据传输
datatrans.send_data(soc, addr, file_name)
soc.close()