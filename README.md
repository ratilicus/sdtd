# 7d2d
7 Days To Die

Hi I'm RaTilicus (Adam Dybczak)
this is the code for my 7D2D website hosted at http://7d2d.ratilicus.com

## Main Features of the website:

### Day Time/Live player list
- Current in-game Day and time
- Live list of players and their health currently in the game 
  (if clicked the map follows that player around)

### Map
- Updated top down view of the in-game world.
- Current entities/players in the world
- POI markers created by players indicating points of interest
- If a spot on map is clicked a bar below the map displays exact coordinates and
  allows web user to create a POI marker at that spot
  (if the web user is logged in to the website, and playing inside the game,
   they can also teleport that their player to that location in the map)

### Chat
- Posted messages that logged in users have written (where to download the mods, etc)
- Live Chat that any web user can write (this only goes to current web users only)
- Entry for posts/chat messages
- List of current web users


### Installation/My Server Setup

#### Requirements:
- Ubuntu 12.04 server (other linux distros should work as well)
- 7d2d game installed and running per: https://7dtd.illy.bz/
  - if using different installation method then need to install
    Alloc's Server mods (https://7dtd.illy.bz/wiki/Server%20fixes)
- nginx (1.3+ to allow websocket proxying, http://wiki.nginx.org/Install)
- mongodb (http://docs.mongodb.org/manual/installation/)
- tornado (pip install)
- motor (pip install)
- pymongo (pip install)
- telnetlib
- simplejson
- jsonschema

#### Setup:
(at the moment the paths are hardcoded in various places, change them if you need to)
- sdtd base (should be like this if your 7d2d game is setup as instructed): /home/sdtd/
- web server path: /var/www/sdtd/
- web server static path: /var/www/sdtd/static/
    leafjs requires access to map dir in your sdtd instance
    to set it up either do it in nginx config or do something like this:
        ln -s /home/sdtd/instances/{your sdtd instance name}/{map type, eg. Random\ Gen}/map /var/www/sdtd/static/map
- upstart-configs: /etc/init/
- nginx-sites-enabled: /etc/nginx/sites-enabled
    scripts should be added in sites-available and ln -s to sites-enabled



