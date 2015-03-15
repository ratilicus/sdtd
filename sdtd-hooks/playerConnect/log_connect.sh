#!/usr/bin/python

import sys
import random
import telnetlib
import pymongo


if __name__ == '__main__':
    instance, client_id, entity_id, username, steam_id, ip = sys.argv[1:]
    steam_id = int(steam_id)

    telnet = telnetlib.Telnet('localhost', 25025)

    db = pymongo.connection.Connection().sdtd
    player = db.players.find_one({'_id': steam_id})
    if not player:
        password = '%04d' % random.randrange(0, 9999)
        db.players.insert({
            '_id': steam_id,
            'eid': int(entity_id),
            'username': username,
            'password': password,
            'ip': ip,
            'hide': True,
            'markers': []
        })
        telnet.write('sayplayer %s Welcome %s.  Live map available at: http://7d2d.ratilicus.com/ (password: %s)\n' % (
                     username, username, password))
    else:
        if player['ip'] != ip:
            player['ip'] == ip
            db.players.update({'_id': steam_id}, {'$set': {'ip': ip}})
        password = str(player['password'])
        print player
        telnet.write('sayplayer %s Welcome back %s.  Live map available at: http://7d2d.ratilicus.com/ (password: %s)\n' % (
                     username, username, password))


