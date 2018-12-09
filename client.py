'''
客户端，尝试连接服务端。
当建立连接后发送指定数据。
'''

import socket, time, os, json
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

# 组合并发送文件头信息
file_name = 'test'
file_size = os.path.getsize(file_name)
# 文件分片大小，以后可以自己设定
part = 8
file_data = {'name': file_name, 'size': file_size, 'part': part}
print('File: {0}('.format(file_data['name']) + datatrans.display_file_length(file_data['size']) + ') transmission will begin within 3 seconds.')
soc.send(json.dumps(file_data).encode('utf-8'))
time.sleep(3)
print('Transfer starting...')
# 开始数据传输
datatrans.send_data(soc, addr, file_name)
soc.close()