# 7d2d
7 Days To Die



This repo has a couple parts:
- users Leaflet.js for showing 7d2d map
- tornado/mongodb based server for creating/removing map markers
- a background script for polling server telnet and getting entities
- sdtd hooks to register new players and setup login/pw

Note: work in progress
some paths are hardcoded at the moment, will need to be changed based on installation.

Installation:
Running on Ubuntu 12.04 server

Require:
- nginx (get newer version for websockets, coming soon)
- tornado (pip install)
- motor (pip install)
- mongodb
- pymongo (pip install)
- telnetlib
- simplejson
- jsonschema

My setup:
- sdtd base: /home/sdtd/
- sdtd hooks: /home/sdtd/hooks/          
- repo path: /var/www/sdtd/
- static path: /var/www/sdtd/static/
    leafjs requires access to map dir in your sdtd instance
    to set it up either do it in nginx config or do something like this:
        ln -s /home/sdtd/instances/{your sdtd instance name}/{map type, eg. Random\ Gen}/map /var/www/sdtd/static/map
- upstart: /etc/init/
- nginx sites-enabled: /etc/nginx/sites-enabled
    scripts should be added in sites-available and ln -s to sites-enabled

TODO:
- add marker editing
- add proper ui for marker create/edit/remove
- websocket chat/entity updates
    - sdtd-log will merge into sdtd-tornado for this
- clean up code
    - document
    - remove hardcoded paths, etc
