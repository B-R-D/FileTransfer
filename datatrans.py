import time, os

# 文件显示模式：双端
def display_file_length(file_size):
    if file_size < 1:
        return '{0:.1f}B'.format(file_size)
    elif 1 <= file_size < 1048576:
        return '{0:.1f}kB'.format(file_size/1024)
    elif 1048576 <= file_size < 1073741824:
        return '{0:.1f}MB'.format(file_size/1048576)
    else:
        return '{0:.1f}GB'.format(file_size/1073741824)

# 读取文件并发送数据：客户端
def send_data(sock, adr, file_name):
    with open(file_name, 'rb') as transfile:
        content = transfile.read()
        sock.sendall(content)
    print('Upload complete.')
    # 判断是否完全接收文件
    while True:
        comp = sock.recv(18)
        if comp.decode('utf-8') == 'File has received.':
            print('Transmission successfully terminated.')
            break

# 接收数据并保存文件：服务端
def save_data(sock, adr, name, size):
    data = b''
    while len(data) < size:
        print('{:.2f}%'.format(len(data)/size*100))
        data += sock.recv(1450)
    sock.send(b'File has received.')
    with open('test1', 'wb') as transfile:
        transfile.write(data)
    sock.close()