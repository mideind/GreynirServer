//const XMLHttpRequest = require("xmlhttprequest").XMLHttpRequest;

// returns ID of lights and groups with the provided name
function getIdByName(ipAddress, username, name) {

    let ids = {}

    let request = new XMLHttpRequest();

    request.open('GET', `http://${ipAddress}/api/${username}`, false);
    request.send(null);

    if (request.status === 200) {
        let hub = JSON.parse(request.responseText);
        let groupId = Object.keys(hub.groups).find(key => hub.groups[key].name.toLowerCase() === name.toLowerCase());
        if (groupId) {
            ids.groupId = groupId
        } 

        let lightId = Object.keys(hub.lights).find(key => hub.lights[key].name.toLowerCase() === name.toLowerCase());
        if (lightId) {
            ids.lightId = lightId
        } 

        return ids;

    }

}

function changeGroup(ipAddress, username, groupId, on = null, bri = null, hue = null) {

    let body = {};

    if(on !== null) {
        body.on = on
    }

    if (bri !== null) {
        body.bri = parseInt(parseInt(bri) * 254/100);
    }

    if (hue) {
        body.hue = parseInt(hue);
        body.sat = 254;
    }

    let request = new XMLHttpRequest();
    request.open('PUT', `http://${ipAddress}/api/${username}/groups/${groupId}/action`, false);  // `false` makes the request synchronous
    request.send(JSON.stringify(body));
    console.log(body);
    if (request.status === 200) {
        let result = JSON.parse(request.responseText);
        console.log(result);
        return 'Tókst';
    }
    throw new Error('Hópur fannst ekki');

}

function changeLight(ipAddress, username, lightId, on = null, bri = null, hue = null) {

    let body = {};

    if(on !== null) {
        body.on = on
    }

    if (bri !== null) {
        body.bri = parseInt(parseInt(bri) * 254/100)
    }

    if (hue) {
        body.hue = parseInt(hue);
        body.sat = 254;
    }

    /*
    const body = JSON.stringify({
        on: on,
        bri:254,
        hue: 65280,
        sat: 254,

    });
    */

    let request = new XMLHttpRequest();
    request.open('PUT', `http://${ipAddress}/api/${username}/lights/${lightId}/state`, false);  // `false` makes the request synchronous
    request.send(JSON.stringify(body));

}
/*
serviceStorage = {
    username: 'oL27u8MQOYqD486TKcg7ki8OosDx982M5l2oqToP',
    ipAddress: '192.168.1.140'
}
*/
function main(name = null, on = null, bri = null, hue = null) {
    if (!serviceStorage) {
        return 'Snjalltæki er ekki tengt'
    }

    let { ipAddress, username } = serviceStorage;

    if ( !ipAddress || !username) {
        return 'Snjalltæki er ekki tengt';
    }

    if (name) {
        try {
            let idDict = getIdByName(ipAddress, username, name);
            if (idDict.groupId) {
                return changeGroup(ipAddress, username, idDict.groupId, on, bri, hue);
            }
            if (idDict.lightId) {
                return changeLight(ipAddress, username, idDict.lightId, on, bri, hue);
            }
        } catch(error) {
            console.log(error)
            return error.message;
        }
    }

    return `Hópur eða ljós ${name} fannst ekki.`

}
