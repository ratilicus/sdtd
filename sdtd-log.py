#!/usr/bin/python

import time
import re
import telnetlib
from simplejson import dumps as json_encode
import pymongo

LOOP_SLEEP_SEC = 2
LOOP_SLEEP_EMPTY_SEC = 60
EMPTY_LOOP_THRESHOLD = 5

entity_pat = re.compile('^.*type=([^,]+).*name=([^,]+).*id=(\d+).*pos=\((-?\d+\.\d+), (-?\d+\.\d+), (-?\d+\.\d+)\).*dead=(True|False).*$')

def update_player(player, data, ts):
    dx = data['x']-player['x']
    dy = data['y']-player['y']
    dz = data['z']-player['z']
    player['md'] = dx*dy+dy*dy+dz*dz
    player['dts'] = player['ts'] - ts
    player['ts'] = ts
    player['new'] = False
    player['x'] = data['x']
    player['y'] = data['y']
    player['z'] = data['z']

def poll(db, telnet):
    '''
    poll server telnet for current entities
    - update public entities list
    - init/update player stats
    '''
    loop_count = 0
    empty_loops = 0
    refresh_rate = LOOP_SLEEP_SEC
    day_info = ''
    entities = {}
    players = {}
    player_pos = []
    while True:
        ts = int(time.time())
        telnet.write('gt\nle\n')
        lines = telnet.read_very_eager()
        entities.clear()
        if lines:
            for line in lines.split('\r\n'):
                if line:
                    if line[31:34] == 'INF':
                        pass
                    elif  line.startswith('Day '):
                        day_info = '(%s)' % line
                    elif 'type=Entity' in line and not 'type=EntityCar' in line and 'dead=' in line:
                        try:
                            pat_data = entity_pat.findall(line.strip())
                            type, name, id, x, y, z, dead = pat_data[0]
                            id=int(id)
                            data = dict(id=id, type=type, name=name, x=float(x), y=float(y), z=float(z), dead=dead=='True')
                            entities[id] = data
                            if type=='EntityPlayer':
                                if id in players:
                                    update_player(players[id], data, ts)
                                else:
                                    data.update(md=0, ts=ts, dts=0, new=True)
                                    players[id] = data
                        except Exception, e:
                            print 'ERROR: findall> ', e, repr(line), pat_data
                        #print '\t', data
            player_pos=[]
            for id, player in list(players.items()):
                # if last update of player is more than n sec remove from list (logged out)
                if player['dts'] > 10:
                    players.pop(id)
                # if moved distance moved is more than n or if player is new log position to db
                elif player['md'] >=5 or player['new']:  # record player pos if player moved some distance or is a new player
                    player_pos.append({'eid': player['id'], 'x': player['x'], 'y': player['y'], 'z': player['z'], 'ts': ts})
            if not players:
                empty_loops += 1
            else:
                empty_loops = 0
                refresh_rate = LOOP_SLEEP_SEC
        else:
            empty_loops += 1
            
        if empty_loops > EMPTY_LOOP_THRESHOLD:
            refresh_rate = LOOP_SLEEP_EMPTY_SEC

        loop_count += 1

        print '%d\tlc: %d (%d)\trr: %d\tle: %d\tlp: %s' % (ts, loop_count, empty_loops, refresh_rate, len(entities), len(players))

        if player_pos:
            print 'update player_pos', player_pos
            db.player_pos.insert(player_pos)

        with open('/var/www/sdtd/static/entities.js', 'w') as of:
            of.write(json_encode(dict(day_info=day_info, refresh_rate=refresh_rate, entities=entities)))

        time.sleep(refresh_rate)
        
if __name__ == "__main__":
    try:
        telnet = telnetlib.Telnet('localhost', 25025)
        db = pymongo.connection.Connection().sdtd
    except:
        time.sleep(5*60)
        raise
    else:
        poll(db, telnet)

