#!/usr/bin/python

'''
7D2D map markers Tornado Server
by: Adam Dybczak (RaTilicus)
'''

import time
import tornado.web, tornado.ioloop
import motor
from bson.json_util import loads as json_decode, dumps as json_encode
from tornado import gen

from handlers import IndexHandler, RecipesHandler, AboutHandler, LoginHandler, LogoutHandler, MarkerHandler
from websocket import WebSocket
#from ttelnet import SDTDTelnet
import telnetlib
from tparser import TelnetParser

if __name__ == '__main__':
    print 'START'

    db = motor.MotorClient().sdtd
    sockets = {}

    #telnet = SDTDTelnet()
    telnet = telnetlib.Telnet('localhost', 25025)
    telnet_parser = TelnetParser(db, telnet)

    SETTINGS = {
        't': int(time.time()),
        'cookie_secret': "__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
        "login_url": "/login",
        #'xsrf_cookies': True,
        'autoreload': True,
        #'debug': True,
        'db': db,
        'telnet': telnet,
        'telnet_parser': telnet_parser,
        'sockets': sockets,
    }

    URLS = [
        (r"^/$", IndexHandler),
        (r"^/recipes/$", RecipesHandler),
        (r"^/about/$", AboutHandler),
        (r'/ws/', WebSocket),
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
    tornado.ioloop.PeriodicCallback(telnet_parser.update, 1000).start()
    tornado.ioloop.IOLoop.instance().start()
    
    print 'END'

