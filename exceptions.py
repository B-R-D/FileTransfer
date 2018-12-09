# 自定义传输异常
class ConnectionFailed(Exception):
    def __init__(self, addr, port):
        self.addr = addr
        self.port = port
