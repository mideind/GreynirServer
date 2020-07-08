const XMLHttpRequest = require("xmlhttprequest").XMLHttpRequest;

function lightInfo(ipAddress, username) {

    var request = new XMLHttpRequest();
    request.open('GET', `http://${ipAddress}/api/${username}/lights`, false);  // `false` makes the request synchronous
    request.send(null);

    if (request.status === 200) {
        return JSON.parse(request.responseText);
    }
    else {
        throw new Error('Error while fetchin light info')
    }

}

serviceStorage = {
    username: 'oL27u8MQOYqD486TKcg7ki8OosDx982M5l2oqToP',
    ipAddress: '192.168.1.140'
}

function main() {
    if (!serviceStorage) {
        return 'Snjalltæki ekki tengt'
    }
    let { username, ipAddress } = serviceStorage;

    if (!username || !ipAddress) {
        return 'Snjalltæki ekki tengt'
    }

    let lights = null;
    let deviceString = '';

    try {
        lights = lightInfo(ipAddress, username);
    } catch(error) {
        return 'Villa kom upp í samskiptum við snjalltæki'
    }

    for (let key in lights) {
        deviceString += `${key}. ${lights[key].name} `
    }
    return deviceString

}

console.log(main());