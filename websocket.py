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
import time

TP_DELAY_MIN = 10

class WebSocket(tornado.websocket.WebSocketHandler):
    socket_count = 0

    sid = None
    uid = None
    name = None

    sockets = {}
    _cache = []
    _cache_loaded = False

    @gen.coroutine
    def prepare(self):
        ''' handler init
        - set self.db var
        - set self.curent_user (if logged in)
        - set self.POST from request body, decode json if request is json
        '''
        WebSocket.socket_count += 1
        self.sid = WebSocket.socket_count

        self.log('WebSocket prepare')
        self.last_tp = None
        self.sockets = WebSocket.sockets = self.settings['sockets']
        self.db = self.settings['db']
        self.telnet = self.settings['telnet']
        self.telnet_parser = self.settings['telnet_parser']
        self.need_full_update = True

        # preload messages and store them in class-wide variable
        if not WebSocket._cache_loaded:
            self.log('WebSocket loading _cache')
            WebSocket._cache_loaded = True
            del WebSocket._cache[:]
            cursor = self.db.messages.find({'tt': 'post'}, ['_id', 'uid', 'msg', 'u', 'ts'], sort=(('_id', 1),), limit=1000)
            while (yield cursor.fetch_next):
                WebSocket._cache.append(cursor.next_object())

        self.log('WebSocket prepared')

    def log(self, text, *args):
        print '(%s, %s, %s) %s %r' % (self.sid, self.uid, self.name, text, args)

#    def check_origin(self, origin):
#        print 'origin_check', origin
#        return True#bool(re.match(r'^.*?\.mydomain\.com', origin))
        
    @gen.coroutine
    def open(self):
        self.name = None

        self.log('WebSocket opened')

#        self.load_player()

        uid = self.get_secure_cookie("user")
        self.log('loading player', uid)
        if uid:
            self.uid = int(uid)
            self.current_user = yield self.db.players.find_one({'_id': self.uid}, ['_id', 'eid', 'username', 'last_login', 'last_tp'])
            self.name = self.current_user['username']
        else:
            self.name = 'Anonymous'
        self.log('loaded player', self.name)



        self.sockets[self.sid] = self
        self.send_userlist()
        self.telnet_parser.send_day_info()

    @gen.coroutine
    def send_userlist(self):
        self.log('send userlist')
        # send current user list to new user
        WebSocket.send_update({
            'tt': 'uu',
            'uc': len(self.sockets),
#            'ul': [s.name for s in self.sockets.values() if s.name],
            'ul': [s.name if s.name else s.sid for s in self.sockets.values()],
        })

    @gen.coroutine
    def on_message(self, message):
        ts = int(time.time())
        self.log('on_message: %s' % len(message))

        try:        
            json = json_decode(message)
        except Exception as e:
            self.log('on message: json_decode error: %s' % e)
            return

        tt = json['tt']

        json['_id'] = id = ObjectId()
        json['u'] = self.name
        json['uid'] = self.current_user['_id'] if self.current_user else None
        json['ts'] = ts

        if tt == 'post' and not self.current_user:
            # anon users can't create posts
            json['tt'] = tt = 'msg'


        if tt == 'post':
            self.db.messages.insert(json)
            WebSocket._cache.append(json)
        elif tt == 'tp':
            self.db.tp.insert(json)

        text = ''

        if tt == 'msg' or tt == 'post':
            text = u'%s wrote: %s' % (self.name, json['msg'])
            self.send_msg(text, tt=tt, id=id, uid=json['uid'], ts=json['ts'])

        elif tt == 'cmd':
            self.log('commmand', json)
            if json['msg'] == '/posts':
                # send existing message to newly connected user
                if WebSocket._cache:
                    for msg in WebSocket._cache:
                        text = u'%s wrote: %s' % (msg['u'], msg['msg'])
                        self.send_msg(text, to_all=False, tt='post', id=msg['_id'], uid=msg['uid'], ts=msg['ts'])
            elif json['msg'] == '/rm':
                if self.current_user:
                    remove_message = self.db.messages.remove({'uid': self.current_user['_id'], '_id': ObjectId(json['sm'])})
                    yield remove_message
                    WebSocket._cache_loaded = False
                    # TODO send a message to all to remove the post
            elif json['msg'] == '/u':
                self.send_userlist()
        elif tt == 'tp' and self.current_user:
            x, y, z = json['tp']['x'], json['tp']['y'], json['tp']['z']
            if 'last_tp' in self.current_user:
                dt = ts - self.current_user['last_tp']
                if dt < TP_DELAY_MIN * 60:
                    if self.last_tp:
                        dist = (x-self.last_tp[0])**2 + (z-self.last_tp[1])**2
                        if dist > 64:
                            self.send_msg('You can only teleport once every %d min.  Only %2.1f min have passed.' % (TP_DELAY_MIN, dt/60.0), to_all=False, tt='info')
                            return
            
            self.log('teleporting %s to %s' % (self.current_user['_id'], json['tp']))
            self.telnet.write('tele %s %s 1500 %s\n' % (self.current_user['_id'], x, z))
            yield gen.sleep(1.5)
            self.telnet.write('tele %s %s %s %s\n' % (self.current_user['_id'], x, y, z))
            self.current_user['last_tp'] = last_tp = ts
            self.last_tp = (json['tp']['x'], json['tp']['z'])
            upd = self.db.players.update(
                {'_id': self.current_user['_id']}, 
                {'$set': {'last_tp': last_tp}}
            )
            yield udp

    def send_msg(self, text, to_all=True, tt='msg', id='', uid=None, ts=None):
        if text:
            json = {
                'tt': tt,
                'msg': text,
                'id': str(id),
                'uid': uid,
                'ts': ts,
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
        self.log('WebSocket closing')

        if self.sid in self.sockets:
            del self.sockets[self.sid]

        self.log('WebSocket closed')
        self.send_userlist()
