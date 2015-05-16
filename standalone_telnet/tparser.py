'''
7D2D map markers Tornado Server
by: Adam Dybczak (RaTilicus)
'''

import time
import random
import re
from simplejson import dumps as json_encode

class CommandBase(object):
    cmd = ''
    delay = 1
    def __init__(self, db, telnet, ts, telnet_parser):
        self.db = db
        self.telnet = telnet
        self.next = ts
        self.processing_flag = False
        self.telnet_parser = telnet_parser

    def ready(self, ts):
        return not self.processing_flag and ts > self.next

    def done(self):
        return not self.processing_flag

    def send(self, ts):
        if self.processing_flag:
            raise Exception('calling send on %s while processing' % self)
            
        if self.ready(ts):
            #print 'cmd: sending %s' % self
            self.pre_send(ts)
            self.telnet.write('%s\n' % self.cmd)
            self.processing_flag = True
            return True
        else:
            return False

    def processing(self, ts, line):
        'process the line, return True if still processing, False if done'
        if not self.processing_flag:
            return False

        self.processing_flag = self.process_line(ts, line)
        if not self.processing_flag:
            self.next = ts + self.delay
            #print 'cmd: processing done %s' % self
        return self.processing_flag

    def pre_send(self, ts):
        'OVERRIDE THIS: runs at send time'
        pass

    def process_line(self, ts, line):
        'OVERRIDE THIS: process line, return True if expecting more lines, False if done'
        return False


class GTCommand(CommandBase):
    cmd = 'gt'
    delay = 30
    
    def process_line(self, ts, line):
        if line.startswith('Day '):
            print 'GT day ' + line
            self.telnet_parser.day_info = '(%s)' % line
            return False
        return True

class LECommand(CommandBase):
    entity_pat = re.compile('^.*type=([^,]+).*name=([^,]+).*id=(\d+).*pos=\((-?\d+\.\d+), (-?\d+\.\d+), (-?\d+\.\d+)\).*dead=(True|False).*$')

    cmd = 'le'
    delay = 0

    def update_player(self, player_id, data, ts):
        player = self.telnet_parser.players[player_id]
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

    def pre_send(self, ts):
        self.telnet_parser.entities.clear()
        self.telnet_parser.update_entities_flag = False

    def process_line(self, ts, line):    
        if line.startswith('Total of '):
            self.telnet_parser.update_entities()
            return False
        
        try:
            if 'type=Entity' in line and not 'type=EntityCar' in line and not 'EntityItem' in line and 'dead=' in line:
                pat_data = self.entity_pat.findall(line.strip())
                type, name, player_id, x, y, z, dead = pat_data[0]
                player_id=int(player_id)
                data = dict(id=player_id, type=type, name=name, x=float(x), y=float(y), z=float(z), dead=dead=='True')
                self.telnet_parser.entities[player_id] = data
                if type=='EntityPlayer':
                    if player_id in self.telnet_parser.players:
                        self.update_player(player_id, data, ts)
                    else:
                        data.update(md=0, ts=ts, dts=0, new=True)
                        self.telnet_parser.players[player_id] = data
        except Exception, e:
            print 'LE ERROR: findall> ', e, repr(line), pat_data

        return True
    

class TelnetParser(object):
    player_connected_pat = re.compile(r'entityid=(\d+), name=([^,]+), steamid=(\d+)')

    ############### INF ################

    def player_connected(self, line):
        entity_id, username, steam_id = self.player_connected_pat.findall(line[50:])[0]
        player = self.db.players.find_one({'_id': int(steam_id)})
        print 'PLAYER CONNECTED', entity_id, username, steam_id, player
        
        if not player:
            password = '%04d' % random.randrange(0, 9999)
            self.db.players.insert({
                '_id': int(steam_id),
                'eid': int(entity_id),
                'username': username,
                'password': password,
            })
        else:
            password = str(player['password'])
        self.telnet.write('pm %s "7d2d.ratilicus.com (u: %s p: %s)"\n' % (entity_id, username, password))


    def parse_INF(self, line):
        # handle player login
        if 'Player connected' in line:
            self.player_connected(line)
        # handle player messages
        # handle custom commands?
        
    ############# UPDATE ###############

    def __init__(self, db, telnet):
        self.ts = int(time.time())
        self.day_info = ''
        self.db = db
        self.telnet = telnet
        self.entities = {}
        self.players = {}

        self.commands = [
            GTCommand(db, telnet, self.ts, self),
            LECommand(db, telnet, self.ts, self),
        ]
        self.current_command = None

    def send_command(self):
        if not self.current_command or self.current_command.done():
            for cmd in self.commands:
                if cmd.ready(self.ts):
                    self.current_command = cmd
                    #print 'sending %s' % self.current_command
                    self.current_command.send(self.ts)
                    return
            #print 'no ready commands to send (cur: %s)' % self.current_command
        #else:
        #    print 'current command %s not done?' % self.current_command        

    def process_command(self, line):
        if self.current_command and not self.current_command.done():
            self.current_command.processing(self.ts, line)
            
    def update(self):
        self.ts = int(time.time())
        self.send_command()
        lines = self.telnet.read_very_eager()

        if not lines:
            return False

        for line in lines.split('\r\n'):
            if line:
                self.update_line(line)

        return True

    def update_line(self, line):
        if ' INF ' in line:
            self.parse_INF(line)
        else:
            self.process_command(line)

    def update_entities(self):
        for id, player in list(self.players.items()):
            # if last update of player is more than n sec remove from list (logged out)
            if player['dts'] > 10:
                self.players.pop(id)
                    
        with open('/var/www/sdtd/static/entities.js', 'w') as of:
            of.write(json_encode(dict(
                day_info=self.day_info, 
                refresh_rate=2, 
                entities=self.entities)))
