#!/usr/bin/python

import time
import telnetlib
import re    


line_pat = re.compile(r'\d+\. (?P<username>[^,]*), id=(?P<id>\d+), steamid=(?P<steamid>\d+), online=(?P<online>True|False), ip=[\d.]*, playtime=(?P<playtime>\d+).*')
slot_pat = re.compile(r'Slot \d+: (\d{3}) * (.*)')

ban_pat = re.compile(r'^  \d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2} - (\d+) -.*$')


if __name__ == "__main__":
    telnet = telnetlib.Telnet('localhost', 25025)
    telnet.write('loglevel all off\n')
    time.sleep(2)
    telnet.write('ban list\n')
    time.sleep(2)
    line = telnet.read_until('Ban list entries:')
    line = telnet.read_until('\n')
    ban_list = []
    cont = True
    while cont:
        line = telnet.read_until('\n', 1)
        print 'line >%s<' % line
        if not line.strip():
            cont = False
        else:
            steamid =  ban_pat.findall(line)
            if steamid:
                ban_list.extend(steamid)

    print 'banned>', ban_list

    telnet.write('lkp\n')
    cont = True

    players = []
   
    print 'getting player list'
    while cont:
        line = telnet.read_until('\n')
        print 'line>', line
        if line.startswith('Total'):
            cont = False
        else:
            result = line_pat.match(line)
            if result:
                #print 'user>', result.groupdict()
                data = result.groupdict()
                if int(data['playtime']) < 300:
                    players.append(data)

    print 'scanning players'
    for p in players:
        if p['steamid'] in ban_list:
            print 'player %s is already banned... skipping' % p['steamid']
            continue
        print 'scanning', p
        suspect = False
        items = []
        telnet.write('si %s\n' % p['steamid'])
        ct = 0
        while ct < 3:
            line = telnet.read_until('\n', 0.25)
            if not line:
                time.sleep(0.1)
                ct+=1
            else:
                result = slot_pat.findall(line)
                if result:
                    count, item = result[0]
#                    print item, count
                    if (
                        'sniperRifle' in item
                        or 'mp5' in item
                        or 'tnt' in item
                        or 'reinforcedConcrete' in item
                    ):
                        suspect = True
                        items.append((item, count, True))
                    else:
                        items.append((item, count, False))

        if suspect:
            for item, count, suspect_item in items:
                print 'SUSPECT %s x%s   %s' % (item, count, '<- SUSPECT' if suspect_item else '')

