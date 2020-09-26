"use strict";

const XMLHttpRequest = require("xmlhttprequest").XMLHttpRequest;

function lightInfo(ipAddress, username) {

    var request = new XMLHttpRequest();
    request.open('GET', `http://${ipAddress}/api/${username}/lights`, false);  // `false` makes the request synchronous
    request.send(null);

    if (request.status === 200) {
        return JSON.parse(request.responseText);
    }
    else {
        throw new Error('Error while fetching light info');
    }

}

function groupInfo(ipAddress, username) {
    let request = new XMLHttpRequest();
    request.open('GET', `http://${ipAddress}/api/${username}/groups`, false);
    request.send(null);

    if (request.status === 200) {
        return JSON.parse(request.responseText);
    } else {
        throw new Error ('Error while fetching group info');
    }

}
/*
serviceStorage = {
    username: 'oL27u8MQOYqD486TKcg7ki8OosDx982M5l2oqToP',
    ipAddress: '192.168.1.140'
}
*/
function main() {
    if (!serviceStorage) {
        return 'Snjalltæki ekki tengt';
    }
    let { username, ipAddress } = serviceStorage;

    if (!username || !ipAddress) {
        return 'Snjalltæki ekki tengt';
    }

    let lights = null;
    let groups = null;
    let deviceString = 'Ljós:';

    try {
        lights = lightInfo(ipAddress, username);
    } catch(error) {
        return 'Villa kom upp í samskiptum við snjalltæki';
    }

    for (let key in lights) {
        deviceString += ` ${lights[key].name},`;
    }

    try {
        groups = groupInfo(ipAddress, username);
    } catch(error) {
        console.log(error);
        return 'Villa kom upp í samskiptum við snjalltæki';
    }

    deviceString = deviceString.slice(0, -1);

    deviceString += ' Hópar:';

    for (let key in groups) {
        deviceString += ` ${groups[key].name},`;
    }

    deviceString = deviceString.slice(0, -1);

    return deviceString;

}
main();