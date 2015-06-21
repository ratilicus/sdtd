'''
7D2D map markers Tornado Server
by: Adam Dybczak (RaTilicus)

Note: the Telnet and Tornado/Websocket code have recently been merged to allow exciting possibilities
like in game teleportation using web interface, updating entities via websocket push as opposed to polling ajax.
In the future, other possibilities like game to web to game chat, etc.
The code is in the process of being cleaned up, some things are done inconsistently or incorrectly
(such as how Websocket commands are sent, etc.)  Please bear with me.
'''

# MOD name
MOD = 'Live Free or Die'

# message of the day (for announcing mod updates, map resets, etc)
MOTD = ''

import time
import random
import re
from simplejson import dumps as json_encode
from tornado import gen
import traceback
import telnetlib
import psutil

class CommandBase(object):
    ''' base class for commands that can be sent via telnet to game server '''
    cmd = ''        # command name
    delay = 1       # min number of seconds between sending the command
    
    def __init__(self, db, ts, telnet_handler):
        self.db = db
        self.next = ts
        self.processing_flag = False
        self.th = telnet_handler

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
#            print 'cmd: sending %s' % self
            self.pre_send(ts)
            self.th.telnet.write('%s\n' % self.cmd)
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
    delay = 15

    def get_stats(self, ts):
        io = psutil.net_io_counters(pernic=True)['eth0']
        if self.last_ts and self.last_ts < ts:
            cpu = psutil.cpu_percent(interval=0)
            mem = psutil.virtual_memory().percent
            io = psutil.net_io_counters(pernic=True)['eth0']
            tsd = ts - self.last_ts
            sent, recv = (io.bytes_sent-self.last_sent)/tsd/1024, (io.bytes_recv-self.last_recv)/tsd/1024
            self.last_ts, self.last_sent, self.last_recv = ts, io.bytes_sent, io.bytes_recv
            return ('CPU: %5.1f%% | MEM: %5.1f%% | NET: &uarr; %.1fkb/s &darr; %.1fkb/s' %
                   (cpu, mem, sent, recv))
        self.last_ts, self.last_sent, self.last_recv = ts, io.bytes_sent, io.bytes_recv
    
    def __init__(self, db, ts, telnet_handler):
        super(GTCommand, self).__init__(db, ts, telnet_handler)
        self.last_ts = None
        self.get_stats(ts)

    def process_line(self, ts, line):
        if line.startswith('Day '):
            stats = self.get_stats(ts)
            data = '%s | %s' % (stats, line)
            print 'GT day: ' + data
            self.th.send_day_info(data)
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
        self.th.entities.clear()
        

    def process_line(self, ts, line):    
        if line.startswith('Total of '):
            # found last line of the telnet output, send partial and full entity updates, and removes
            remove_entities = list(set(self.old_entities.keys()) - set(self.entities.keys()))
            self.th.update_entities(updates=self.updates, entities=self.entities, remove_entities=remove_entities)
            return False
        
        try:
            # process the line from telnet
            if 'type=Entity' in line and not 'type=EntityCar' in line and not 'EntityItem' in line and 'dead=' in line:
                pat_data = self.entity_pat.findall(line.strip())
                type, name, eid, x, y, z, rx, ry, rz, dead, health = pat_data[0]
                eid=int(eid)
                data = dict(id=eid, type=type, name=name, x=float(x), y=float(y), z=float(z), h=float(ry), dead=dead=='True', health=int(health))
                self.th.entities[eid] = data

                self.entities[eid] = data

                # if the entity is new or changed position/etc add it to updates dict
                if not eid in self.old_entities or self.old_entities[eid] != data:
                    self.updates[eid] = data

        except Exception, e:
            print 'LE ERROR: findall: %r> %s \n %s \n %s' % (e, repr(line), pat_data, traceback.print_exc())

        return True


