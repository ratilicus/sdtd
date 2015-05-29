#!/usr/bin/python

import time
import telnetlib
import re    


line_pat = re.compile(r'\d+\. (?P<username>[^,]*), id=(?P<id>\d+), steamid=(?P<steamid>\d+), online=(?P<online>True|False), ip=[\d.]*, playtime=(?P<playtime>\d+).*')
slot_pat = re.compile(r'Slot \d+: (\d{3}) * (.*)')


if __name__ == "__main__":
    telnet = telnetlib.Telnet('localhost', 25025)
    telnet.write('loglevel all off\n')
    time.sleep(2)

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
                if int(data['playtime']) < 60:
                    players.append(data)

    print 'scanning players'
    for p in players:
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
                    items.append((item, count))
                    if (
                        'sniperRifle' in item
                        or 'mp5' in item
                        or 'tnt' in item
                    ):
                        suspect = True
        if suspect:
            for item, count in items:
                print 'SUSPECT %s x%s' % (item, count)

#42. bogard_a, id=48569, steamid=76561198097891896, online=False, ip=75.185.4.199, playtime=67 m, seen=2015-05-07 15:21

