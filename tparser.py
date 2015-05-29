'''
7D2D map markers Tornado Server
by: Adam Dybczak (RaTilicus)

Note: the Telnet and Tornado/Websocket code have recently been merged to allow exciting possibilities
like in game teleportation using web interface, updating entities via websocket push as opposed to polling ajax.
In the future, other possibilities like game to web to game chat, etc.
The code is in the process of being cleaned up, some things are done inconsistently or incorrectly
(such as how Websocket commands are sent, etc.)  Please bear with me.
'''

# message of the day (for announcing mod updates, map resets, etc)
MOTD = ''

import time
import random
import re
from simplejson import dumps as json_encode
from tornado import gen
from websocket import WebSocket
import traceback

class CommandBase(object):
    ''' base class for commands that can be sent via telnet to game server '''
    cmd = ''        # command name
    delay = 1       # min number of seconds between sending the command
    
    def __init__(self, db, telnet, ts, telnet_parser):
        self.db = db
        self.telnet = telnet
        self.next = ts
        self.processing_flag = False
        self.telnet_parser = telnet_parser

    def reset(self):
        ''' reset command status, if command times out, etc '''
        self.processing_flag = False

    def ready(self, ts):
        ''' returns True if command is ready to process '''
        return not self.processing_flag and ts > self.next

    def done(self):
        ''' returns True if command is done processing '''
        return not self.processing_flag

    def send(self, ts):
        ''' send command and init processing state '''
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
        ''' any code you need to run before send
        OVERRIDE THIS, IF NEED BE
        '''
        pass

    def process_line(self, ts, line):
        ''' processes a line from telnet
        return True if expecting more lines, False if done
        OVERRIDE THIS
        '''
        return False


class GTCommand(CommandBase):
    ''' get time command '''
    cmd = 'gt'
    delay = 60

    def process_line(self, ts, line):
        if line.startswith('Day '):
            print 'GT day ' + line
            self.telnet_parser.send_day_info(line)
            return False
        return True

class LECommand(CommandBase):
    ''' list entities command 
    gets the list of entities and compiles a partial and full update list,
    send_update sends the proper version based on websock client needs.
    '''
    entity_pat = re.compile('^.*type=([^,]+).*name=([^,]+).*id=(\d+).*pos=\((-?\d+\.\d+), (-?\d+\.\d+), (-?\d+\.\d+)\).*rot=\((-?\d+\.\d+), (-?\d+\.\d+), (-?\d+\.\d+)\).*dead=(True|False).*health=(\d+).*$')
    entities = {}
    old_entities = {}
    
    cmd = 'le'
    delay = 1

    def pre_send(self, ts):
        # reset entity status
        self.old_entities = self.entities
        self.entities = {}
        self.updates = {}
        self.telnet_parser.entities.clear()
        

    def process_line(self, ts, line):    
        if line.startswith('Total of '):
            # found last line of the telnet output, send partial and full entity updates, and removes
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

            return False
        
        try:
            # process the line from telnet
            if 'type=Entity' in line and not 'type=EntityCar' in line and not 'EntityItem' in line and 'dead=' in line:
                pat_data = self.entity_pat.findall(line.strip())
                type, name, eid, x, y, z, rx, ry, rz, dead, health = pat_data[0]
                eid=int(eid)
                data = dict(id=eid, type=type, name=name, x=float(x), y=float(y), z=float(z), h=float(ry), dead=dead=='True', health=int(health))
                self.telnet_parser.entities[eid] = data

                self.entities[eid] = data

                # if the entity is new or changed position/etc add it to updates dict
                if not eid in self.old_entities or self.old_entities[eid] != data:
                    self.updates[eid] = data

        except Exception, e:
            print 'LE ERROR: findall: %r> %s \n %s \n %s' % (e, repr(line), pat_data, traceback.print_exc())

        return True


class TelnetParser(object):
    ''' Parses Telnet information and sends commands
    There are 2 basic communications related to telnet
    - parsing INF entries
    - sending commands and parsing the returned data    
    
    '''
    player_connected_pat = re.compile(r'entityid=(\d+), name=([^,]+), steamid=(\d+)')

    @gen.coroutine
    def player_connected(self, line):
        ''' handle player connections
        - create the player entry if need be
        - send website login info and MOTD
        '''
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
        if MOTD:
            self.telnet.write('pm %s "%s"\n' % (entity_id, MOTD))


    def parse_INF(self, line):
        ''' INF handler '''
        # handle player login
        if 'Player connected' in line:
            self.player_connected(line)
        # handle player messages
        # handle custom commands?
        

    def send_day_info(self, day_info=None):
        ''' send day time info.. called from GT command '''
        if day_info:
            self.day_info = '%s' % day_info

        print 'sdi', self.day_info, day_info
        WebSocket.send_update({
            'tt': 'ut',
            'ut': self.day_info
        })
   
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
            GTCommand(db, telnet, self.ts, self),
            LECommand(db, telnet, self.ts, self),
        ]
        self.current_command = None

    def send_command(self):
        if not self.current_command or self.current_command.done():
            for cmd in self.commands:
                if cmd.ready(self.ts):
                    self.last_cmd = cmd.cmd
                    self.current_command_loops = 0
                    self.current_command = cmd
                    self.current_command.send(self.ts)
                    return

    def process_command(self, line):
        if self.current_command and not self.current_command.done():
            if self.current_command_loops > 200:
                self.reset_current_command('too many loops: %s' % self.current_command_loops)
            else:
                self.current_command_loops += 1
                self.current_command.processing(self.ts, line)

    @gen.coroutine
    def reset_current_command(self, reason='N/A'):
        ''' reset current command helper 
        - log reason for reset
        - reset command status and que
        - reconnect telnet (resets are usually due to timeout/telnet disconnect)
        '''
        print 'resetting current command: %s' % reason

        self.telnet.open(self.telnet.host, self.telnet.port)
        yield gen.sleep(2)

        self.blank_line_count = 0
        self.current_command_loops = 0
        self.current_command.reset()
        self.current_command = None
            
    def update(self):
        ''' update/process telnet parser
        this gets called periodically (in sdtd-tornado.py)
        - all tparser processes are updated from this
        - sends commands
        - gets data from telnet
        - passes data to current command
        - checks for timeouts
        '''
        self.ts = int(time.time())
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

    def update_line(self, line):
        ''' updates/parses one telnet line at a time
        sends the data to INF handler or command handler
        '''
        if line:
            if ' INF ' in line:
                self.parse_INF(line)
            else:
                self.process_command(line)

