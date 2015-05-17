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

import tornado.web
from bson import ObjectId
from bson.json_util import loads as json_decode, dumps as json_encode
from schemaforms import SchemaForm
from tornado import gen
import tornado.websocket


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
            try:
                self.current_user = yield self.db.players.find_one({'_id': int(user_id)})
            except:
                pass

        if self.request.method in ['POST', 'PUT'] and self.request.body:
            try:
                self.POST = json_decode(self.request.body)
            except Exception, e:
                self.POST = self.request.arguments

    @gen.coroutine
    def render(self, template, **data):
        data['user'] = self.current_user
        if not 'username' in data:
            data['username'] = self.get_argument('username', '')
        super(BaseHandler, self).render(template, **data)

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
        )
        print 'show login form'
        self.set_header('Cache-Control', 'no-cache, must-revalidate')
        self.set_header('Pragma', 'no-cache')
        self.set_header('Expires', 'Sun, 11 Aug 2013 11:00:00 GMT')
        self.render('templates/index.html', **data)


class RecipesHandler(BaseHandler):
    @gen.coroutine
    def get(self):
        ''' recipes page '''
        data=dict()
        print 'show recipes page', data
        self.render('templates/recipes.html', **data)


class AboutHandler(BaseHandler):
    @gen.coroutine
    def get(self):
        ''' about page '''
        data=dict()
        print 'show recipes page', data
        self.render('templates/about.html', **data)


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
        fields = ['id', 'desc', 'x', 'y', 'z', 'public', 'ts', 'eid', 'username']

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
            marker['o'] = self.current_user and (marker.get('eid')==self.current_user['eid']) or False
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

