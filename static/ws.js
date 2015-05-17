function init_ws() {
    window.username = 'User'
    window.ws = new WebSocket("ws://7d2d.ratilicus.com/ws/");
    window.ws.onopen = function() {
        console.log('opened')
    };
    window.ws.onmessage = function (evt) {
        json = JSON.parse(evt.data);
        //console.log(json);
        switch (json.tt) {
            case 'ue':
                //console.log(json);
                update_entities(json.ue, json.re, json.full);
                break;
            case 'ut':
                $('#day_info').html(json.ut);
                break;
            case 'msg':
                var out = $('#chat-output')
                out.append($('<div class="btn-info">'+json.msg+'</div>'));
                out.scrollTop(out.prop("scrollHeight"));
                break;
            default:
                console.log(json);
        }
        
    };
}

function send() {
    if (window.ws) {
        var ci = $('#chat-input');
        var json = JSON.stringify({
            'tt': 'msg',
            'msg': ci.val()        
        });
        window.ws.send(json);
        ci.val('');
    }
}


function teleport(x, z) {
    /*
    add a player made marker
    */

    if (window.ws) {
        var h = prompt("Please set height for teleport (range 3-128, 64=water level, warning: if u tp into an object you will probably die)");
        if (h) {
            var y = 1*h;
            if(y >=3 && y <=128) {
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
                alert('Height ' + h + ' not within 3 -128')            
            }
        }
    }
}


