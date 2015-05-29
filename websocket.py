'''
7D2D map markers Tornado Server
by: Adam Dybczak (RaTilicus)

Note: the Telnet and Tornado/Websocket code have recently been merged to allow exciting possibilities
like in game teleportation using web interface, updating entities via websocket push as opposed to polling ajax.
In the future, other possibilities like game to web to game chat, etc.
The code is in the process of being cleaned up, some things are done inconsistently or incorrectly
(such as how Websocket commands are sent, etc.)  Please bear with me.
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
        self.sockets = WebSocket.sockets = self.settings['sockets']
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
            cursor = self.db.messages.find({'tt': 'post'}, ['_id', 'msg', 'u'], sort=(('_id', 1),), limit=1000)
            while (yield cursor.fetch_next):
                WebSocket._cache.append(cursor.next_object())
            

        print 'WebSocket prepared'

#    def check_origin(self, origin):
#        print 'origin_check', origin
#        return True#bool(re.match(r'^.*?\.mydomain\.com', origin))
        
    @gen.coroutine
    def open(self):
        #sockets = self.settings['sockets']
        self.sid = hash(self)
        self.name = None
        print 'WebSocket opened', self.sid

        # send entered room message
        if self.current_user:
            self.name = self.current_user['username']
        else:
            self.name = 'Anonymous'  #self.request.headers['X-Real-Ip']
        #text = u'%s entered the room' % self.name
        #self.send_msg(text, tt='info')

        # send existing message to newly connected user
        if WebSocket._cache:
            for msg in WebSocket._cache:
                text = u'%s %s: %s' % (msg['_id'].generation_time.strftime('%Y-%m-%d %H:%M:%Sz'), msg['u'], msg['msg'])
                self.send_msg(text, to_all=False, tt='post', id=msg['_id'])

        self.sockets[self.sid] = self
        self.send_userlist()
        self.telnet_parser.send_day_info()

    @gen.coroutine
    def send_userlist(self):
        # send current user list to new user
        '''self.send_msg(u'%d website user(s): %s' % (
            len(self.sockets),
            (', '.join(s.name for s in self.sockets.values() if s.name))),
            to_all=False, tt='info')'''
        
        WebSocket.send_update({
            'tt': 'uu',
            'uc': len(self.sockets),
            'ul': [s.name for s in self.sockets.values() if s.name],
        })



    @gen.coroutine
    def on_message(self, message):
        print 'on_message: %s' % (len(message))

        try:        
            json = json_decode(message)
        except Exception as e:
            print 'on message: json_decode error: %s' % e
            return

        tt = json['tt']

        json['_id'] = id = ObjectId()
        json['u'] = self.name
        json['uid'] = self.current_user['_id'] if self.current_user else None
        if tt == 'post' and not self.current_user:
            json['tt'] = tt = 'msg'

        self.db.messages.insert(json)

        if tt == 'post':
            WebSocket._cache.append(json)

        text = ''

        if tt == 'msg' or tt == 'post':
            text = u'%s %s: %s' % (id.generation_time.strftime('%Y-%m-%d %H:%M:%Sz'), self.name, json['msg'])
            self.send_msg(text, tt=tt, id=id)

        elif tt == 'cmd':
            if json['msg'] == '/u':
                self.send_userlist()

        elif tt == 'tp' and self.current_user:
            print 'teleporting %s to %s' % (self.current_user['_id'], json['tp'])
            self.telnet.write('tele %s %s 1500 %s\n' % (self.current_user['_id'], json['tp']['x'], json['tp']['z']))
            yield gen.sleep(0.75)
            self.telnet.write('tele %s %s %s %s\n' % (self.current_user['_id'], json['tp']['x'], json['tp']['y'], json['tp']['z']))
            self.send_msg(text)

    def send_msg(self, text, to_all=True, tt='msg', id=''):
        #sockets = self.settings['sockets']
        if text:
            json = {
                'tt': tt,
                'msg': text,
                'id': str(id),
            }
            if to_all:
                for s in self.sockets.values():
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

        #sockets = self.settings['sockets']
        if self.sid in self.sockets:
            del self.sockets[self.sid]

        print 'WebSocket closed'

        #text = u'%s left the room' % self.name
        #self.send_msg(text, tt='info')
        self.send_userlist()
