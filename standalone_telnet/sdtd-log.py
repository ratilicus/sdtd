#!/usr/bin/python

import time
import telnetlib
from simplejson import dumps as json_encode
import pymongo

from tparser import TelnetParser

LOOP_SLEEP_SEC = 2
LOOP_SLEEP_EMPTY_SEC = 60
EMPTY_LOOP_THRESHOLD = 5

def poll(db, telnet):
    '''
    poll server telnet for current entities
    - update public entities list
    - init/update player stats
    '''
    loop_count = 0
    empty_loops = 0
    refresh_rate = LOOP_SLEEP_SEC
    gt_count = 0
    no_reply = 0
    #telnet.write('loglevel INF false\n')
    
    telnet_parser = TelnetParser(db, telnet)
    
    while True:
        '''
        if no_reply==0:
            cmds=[]
            if gt_count<=0:
                cmds.append('gt\n')
                gt_count=25
            gt_count-=1
            cmds.append('le\n')
            telnet.write(''.join(cmds))
            time.sleep(1)
        no_reply=0
        '''

        if telnet_parser.update():

            if not telnet_parser.players:
                empty_loops += 1
            else:
                empty_loops = 0
                refresh_rate = LOOP_SLEEP_SEC
                
            if empty_loops > EMPTY_LOOP_THRESHOLD:
                refresh_rate = LOOP_SLEEP_EMPTY_SEC

            loop_count += 1

            print '%d\tlc: %d (%d)\trr: %d\tle: %d\tlp: %s' % (
                telnet_parser.ts, loop_count, empty_loops, refresh_rate, len(telnet_parser.entities), len(telnet_parser.players))

        else:
            print '-'
            no_reply=1

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

