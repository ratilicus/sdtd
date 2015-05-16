import tornado.ioloop
import tornado.iostream
import socket
from tornado import gen
from collections import deque

class SDTDTelnet(object):
    def connect(self):
        print 'connecting'
        socket_instance = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        self.stream = tornado.iostream.IOStream(socket_instance)
        self.stream.connect(("localhost", 25025), self._read_loop)

    @gen.coroutine
    def read_line(self):
    #    return self.queue.popleft() if self.queue else ''
        return self.stream.read_until('\n')

    @gen.coroutine
    def write(self, cmd):
        yield self.stream.write('%s\n' % cmd)
        print 'sent >%s<' % cmd

    ################################################################

    #@gen.coroutine
    def _read_loop(self):
        return
        print 'read loop'
        '''try:
            while True:
                a = yield self.stream.read_until('\n')
                if a:
                    self.queue.append(a.strip())
        except Exception as e:
            print 'read_loop exception %s' % e
            tornado.ioloop.IOLoop.call_later(10, self.connect)'''

    def __init__(self):
        self.queue = deque()
        self.connect()


if __name__ == '__main__':
    telnet = SDTDTelnet()
    #tornado.ioloop.PeriodicCallback(lambda: telnet.write('lkp'), 5000).start()
    tornado.ioloop.IOLoop.instance().start()
