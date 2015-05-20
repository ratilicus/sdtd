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
var degRad = Math.PI/180

function init_map() {
    window.onresize = window_resize
    window_resize();

    window.leafletMap = L.map('map', {
        crs: L.CRS.Simple,
//        maxZoom: 5
    }).setView([0.0, 0.0], 0);

    window.leafletMapTileLayer = L.tileLayer('/static/map/{z}/{x}/{y}.png', {
        maxZoom: 4,
        tms: true,
        continuousWorld: true,
        noWrap: true
    }).addTo(window.leafletMap);
    
    window.leafletMap.on('click', function(e) {
        show_spot_info(e);
    });

    window.leafletMap.on('movestart', function(e) {
        window.clearTimeout(window.follow_timer);
    });
    /*
    window.leafletMapTileLayer.on('tileload', function(e) {
        console.log('tileload', e)
    });*/

    window.spot_info_template = _.template($('script.spot_info_template').html())
    window.entity_info_template = _.template($('script.entity_info_template').html())
    window.players = {};
    window.zombies = {};
    window.entity_markers={};
    window.setTimeout(redraw_map, 10000);
}

function window_resize(e) {
    var height = window.innerHeight - $('nav').height() - $('#entity-info').height() - $('#location-info').height() - $('#chat-input').height() - 8;
    $('#map').css('height', Math.floor(height * 0.75) + 'px');
    $('#chat-output').css('height', Math.floor(height * 0.25) + 'px');
}

function login_submit(e) {
    e.preventDefault();
    console.log(e);
    return false;
}

function redraw_map() {
    var t = new Date().getTime();
    $('#map img').each(function(i, img) {
        src = img.src.split('?')[0]
        img.src = src + '?t=' + t
    });
   
    if (window.redraw_timer)
        window.clearTimeout(window.redraw_timer);
    window.redraw_timer = window.setTimeout(redraw_map, 10000);
}

function player_click(eid) {
    if (eid) {
        window.followPlayer = eid;
    } else {
        eid = window.followPlayer;
    }
    var player = window.players[eid];
    //console.log('click', player);
    if (player) {
        window.leafletMap.panTo([player.z/8.0, player.x/8.0]);
        if (window.leafletMap.getZoom() < 3) {
            window.leafletMap.setZoom(3);
        }
        window.follow_timer = window.setTimeout(player_click, 250);
    }
}

/* ======================= entity markers js =============================== */
function add_entity_marker(x, y, z, h, name, opts) {
    var lat = z/8.0, lng = x/8.0;
    /*
    // add a entity marker (circle)
    var marker = L.circleMarker(
        [lat, lng], 
        opts || {}
    ).addTo(window.leafletMap);
    marker.bindPopup(name);

    var lmarker = L.polyline(
        [[lat, lng], [lat+Math.cos(h*degRad)*0.75, lng+Math.sin(h*degRad)*0.75]],
        opts || {}
    ).addTo(window.leafletMap);

    return [marker, lmarker];*/
    var marker = L.polygon(
        [
            [lat+Math.cos((h-120)*degRad)*0.5, lng+Math.sin((h-120)*degRad)*0.5],
            [lat+Math.cos(h*degRad), lng+Math.sin(h*degRad)],
            [lat+Math.cos((h+120)*degRad)*0.5, lng+Math.sin((h+120)*degRad)*0.5]
        ],
        opts || {}
    ).addTo(window.leafletMap);
    marker.bindPopup(name);
    return marker
}

function update_entity_marker(em, x, y, z, h, color) {
    var lat = z/8.0, lng = x/8.0;
    /*
    var marker = em[0];
    var lmarker = em[1];
    marker.setStyle({color:color})
    marker.setLatLng([lat, lng])
    lmarker.setLatLngs([[lat, lng], [lat+Math.cos(h*degRad)*0.5, lng+Math.sin(h*degRad)*0.5]]);*/
    em.setStyle({fillColor:color})
    em.setLatLngs(
        [
            [lat+Math.cos((h-120)*degRad)*0.75, lng+Math.sin((h-120)*degRad)*0.75],
            [lat+Math.cos(h*degRad)*1.0, lng+Math.sin(h*degRad)*1.0],
            [lat+Math.cos((h+120)*degRad)*0.75, lng+Math.sin((h+120)*degRad)*0.75]
        ]
    );
}


function update_info() {
    $('#entity-info').html(window.entity_info_template({
        day_info: window.day_info || '',
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
        var lat = e.z/8.0, lng = e.x/8.0;
        // update
        update_entity_marker(
            window.entity_markers[e.id],
            e.x, 
            e.y, 
            e.z, 
            e.h, 
            color
        )
    } else {
        // create
        
        var lat = e.z, lng = e.x;
        var NSEW = Math.abs(lat)+ (lat>=0 ? " N ": " S ") +
           Math.abs(lng)+ (lng>=0 ? " E": " W");

        window.entity_markers[e.id] = add_entity_marker(
            e.x, 
            e.y, 
            e.z, 
            e.h, 
            e.name + " [" + e.type + "]", 
            {
                weight: 2,
                opacity: 0.8,
                color: '#000000',
                fillColor: color, 
                fillOpacity: is_player ? 0.75 : 0.5, 
                zIndexOffset: is_player ? 1000 : 100
            }
        )
        update_info();
    }
}

/* ============================== markers js =============================== 
Place Markers based on AJAX calls
TODO: add different kinds of markers (different shapes, sizes, and colors)
*/
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

window.place_markers = {};
function get_markers() {
    /*
    Tornado server code using mongodb are used for managing markers
    */
    $.get("/markers/?ts="+ new Date().getTime(), function(in_data) {
        var data = in_data.data;

        // remove existing static markers from map
        for(id in window.place_markers) {
            window.leafletMap.removeLayer(window.place_markers[id])
            delete window.place_markers[id]
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
            
            window.place_markers[e.id] = add_marker(e.x, e.y, e.z, desc, {color: color})
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
    $('#location-info').html(window.spot_info_template({NSEW: NSEW, lat: lat, lng: lng}));
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

