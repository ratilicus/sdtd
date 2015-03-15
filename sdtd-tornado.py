#!/usr/bin/python

'''
7D2D map markers Tornado Server
by: Adam Dybczak (RaTilicus)

GET /markers
    List owned and public markers

POST /markers
    Create a new marker

DELETE /markers/<id>
    Delete an existing marker

PUT /markers/<id>
    Update an existing marker


'''

import tornado.web, tornado.ioloop
import motor
from bson import ObjectId
from bson.json_util import loads as json_decode, dumps as json_encode
from schemaforms import SchemaForm
from tornado import gen

class BaseHandler(tornado.web.RequestHandler):
    @gen.coroutine
    def prepare(self):
        ''' handler init
        - set self.db var
        - set self.curent_user (if logged in)
        - set self.POST from request body, decode json if request is json
        '''
        self.db = self.settings['db']
        user_id = self.get_secure_cookie("user")
        if user_id:
            self.current_user = yield db.players.find_one({'_id': int(user_id)})

        if self.request.method in ['POST', 'PUT'] and self.request.body:
            try:
                self.POST = json_decode(self.request.body)
            except Exception, e:
                self.POST = self.request.arguments

    @gen.coroutine
    def json_response(self, data, success=False, errors=[]):
        ''' json response helper '''
        self.write(json_encode({
            'data': data,
            'success': success,
            'errors': errors
        }))
        self.finish()


class IndexHandler(BaseHandler):
    @gen.coroutine
    def get(self):
        ''' home/index page '''
        data=dict(
            login_errors='login_errors' in self.request.arguments,
            username=self.get_argument('username', ''),
            user=self.current_user,
        )
        'show login form'
        self.render('templates/index.html', **data)


class LoginHandler(BaseHandler):
    class LoginForm(SchemaForm):
        schema = {
            'type': 'object',
            'properties': {
                'username': {'type': 'string', 'minLength': 1},
                'password': {'type': 'string', 'minLength': 4},
            },
            'required': ['username', 'password'],
        }
        flatten = ['username', 'password']

    @gen.coroutine
    def post(self):
        'login request'

        form = self.LoginForm(self.POST)
        user = None
        if form.is_valid():
            user = yield self.db.players.find_one({'username': form.cleaned_data['username']})
            if user:
                if user['password'] == form.cleaned_data['password']:
                    self.set_secure_cookie("user", str(user['_id']))
                    self.redirect("/")
                else:
                    user = None
        else:
            print form.errors
        if not user:
            self.redirect(u"/?login_errors=1&username=%s" % form.data.get('username', ''))


class LogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("user")
        self.redirect("/")


class MarkerHandler(BaseHandler):
    class MarkerForm(SchemaForm):
        schema = {
            'type': 'object',
            'properties': {
                'desc': {'type': 'string', 'minLength': 1},
                'x': {'type': 'number'},
                'y': {'type': 'number', 'default': 0.0},
                'z': {'type': 'number'},
                'public': {'type': 'boolean', 'default': True}
            },
            'required': ['desc', 'x', 'z']
        }

    @gen.coroutine
    def get(self):
        'get all markers'

        markers = []
        fields = ['id', 'desc', 'x', 'y', 'z', 'public', 'ts', 'eid', 'player']

        if self.current_user:
            # get user owned markers, and other public markers
            query = {'$or': [
                {'eid': self.current_user['eid']},
                {'eid': {'$ne': self.current_user['eid']}, 'public': True}
            ]}
        else:
            # get public markers
            query = {'public': True}

        cursor = self.db.markers.find(query, fields)
        while (yield cursor.fetch_next):
            marker = cursor.next_object()
            marker['id'] = str(marker.pop('_id'))
            markers.append(marker)

        self.json_response(data=markers, success=True)


    @gen.coroutine
    def post(self):
        'create a new marker'

        form = self.MarkerForm(self.POST)
        if form.is_valid():
            data = form.cleaned_data

            data['_id'] = ObjectId()            
            if self.current_user:
                # create user owned marker
                data['eid'] = self.current_user['eid']
                data['username'] = self.current_user['username']
            else:
                # create anon marker
                data['eid'] = 0
                data['public'] = True  # Anon markers have to be public
                
            self.db.markers.insert(data)

            self.json_response(data={'_id': str(data['_id'])}, success=True)
        else:
            print 'form errors', form.errors
            self.json_response(data={}, success=False, errors=form.errors)

    @gen.coroutine
    def delete(self, id):
        'remove a marker'

        query = {
            '_id': ObjectId(id),
            # if user is logged in, the user can remove owned and anon markers
            # anon users can only remove anon markers
            'eid': ({'$in': [0, self.current_user['eid']]} if self.current_user else 0)
        }
        self.db.markers.remove(query)
        self.json_response(data={}, success=True)

    #@gen.coroutine
    #def put(self, id):
    #    'update a marker'

if __name__ == '__main__':

    db = motor.MotorClient().sdtd
    sockets = {}

    SETTINGS = {
        'cookie_secret': "__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
        "login_url": "/login",
        #'xsrf_cookies': True,
        'autoreload': True,
        'debug': True,
        'db': db,
        'sockets': sockets,
    }

    URLS = [
        (r"^/$", IndexHandler),
        (r"^/login/$", LoginHandler),
        (r"^/logout/$", LogoutHandler),
        (r'^/markers/$', MarkerHandler),
        (r'^/markers/([a-z0-9]+)/$', MarkerHandler),
    ]

    try:
        # update settings based on secrets file (not to be shared with github)
        import __secrets__ as secret
        SETTINGS.update(secret.SETTINGS)
    except:
        pass

    application = tornado.web.Application(URLS, **SETTINGS)
    application.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