class TelnetHandler(object):
    ''' Parses Telnet information and sends commands
    There are 2 basic communications related to telnet
    - parsing INF entries
    - sending commands and parsing the returned data    
    
    '''
    player_connected_pat = re.compile(r'entityid=(\d+), name=([^,]+), steamid=(\d+)')

    def log(self, text, *args):
        print 'TelnetHandler> %s %r' % (text, args)

    @gen.coroutine
    def player_connected(self, line):
        ''' handle player connections
        - create the player entry if need be
        - send website login info and MOTD
        '''
        entity_id, username, steam_id = self.player_connected_pat.findall(line[50:])[0]
        entity_id = int(entity_id)
        steam_id = int(steam_id)
        player = yield self.db.players.find_one({'_id': steam_id})
        print 'PLAYER CONNECTED', entity_id, username, steam_id, player
        
        if not player:
            password = '%04d' % random.randrange(0, 9999)
            self.db.players.insert({
                '_id': steam_id,
                'eid': entity_id,
                'username': username,
                'password': password,
                'admin': False,
                'last_login': int(time.time())
            })
        else:
            password = str(player['password'])
            self.db.players.update({'_id': steam_id}, {'$set': {
                'eid': entity_id,
                'last_login': int(time.time())
            }})
        self.telnet.write('pm %s "7d2d.ratilicus.com (u: %s p: %s)"\n' % (entity_id, username, password))
        self.telnet.write('pm %s "Please go to that site and read the notes."\n' % (entity_id))
        self.telnet.write('pm %s "Please install the %s mod to avoid nasty problems."\n' % (entity_id, MOD))
        if MOTD:
            self.telnet.write('pm %s "%s"\n' % (entity_id, MOTD))


    def parse_INF(self, line):
        ''' INF handler '''
        # handle player login
        if 'Player connected' in line:
            self.player_connected(line)
        # handle player messages
        # handle custom commands?
        
    def get_day_info(self):
        return self.day_info

    def send_day_info(self, day_info=None):
        ''' send day time info.. called from GT command '''
        if day_info:
            self.day_info = '%s' % day_info

        print 'sdi', self.day_info, day_info
        self.sockets.send_day_info(day_info)

    @gen.coroutine
    def send_teleport_command(self, uid, x, y, z):
        if not self.telnet:
            self.log('send_teleport_command | Error no telnet connection')
            return
        self.log('teleporting %s to (%s, %s, %s)' % (uid, x, y, z))
        self.telnet.write('tele %s %s 1500 %s\n' % (uid, x, z))
        yield gen.sleep(1.5)
        self.telnet.write('tele %s %s %s %s\n' % (uid, x, y, z))
        self.log('teleporting %s done' % (uid))

    def update_entities(self, updates, entities, remove_entities):
        print 'send update: s: %d e: %d u: %d r: %d' % (len(self.sockets), len(entities), len(updates), len(remove_entities))
        self.sockets.send_global_message(
            json={
                'tt': 'ue',
                'ue': updates,
                're': remove_entities
            },
            full_json={
                'tt': 'ue',
                'ue': entities,
                're': remove_entities,
                'full': True
            },
            reset_flag=True
        )

   
    ############# UPDATE ###############

    def __init__(self, db, telnet_host, telnet_port):
        self.ts = time.time()
        self.day_info = ''
        self.db = db
        self.entities = {}
        self.players = {}
        self.blank_line_count = 0
        self.last_cmd = ''
        self.telnet_info = telnet_host, telnet_port

        self.connect_telnet()

        self.commands = [
            GTCommand(db, self.ts, self),
            LECommand(db, self.ts, self),
        ]
        self.current_command = None

    @gen.coroutine
    def connect_telnet(self):
        try:
            self.log('Connecting: %s, %d' % self.telnet_info)
            self.telnet = telnetlib.Telnet(*self.telnet_info)
            self.blank_line_count = 0
            self.current_command_loops = 0
            yield gen.sleep(4)
        except Exception, e:
            self.log('Telnet Connection Failed: %s' % e)
            self.telnet = None

    def set_sockets(self, sockets):
        self.sockets = sockets

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
            if self.current_command_loops > 1000:
                self.reset_current_command('too many loops: %s' % self.current_command_loops)
            else:
                self.current_command_loops += 1
                self.current_command.processing(self.ts, line)

    def reset_current_command(self, reason='N/A'):
        ''' reset current command helper 
        - log reason for reset
        - reset command status and que
        - reconnect telnet (resets are usually due to timeout/telnet disconnect)
        '''


        self.blank_line_count = 0
        self.current_command_loops = 0
        self.current_command.reset()
        self.current_command = None
        print 'resetting current command: %s' % reason

        self.connect_telnet()
            
    def update(self):
        ''' update/process telnet parser
        this gets called periodically (in sdtd-tornado.py)
        - all tparser processes are updated from this
        - sends commands
        - gets data from telnet
        - passes data to current command
        - checks for timeouts
        '''

        if not self.telnet:
            return
        
        self.ts = time.time()
        self.send_command()
        try:
            lines = self.telnet.read_very_eager()
        except EOFError:
            self.reset_current_command('EOF Error: %s' % self.blank_line_count)
            lines = None
            
        if not lines:
            self.blank_line_count +=1
            if self.blank_line_count > 5:
                self.reset_current_command('too many blank lines: %s' % self.blank_line_count)
            self.sockets.ping_all()
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

