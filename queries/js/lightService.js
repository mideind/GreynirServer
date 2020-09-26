"use strict";

//const XMLHttpRequest = require("xmlhttprequest").XMLHttpRequest;

// Returns ID of lights and groups with the provided name
function getIdByName(ipAddress, username, name) {

    let ids = {};

    let request = new XMLHttpRequest();

    request.open('GET', `http://${ipAddress}/api/${username}`, false);
    request.send(null);

    if (request.status === 200) {
        let hub = JSON.parse(request.responseText);
        let groupId = Object.keys(hub.groups).find(key => hub.groups[key].name.toLowerCase() === name.toLowerCase());
        if (groupId) {
            ids.groupId = groupId;
        } 

        let lightId = Object.keys(hub.lights).find(key => hub.lights[key].name.toLowerCase() === name.toLowerCase());
        if (lightId) {
            ids.lightId = lightId;
        } 

        return ids;
    }

}

function changeGroup(ipAddress, username, groupId, on = null, bri = null, hue = null, sat = null) {

    let body = {};

    if (on !== null) {
        body.on = on;
    }

    if (bri !== null) {
        body.bri = parseInt(parseInt(bri) * 254/100);
    }

    if (hue !== null) {
        body.hue = parseInt(hue);
        body.sat = 254;
    }

    if (sat !== null) {
        body.sat = parseInt(parseInt(sat) * (254/100));
    }
    //console.log('body');
    //console.log(body);
    let request = new XMLHttpRequest();
    request.open('PUT', `http://${ipAddress}/api/${username}/groups/${groupId}/action`, false);  // `false` makes the request synchronous
    request.send(JSON.stringify(body));

    if (request.status === 200) {
        let result = JSON.parse(request.responseText);
        return 'Tókst';
    }
    throw new Error('Hópur fannst ekki');

}

function changeLight(ipAddress, username, lightId, on = null, bri = null, hue = null, sat = null) {

    let body = {};

    if (on !== null) {
        body.on = on;
    }

    if (bri !== null) {
        body.bri = parseInt(parseInt(bri) * 254/100);
    }

    if (hue !== null) {
        body.hue = parseInt(hue);
        body.sat = 254;
    }

    if (sat !== null) {
        body.sat = parseInt(parseInt(sat) * 254/100);
    }

    let request = new XMLHttpRequest();
    request.open('PUT', `http://${ipAddress}/api/${username}/lights/${lightId}/state`, false);  // `false` makes the request synchronous
    request.send(JSON.stringify(body));

    if (request.status === 200) {
        let result = JSON.parse(request.responseText);
        return 'Tókst';
    }
    throw new Error('Hópur fannst ekki');

}

function main(ipAddress = null, username = null, name = null, on = null, bri = null, hue = null, sat = null) {

    if ( !ipAddress || !username) {
        return 'Snjalltæki er ekki tengt';
    }

    if (name) {
        try {
            let idDict = getIdByName(ipAddress, username, name);
            if (idDict.groupId) {
                return changeGroup(ipAddress, username, idDict.groupId, on, bri, hue, sat);
            }
            if (idDict.lightId) {
                return changeLight(ipAddress, username, idDict.lightId, on, bri, hue, sat);
            }
        } catch(error) {
            return error.message;
        }
    }

    return `Hópur eða ljós ${name} fannst ekki.`;

}
