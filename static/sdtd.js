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

    var layer=L.tileLayer('/static/map/{z}/{x}/{y}.png', {
        maxZoom: 4,
        tms: true,
        continuousWorld: true,
        noWrap: true
    }).addTo(window.leafletMap);
    
    window.leafletMap.on('click', function(e) {
        show_spot_info(e);
    });


    console.log('layer', layer);
    layer.on('tileload', function(e) {
        console.log('tileload', e)
    });

    window.spot_info_template = _.template($('script.spot_info_template').html())
    window.entity_info_template = _.template($('script.entity_info_template').html())
    window.players = {};
    window.zombies = {};
    window.entity_markers={};
}

function login_submit(e) {
    e.preventDefault();
    console.log(e);
    return false;
}

function player_click(eid) {
    var player = window.players[eid];
    //console.log('click', player);
    window.leafletMap.panTo([player.z/8.0, player.x/8.0])
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

function update_info() {
    $('#entity-info').html(window.entity_info_template({
        players: players
    }));
}

function remove_entities(entity_ids, exclude_ids) {
    for(i in entity_ids) {
        var id = entity_ids[i];
        if (!exclude_ids || exclude_ids.indexOf(id)==-1) {
            var en = window.entity_markers[id];
            delete window.entity_markers[id];
            delete window.players[id];
            delete window.zombies[id];
            update_info();
            if(en) window.leafletMap.removeLayer(en)
        }
    }
}

function update_entities(entities, remove, full) {
   
    
    for(id in entities) {
        update_entity(entities[id]);
    }
    if (full) {
        remove_entities(Object.keys(window.entity_markers), Object.keys(entities));    
    } else
        remove_entities(remove);
}

function update_entity(e) {
    var id = e.id;

    var is_player = false;

    if (e.dead) {
        color = '#666666';
    } else switch (e.type) {
        case 'EntityPlayer':
            color = '#00ff00';
            is_player = true;
            window.players[e.id] = e;
            break;
        case 'EntityZombie':
        case 'EntityZombieCrawl':
        case 'EntityHornet':
            color = '#dd8800';
            window.zombies[e.id] = e;
            break;
        case 'EntityZombieCop':
        case 'EntityZombieDog':
            color = '#ff0000';
            window.zombies[e.id] = e;
            break;
        case 'EntityAnimalStag':
        case 'EntityAnimalRabbit':
            color = '#ffffff';
            break;
    }

    if (window.entity_markers[id]) {
        // update
        if (e.dead) { 
            window.entity_markers[e.id].setStyle({color:color})
        }
        window.entity_markers[e.id].setLatLng([e.z/8.0, e.x/8.0])
    } else {
        // create
        
        var lat = e.z, lng = e.x;
        var NSEW = Math.abs(lat)+ (lat>=0 ? " N ": " S ") +
           Math.abs(lng)+ (lng>=0 ? " E": " W");

        window.entity_markers[e.id] = add_entity_marker(
            e.x, 
            e.y, 
            e.z, 
            e.name + " [" + e.type + "]", 
            {color: color, zIndexOffset: is_player ? 1000 : 100}
        )
        update_info();
    }
}


/* ============================== markers js =============================== */
function add_marker(x, y, z, name, opts) {
    // create a static marker (square)
    var lat = z/8.0, lng = x/8.0;
    var marker = L.polygon([
        [lat-1.0, lng-1.0],
        [lat+1.0, lng-1.0],
        [lat+1.0, lng+1.0],
        [lat-1.0, lng+1.0]
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
                        "- " + (e.username || 'Anonymous') + 
                        ((e.o || !e.username) ? 
                        "<br><button onclick=\"remove_marker('"+
                        e.id+"')\">Remove</button>" : "");
            
            markers[e.id] = add_marker(e.x, e.y, e.z, desc, {color: color})
        };
    }, "json").fail(function(a,b,c) {console.log('error', a,b,c)});
}

function show_spot_info(e) {
    /*
    add a player made marker
    */
    var lat = Math.floor(e.latlng.lat*8);
    var lng = Math.floor(e.latlng.lng*8);
    var NSEW = Math.abs(lat)+ (lat>=0 ? " N ": " S ") +
               Math.abs(lng)+ (lng>=0 ? " E ": " W ");
    $('#spot-info').html(window.spot_info_template({NSEW: NSEW, lat: lat, lng: lng}));
}

function create_marker(lat, lng) {
    /*
    add a player made marker
    */
    console.log('create_marker', lat, lng);
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

