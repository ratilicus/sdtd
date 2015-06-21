import tornado.websocket
from bson import ObjectId
from bson.json_util import loads as json_decode, dumps as json_encode
from tornado import gen
import time

TP_DELAY_MIN = 0

INDEX_MODE = 1+2+4    # map entities + chat + posts

MODE_NAME = {
    INDEX_MODE: 'Map Page',
}


class WebSocketPool(object):
    def __init__(self, db, th):
        ''' Init WebSocketPool
            param: db = database, th = telnet handler
            - init main vars
            - load posts
        '''
        super(WebSocketPool, self).__init__()
        self.db = db
        self.th = th
        self.sockets = {}

        # preload posts
        self.posts = []
        self.load_posts()

    def log(self, text, *args):
        print 'WebSocketPool> %s %r' % (text, args)

    @gen.coroutine
    def load_posts(self):
        cursor = self.db.messages.find({'tt': 'post'}, ['_id', 'uid', 'msg', 'u', 'ts'], sort=(('_id', 1),), limit=1000)
        while (yield cursor.fetch_next):
            self.posts.append(cursor.next_object())


    def create_post(self, json):
        self.db.messages.insert(json)
        self.posts.append(json)


    @gen.coroutine
    def remove_post(self, pid, uid, is_admin=False):
        found = -1
        for i, p in enumerate(self.posts):
            if p['_id'] == pid:
                if is_admin or p['uid'] == uid:
                    found = i
                break
        if found >= 0:
            self.posts.pop(i)
            remove_message = self.db.messages.remove({'_id': pid} if is_admin else {'_id': pid, 'uid': uid})
            yield remove_message
            # TODO send a message to all to remove the post

    def add(self, socket):
        ''' add a socket, send day info, and send updated user list
        '''
        self.sockets[id(socket)] = socket
        self.send_day_info()
        self.send_user_list()

    def remove(self, socket):
        ''' remove a socket and send updated user list
        '''
        del self.sockets[id(socket)]
        self.send_user_list()

    def __iter__(self):
        ''' iterate through all the sockets
        '''
        for s in self.sockets.values():
            yield s

    def __len__(self):
        return len(self.sockets)

    def send_global_message(self, json, full_json=None, reset_flag=False, mode=INDEX_MODE):
        ''' send message to all sockets
        '''
        for s in self:
            if s.mode & mode == 0:
                continue

            if full_json and s.need_full_update:
                s.write_message(full_json)
                if reset_flag:
                    s.need_full_update=False
            else:
                s.write_message(json)

    def send_user_list(self):
        ''' send current user list
        '''
        self.log('send userlist')
        
        # send current user list to new user
        self.send_global_message({
            'tt': 'uu',
            'uc': len(self.sockets),
            'ul': ['%s [%s]' % (s.name, MODE_NAME[s.mode]) for s in self],
        })

    def send_day_info(self, day_info=None):
        ''' send day info
        '''
        self.send_global_message({
            'tt': 'ut',
            'ut': day_info or self.th.get_day_info()
        })

    def ping_all(self):
        self.log('ping_all', len(self.sockets))
        for s in self:
            s.ping('ping')


