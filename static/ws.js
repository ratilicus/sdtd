/*
Code used for websocket communications
- Note: code in progress

- communications are sent back and forth using json

- backend is running on python based tornado server with mongodb for storage

- entity markers are updated via websocket json updates.
  
- chat is websocket based

- Author: Adam Dybczak (RaTilicus)
*/
function open_ws(reconnecting) {
    /* initialize websocket connection */
    window.ws = new WebSocket("ws://7d2d.ratilicus.com/ws/");
    window.ws.onopen = function() {
        console.log('ws opened');
        if (! reconnecting) {
            // if it got disconnected, and now reconnecting, the server will resend all the info except chat
            // So, we have to remove those so we don't have duplicates
//            $('#chat-output div.chat-post').remove()
//            $('#chat-output div.chat-info').remove()
            var json = JSON.stringify({
                'tt': 'cmd',
                'msg': '/posts'
            });
            window.ws.send(json);
        } 
    }

    window.ws.onclose = function() {
        /* connection was lost, so reconnect */
        console.log('closed.. reopening');
        open_ws(true);
    }

    window.ws.onmessage = function (evt) {
        /* message was received from server, process it */
        json = JSON.parse(evt.data);
        //console.log(json);
        switch (json.tt) {
            case 'ue':  // update entities
                //console.log(json);
                update_entities(json.ue, json.re, json.full);
                break;
            case 'uu':  // update users list
                var ul = $('#userlist');
                ul.find('option').remove();
                ul.append('<option>'+json.uc+' users</option>');
                for(i in json.ul) {
                    ul.append('<option>'+json.ul[i]+'</option>');                    
                }
                break;
            case 'ut':  // update time
                window.day_info = json.ut
                update_info();
                break;
            case 'msg':     // chat message received (chat message that only exists for currently logged in users)
            case 'post':    // post message received (perminent message)
            case 'info':    // info message received (since user list was introduced there is no more user entered/left the room messages)
                var out = $(json.tt=='post' ? '#posts': '#msgs')
                var close = ((USER.id==json.uid) && (json.tt=='post')) ? '<button type="button" class="close" onclick="remove_message(this, \''+json.id+'\')" aria-label="Close"><span aria-hidden="true">&times;</span></button>': ''
                var dt = json.ts ? moment(json.ts*1000).format('lll') + ' | ' : '';
                out.append('<div mid="'+json.id+'" class="chat-'+ (json.tt || 'info') +'" onclick="msg_click(this)">'+dt+json.msg+close+'</div>');
                out.scrollTop(out.prop("scrollHeight"));
                break;
            case 'lr':      // reload page command (not used yet, potentially necessary to update css/js on client side)
                location.reload();
                break;
            default:
                console.log(json);
        }
    }
}

function msg_click(el) {
    /* mark selected message (not used yet) */
    console.log(el);
    window.selected_message = el.attributes.mid.value || null;
}

function init_ws() {
    window.username = 'User'
    open_ws();
}

function remove_message(el, mid) {
    if (window.ws) {
        var json = JSON.stringify({
            'tt': 'cmd',
            'msg': '/rm',
            'sm': mid
        });
        window.ws.send(json);
        var mel = $(el)
        mel.parent().css('backgroundColor', 'red');
        mel.remove();
    }
}

function send() {
    /* send chat message */
    if (window.ws) {
        var ci = $('#chat-input'),
            msg = ci.val(),
            tt = 'msg';

        if (msg[0] == '*') {
            /* for now * marks posts as opposed to chat messages */
            msg = msg.slice(1);
            tt = 'post'
        } else if (msg[0] == '/') {
            /* '/' indicates command (not used yet), planned to use commands for posts, removing messages, etc */
            tt = 'cmd'
        }

        var json = JSON.stringify({
            'tt': tt,
            'msg': msg,
            'sm': window.selected_message
        });
        window.ws.send(json);
        ci.val('');
    }
}


function teleport(x, z) {
    /* send a teleport player command */

    if (window.ws) {
        var h = prompt("Please set height for teleport (range 3-256, 64=water level, warning: if u tp into an object you will probably die)");
        if (h) {
            var y = 1*h;
            if(y >=3 && y <=256) {
                var json = JSON.stringify({
                    'tt': 'tp',
                    'tp': {
                        x: 1*x,
                        y: y,
                        z: 1*z
                    }     
                });
                window.ws.send(json);
            } else {
                alert('Height ' + h + ' not within 3 and 256')            
            }
        }
    }
}


