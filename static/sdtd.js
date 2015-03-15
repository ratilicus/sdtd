/*
Code used for displaying dynamic entity markers and static player made markers.
- Note: code in progress

- currenty for dynamic markers a background server script using telnet probes 
  for current entity positions and updates the entities.js file which we poll 
  periodically.
  
- static/player made markers are listed/created/deleted via tornado based 
  server using mongodb for storage.

- chat is websocket based

- Author: Adam Dybczak (RaTilicus)
*/

function init_map() {
    window.leafletMap = L.map('map', {
        crs: L.CRS.Simple
    }).setView([0.0, 0.0], 0);

    L.tileLayer('/static/map/{z}/{x}/{y}.png', {
        maxZoom: 4,
        tms: true,
        continuousWorld: true,
        noWrap: true
    }).addTo(window.leafletMap);
    
    window.leafletMap.on('click', function(e) {
        create_marker(e);
    });
}

function login_submit(e) {
    e.preventDefault();
    console.log(e);
    return false;
}

/* ======================= entity markers js =============================== */
function add_entity_marker(x, y, z, name, opts) {
    // add a entity marker (circle)
    var marker = L.circleMarker(
        [z/8.0, x/8.0], 
        opts || {}
    ).addTo(window.leafletMap);
    marker.bindPopup(name);
    return marker;
}

var entity_markers={};
function get_entities() {
    /*
    Get entity markers
    a background script keeps writing to the entities.js files periodically 
    to update positions of various entities including players, zombies, 
    animals, and current time. The background script is connected to the 
    server telnet and runs gt and le commands.
    */
    $.get("/static/entities.js?ts="+ new Date().getTime(), function(in_data) {
        var data = in_data.entities;
        var day_info = in_data.day_info;
        var refresh_rate_sec = in_data.refresh_rate || 60;

        // remove existing map entity markers that are no longer in the game
        for(id in entity_markers) {
            var el = entity_markers[id];
            if (! data[id]) {
                // delete marker
                window.leafletMap.removeLayer(entity_markers[id])
                delete entity_markers[id]
            }
        };

        // add/update entity markers
        for(id in data) {
            var e = data[id];
            if (entity_markers[id]) {
                // update
                if (e.dead) { 
                    color = '#666666';
                    entity_markers[e.id].setStyle({color:color})
                }
                entity_markers[e.id].setLatLng([e.z/8.0, e.x/8.0])
            } else {
                // create
                color = '#ffffff';
                switch (e.type) {
                    case 'EntityPlayer':
                        color = '#00ff00';
                        break;
                    case 'EntityZombie':
                    case 'EntityZombieCrawl':
                    case 'EntityHornet':
                        color = '#dd8800';
                        break;
                    case 'EntityZombieCop':
                    case 'EntityZombieDog':
                        color = '#ff0000';
                        break;
                    case 'EntityAnimalStag':
                    case 'EntityAnimalRabbit':
                        color = '#ffffff';
                        break;
                
                }
                if (e.dead) {
                    color = '#666666';
                }
                entity_markers[e.id] = add_entity_marker(
                    e.x, 
                    e.y, 
                    e.z, 
                    e.name + " [" + e.type + "]", 
                    {color: color}
                )
            }
        };
        $('#day_info').html(day_info);
        // refresh rate is provided from the server.
        // When players are in the server updates are every 2 sec, else 30 sec
        window.setTimeout('get_entities()', 1000 * refresh_rate_sec)
    }, "json").fail(function(a,b,c) {console.log('error', a,b,c)});
}

/* ============================== markers js =============================== */
function add_marker(x, y, z, name, opts) {
    // create a static marker (square)
    var lat = z/8.0, lng = x/8.0;
    var marker = L.polygon([
        [lat-2.0, lng-2.0],
        [lat+2.0, lng-2.0],
        [lat+2.0, lng+2.0],
        [lat-2.0, lng+2.0]
    ], opts || {}).addTo(window.leafletMap);
    marker.bindPopup(name);
    return marker;
}

var markers={};
function get_markers() {
    /*
    Tornado server code using mongodb are used for managing markers
    */
    $.get("/markers/?ts="+ new Date().getTime(), function(in_data) {
        var data = in_data.data;

        // remove existing static markers from map
        for(id in markers) {
            window.leafletMap.removeLayer(markers[id])
            delete markers[id]
        };

        // add new markers
        for(id in data) {
            var e = data[id];
            // create
            color = e.private ? '#00ff00' : '#ffff00';
            var NSEW = Math.abs(e.z*8)+ (e.z>=0 ? " N ": " S ") +
               Math.abs(e.x*8)+ (e.x>=0 ? " E": " W");

            var desc = "["+NSEW+"] ("+ 
                        (e.public ? 'public' : 'private' ) +") <br>" + 
                        e.desc + "<br><br>" +
                        "- " + (e.player || 'Anonymous') + 
                        ((e.o || !e.player) ? 
                        "<br><button onclick=\"remove_marker('"+
                        e.id+"')\">Remove</button>" : "");
            
            markers[e.id] = add_marker(e.x, e.y, e.z, desc, {color: color})
        };
    }, "json").fail(function(a,b,c) {console.log('error', a,b,c)});
}

function create_marker(e) {
    /*
    add a player made marker
    */
    var lat = e.latlng.lat*8;
    var lng = e.latlng.lng*8;
    var NSEW = Math.abs(lat)+ (lat>=0 ? " N ": " S ") +
               Math.abs(lng)+ (lng>=0 ? " E": " W");
    var desc = prompt("Creating a marker at ["+NSEW+"]\n" +
                      "Enter marker description:\n" +
                      "(put: '*' as the first character to make private)")
    if (!desc) {
        return;
    }

    var public_marker = true;
    if (desc[0] == '*') {
        // if the first character is a *, make private
        // this is a stop gap until I implement a proper create marker ui
        public_marker = false;
        desc=desc.slice(1);
    }

    $.ajax({
        url: "/markers/?ts="+ new Date().getTime(),
        data: JSON.stringify({
            z: lat,
            x: lng,
            y: 0,
            desc: desc,
            public: public_marker
        }),
        method: "POST",
        success: function(in_data) {
            get_markers();
        }, 
        error: function(a,b,c) {
            console.log('error', a,b,c)
        },
        dataType: "json"
    });

}

function remove_marker(marker_id) {
    /* 
    remove a player created marker
    */
    $.ajax({
        url: "/markers/" + marker_id + "/?ts="+ new Date().getTime(),
        method: "DELETE",
        success: function(in_data) {
            get_markers();
        }, 
        error: function(a,b,c) {
            console.log('error', a,b,c)
        },
        dataType: "json"
    });
}

/* =============================== chat js ================================= */
function init_chat() {
    window.ws = new WebSocket("ws://7d2d.ratilicus.com/chat/");
    window.ws.onopen = function() {
       //window.ws.send('.');
    };
    window.ws.onmessage = function (evt) {
       //alert(evt.data);
       $('#ob').append(evt.data+'<br>')
    };
}

function chat_send() {
    if (window.ws) {
        ws.send($('#ib').val());
        $('#ib').val('');
    }
}

