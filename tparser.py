'''
7D2D map markers Tornado Server
by: Adam Dybczak (RaTilicus)
'''

import time
import random
import re
from simplejson import dumps as json_encode
from tornado import gen
from websocket import WebSocket
import traceback

class CommandBase(object):
    cmd = ''
    delay = 1
    allow_repeat = True
    
    def __init__(self, db, telnet, ts, telnet_parser):
        self.db = db
        self.telnet = telnet
        self.next = ts
        self.processing_flag = False
        self.telnet_parser = telnet_parser

    def reset(self):
        self.processing_flag = False

    def ready(self, ts):
        return not self.processing_flag and ts > self.next

    def done(self):
        return not self.processing_flag

    def send(self, ts):
        if self.processing_flag:
            raise Exception('calling send on %s while processing' % self)
            
        if self.ready(ts):
            print 'cmd: sending %s' % self
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
    delay = 60
    allow_repeat = False
    
    def process_line(self, ts, line):
        if line.startswith('Day '):
            print 'GT day ' + line
            self.telnet_parser.day_info = '(%s)' % line

            WebSocket.send_update({
                'tt': 'ut',
                'ut': line
            })


            return False
        return True

class LECommand(CommandBase):
    entity_pat = re.compile('^.*type=([^,]+).*name=([^,]+).*id=(\d+).*pos=\((-?\d+\.\d+), (-?\d+\.\d+), (-?\d+\.\d+)\).*dead=(True|False).*$')
    entities = {}
    old_entities = {}
    
    cmd = 'le'
    delay = 1

    def pre_send(self, ts):
        self.old_entities = self.entities
        self.entities = {}
        self.updates = {}
        self.telnet_parser.entities.clear()
        self.telnet_parser.update_entities_flag = False
        

    def process_line(self, ts, line):    
        if line.startswith('Total of '):
            remove_entities = list(set(self.old_entities.keys()) - set(self.entities.keys()))
            print 'send update: s: %d e: %d u: %d r: %d' % (len(WebSocket.sockets), len(self.entities), len(self.updates), len(remove_entities))
            WebSocket.send_update(
                update_json={
                    'tt': 'ue',
                    'ue': self.updates,
                    're': remove_entities
                },
                full_json={
                    'tt': 'ue',
                    'ue': self.entities,
                    're': remove_entities,
                    'full': True
                },
                reset_flag=True
            )

            #self.telnet_parser.update_entities()
            return False
        
        try:
            if 'type=Entity' in line and not 'type=EntityCar' in line and not 'EntityItem' in line and 'dead=' in line:
                pat_data = self.entity_pat.findall(line.strip())
                type, name, eid, x, y, z, dead = pat_data[0]
                eid=int(eid)
                data = dict(id=eid, type=type, name=name, x=float(x), y=float(y), z=float(z), dead=dead=='True')
                self.telnet_parser.entities[eid] = data

                self.entities[eid] = data

                if not eid in self.old_entities or self.old_entities[eid] != data:
                    self.updates[eid] = data

                '''if type=='EntityPlayer':
                    if eid in self.telnet_parser.players:
                        self.update_player(eid, data, ts)
                    else:
                        data.update(md=0, ts=ts, dts=0, new=True)
                        self.telnet_parser.players[eid] = data'''
        except Exception, e:
            print 'LE ERROR: findall: %r> %s \n %s \n %s' % (e, repr(line), pat_data, traceback.print_exc())

        return True

class TelnetParser(object):
    player_connected_pat = re.compile(r'entityid=(\d+), name=([^,]+), steamid=(\d+)')

    ############### INF ################

    @gen.coroutine
    def player_connected(self, line):
        entity_id, username, steam_id = self.player_connected_pat.findall(line[50:])[0]
        player = yield self.db.players.find_one({'_id': int(steam_id)})
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
        self.telnet.write('pm %s "Please go to that site and read the notes."\n' % (entity_id))
        self.telnet.write('pm %s "Please install the Live Free or Die mod to avoid nasty problems."\n' % (entity_id))


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
        self.blank_line_count = 0
        self.last_cmd = ''

        self.commands = [
#            GTCommand(db, telnet, self.ts, self),
            LECommand(db, telnet, self.ts, self),
        ]
        self.current_command = None

    def send_command(self):
        #print 'send_command', self.current_command, self.current_command.done() if self.current_command else 'N/A'
        if not self.current_command or self.current_command.done():
            for cmd in self.commands:
                #print  'cmd', cmd.ready(self.ts), cmd.processing_flag, self.ts, cmd.next
                if cmd.ready(self.ts):
                    self.last_cmd = cmd.cmd
                    self.current_command_loops = 0
                    self.current_command = cmd
                    self.current_command.send(self.ts)
                    return
            #print 'no ready commands to send (cur: %s)' % self.current_command
        #else:
        #    print 'current command %s not done?' % self.current_command        

    def process_command(self, line):
        if self.current_command and not self.current_command.done():
            if self.current_command_loops > 200:
                self.reset_current_command('too many loops: %s' % self.current_command_loops)
            else:
                self.current_command_loops += 1
                self.current_command.processing(self.ts, line)

    @gen.coroutine
    def reset_current_command(self, reason='N/A'):
        print 'resetting current command: %s' % reason
        self.telnet.open(self.telnet.host, self.telnet.port)
        yield gen.sleep(2)
        self.blank_line_count = 0
        self.current_command_loops = 0
        self.current_command.reset()
        self.current_command = None
            
    def update(self):
        self.ts = int(time.time())
        #print 'update', self.ts
        self.send_command()
        lines = self.telnet.read_very_eager()

        if not lines:
            self.blank_line_count +=1
            if self.blank_line_count > 5:
                self.reset_current_command('too many blank lines: %s' % self.blank_line_count)
            WebSocket.ping_all()
            return False

        self.blank_line_count = 0
        for line in lines.split('\r\n'):
            self.update_line(line)

        return True

    @gen.coroutine
    def parse_ttelnet(self):
        self.ts = int(time.time())
        self.send_command()
        line = yield self.telnet.stream.read_until('\n')
        self.update_line(line)

    def update_line(self, line):
        #print 'update_line', line
        if line:
            if ' INF ' in line:
                self.parse_INF(line)
            else:
                self.process_command(line)

    def update_entities(self):
        '''for id, player in list(self.players.items()):
            # if last update of player is more than n sec remove from list (logged out)
            if player['dts'] > 10:
                self.players.pop(id)'''

        #print 'update_entities: players: %d, entities: %d' % (len(self.players), len(self.entities))
                    
        with open('/var/www/sdtd/static/entities.js', 'w') as of:
            of.write(json_encode(dict(
                day_info=self.day_info, 
                refresh_rate=2, 
                entities=self.entities)))
