'''
7D2D map markers Tornado Server
by: Adam Dybczak (RaTilicus)
'''

import tornado.websocket
from bson import ObjectId
from bson.json_util import loads as json_decode, dumps as json_encode
from tornado import gen


class WebSocket(tornado.websocket.WebSocketHandler):
    sid = None
    name = None

    sockets = {}
    _cache = None

    @gen.coroutine
    def prepare(self):
        ''' handler init
        - set self.db var
        - set self.curent_user (if logged in)
        - set self.POST from request body, decode json if request is json
        '''
        print 'WebSocket prepare'
        WebSocket.sockets = self.settings['sockets']
        self.db = self.settings['db']
        self.telnet = self.settings['telnet']
        self.telnet_parser = self.settings['telnet_parser']
        self.need_full_update = True

        user_id = self.get_secure_cookie("user")
        if user_id:
            self.current_user = yield self.db.players.find_one({'_id': int(user_id)})

        # preload messages and store them in class-wide variable
        if WebSocket._cache is None:
            print 'WebSocket loading _cache'
            WebSocket._cache = []
            cursor = self.db.messages.find({'tt': 'msg'}, ['_id', 'msg', 'u'], sort=(('_id', 1),), limit=1000)
            while (yield cursor.fetch_next):
                WebSocket._cache.append(cursor.next_object())
            

        print 'WebSocket prepared'

#    def check_origin(self, origin):
#        print 'origin_check', origin
#        return True#bool(re.match(r'^.*?\.mydomain\.com', origin))
        
    @gen.coroutine
    def open(self):
        sockets = self.settings['sockets']
        self.sid = hash(self)
        self.name = None
        print 'WebSocket opened', self.sid

        # send entered room message
        if self.current_user:
            self.name = self.current_user['username']
        else:
            self.name = 'Anonymous'  #self.request.headers['X-Real-Ip']
        text = u'%s entered the room' % self.name
        self.send_msg(text)

        # send existing message to newly connected user
        if WebSocket._cache:
            for msg in WebSocket._cache:
                text = u'%s %s: %s' % (msg['_id'].generation_time.strftime('%Y-%m-%d %H:%M:%Sz'), msg['u'], msg['msg'])
                self.send_msg(text, to_all=False)

        # send current user list to new user
        users = []
        self.send_msg(u'%d website user(s): %s' % (
            len(sockets),
            (', '.join(s.name for s in sockets.values() if s.name))),
            to_all=False)

        sockets[self.sid] = self

        self.telnet_parser.send_day_info()


    @gen.coroutine
    def on_message(self, message):
        print 'on_message: %s' % (len(message))

        try:        
            json = json_decode(message)
        except Exception as e:
            print 'on message: json_decode error: %s' % e
            return

        json['_id'] = id = ObjectId()
        json['u'] = self.name
        self.db.messages.insert(json)
        if json['tt']=='msg':
            WebSocket._cache.append(json)

        tt = json['tt']
        text = ''

        if tt == 'msg':
            text = u'%s %s: %s' % (id.generation_time.strftime('%Y-%m-%d %H:%M:%Sz'), self.name, json['msg'])

        elif tt == 'tp' and self.current_user:
            print 'teleporting %s to %s' % (self.current_user['_id'], json['tp'])
            self.telnet.write('tele %s %s 1500 %s\n' % (self.current_user['_id'], json['tp']['x'], json['tp']['z']))
            yield gen.sleep(0.75)
            self.telnet.write('tele %s %s %s %s\n' % (self.current_user['_id'], json['tp']['x'], json['tp']['y'], json['tp']['z']))
            
            
        print text

        if text:
            self.send_msg(text)

    def send_msg(self, text, to_all=True):
        sockets = self.settings['sockets']
        if text:
            json = json_encode({
                'tt': 'msg',
                'msg': text
            })
            if to_all:
                for s in sockets.values():
                    s.write_message(json)
            else:
                self.write_message(json)

    @classmethod
    def send_update(cls, update_json, full_json=None, reset_flag=False):
        for s in WebSocket.sockets.values():
            if full_json and s.need_full_update:
                s.write_message(full_json)
                if reset_flag:
                    s.need_full_update=False
            else:
                s.write_message(update_json)

    @classmethod
    def ping_all(cls):
        print 'ping_all', len(WebSocket.sockets)
        for s in WebSocket.sockets.values():
            s.ping('ping')

    @gen.coroutine
    def on_close(self):
        print 'WebSocket closing', self.sid

        sockets = self.settings['sockets']
        if self.sid in sockets:
            del sockets[self.sid]

        print 'WebSocket closed'

        text = u'%s left the room' % self.name
        self.send_msg(text)