class WebSocket(tornado.websocket.WebSocketHandler):
    socket_count = 0

    uid = None
    name = None

    @gen.coroutine
    def prepare(self):
        ''' handler init
        - set self.db var
        - set self.curent_user (if logged in)
        - set self.POST from request body, decode json if request is json
        '''

        self.log('WebSocket prepare')
        self.last_tp_coord = None
        self.sockets = self.settings['sockets']
        self.db = self.sockets.db
        self.need_full_update = True    # initially need a full list of all entities, after that updates can be incremental

        self.log('WebSocket prepared')

    def log(self, text, *args):
        print 'Websocket %s, %s, %s> %s %r' % (id(self), self.uid, self.name, text, args)

    @gen.coroutine
    def open(self):
        self.uid = None
        self.name = 'Anonymous'
        self.mode = INDEX_MODE

        self.log('WebSocket opened')

        uid = self.get_secure_cookie("user")
        self.log('loading player', uid)
        if uid:
            self.uid = int(uid)
            self.current_user = yield self.db.players.find_one({'_id': self.uid}, ['_id', 'eid', 'username', 'last_login', 'last_tp', 'admin'])
            self.name = self.current_user['username']
        self.log('loaded player', self.name)
        self.sockets.add(self)

    @gen.coroutine
    def on_message(self, message):
        ts = int(time.time())

        try:        
            json = json_decode(message)
        except Exception as e:
            self.log('on message: json_decode error: %s' % e)
            return

        self.log('on_message: %s' % json)

        tt = json['tt']

        json['_id'] = id = ObjectId()
        json['u'] = self.name
        json['uid'] = self.uid
        json['ts'] = ts

        if tt == 'post' and not self.current_user:
            # anon users can't create posts
            json['tt'] = tt = 'msg'

        if tt == 'post':
            self.sockets.create_post(json)
        elif tt == 'tp':
            self.db.tp.insert(json)

        text = ''

        if tt == 'msg' or tt == 'post':
            text = u'%s wrote: %s' % (self.name, json['msg'])
            self.send_message(text, tt=tt, id=id, uid=json['uid'], ts=json['ts'], to_all=True)

        elif tt == 'page':
            if json['page'] == 'index':
                self.mode = MESSAGE_MODE

        elif tt == 'cmd':
            if json['msg'] == '/posts':
                # send current list of posts
                self.send_posts()

            if json['msg'] == '/resolutions':
                pass

            elif json['msg'] == '/rm':
                # remove a post
                if self.uid:
                    self.sockets.remove_post(ObjectId(json['sm']), self.uid, is_admin=self.current_user['admin'])

            elif json['msg'] == '/u':
                self.send_userlist()

            elif json['msg'] == '/lr':
                print 'sending LR'
                self.sockets.send_global_message({'tt': 'lr'})

        elif tt == 'tp' and self.current_user:
            # teleport player
            x, y, z = json['tp']['x'], json['tp']['y'], json['tp']['z']
            print self.current_user, self.last_tp_coord
            if 'last_tp' in self.current_user:
                dt = ts - self.current_user['last_tp']
                # limit teleporting to once every TP_DELAY_MIN minutes
                # Note: currently keeping tp info in each socket.. so technically someone could do one tp for each open socket
                print 'DT', dt
                if not self.current_user['admin'] and dt < TP_DELAY_MIN * 60:
                    if self.last_tp_coord:
                        dist_sqr = (x-self.last_tp_coord[0])**2 + (z-self.last_tp_coord[1])**2
                        # only limit teleport if it's more than 8 blocks from the last tp coordinates
                        # to allow teleporting to a different height if the player got stuck
                        print 'dist_sqr', dist_sqr
                        if dist_sqr > 64:
                            self.send_message('You can only teleport once every %d min.  Only %2.1f min have passed.' % (TP_DELAY_MIN, dt/60.0), tt='info')
                            return
            self.sockets.th.send_teleport_command(self.uid, x, y, z)
            self.current_user['last_tp'] = last_tp = ts
            self.last_tp_coord = (json['tp']['x'], json['tp']['z'])
            update_last_tp = self.db.players.update(
                {'_id': self.uid}, 
                {'$set': {'last_tp': last_tp}}
            )
            yield update_last_tp

    def send_posts(self):
        ''' send existing message to newly connected user
        '''
        for msg in self.sockets.posts:
            text = u'%s wrote: %s' % (msg['u'], msg['msg'])
            self.send_message(text, to_all=False, tt='post', id=msg['_id'], uid=msg['uid'], ts=msg['ts'])

    def send_message(self, text, to_all=False, tt='msg', id='', uid=None, ts=None):
        ''' send message to user, or if to_all=True to all users
        '''
        if text:
            json = {
                'tt': tt,
                'msg': text,
                'id': str(id),
                'uid': uid,
                'ts': ts,
            }
            if to_all:
                self.sockets.send_global_message(json)
            else:
                self.write_message(json)

    @gen.coroutine
    def on_close(self):
        self.log('WebSocket closing')
        self.sockets.remove(self)
        self.log('WebSocket closed')

