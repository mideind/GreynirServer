const XMLHttpRequest = require("xmlhttprequest").XMLHttpRequest;

function getGroupId(ipAddress, username, groupName) {
    var request = new XMLHttpRequest();

    request.open('GET', `http://${ipAddress}/api/${username}/groups`, false);
    request.send(null);

    if (request.status === 200) {
        let groups = JSON.parse(request.responseText);

        let id = Object.keys(groups).find(key => groups[key].name.toLowerCase() === groupName.toLowerCase());
        if (id) {
            return id;
        } 
        throw new Error('Hópur fannst ekki');

    }

}

function turnOnGroup(ipAddress, username, groupId, on) {

    const body = JSON.stringify({
        on: on,
    });

    var request = new XMLHttpRequest();
    request.open('PUT', `http://${ipAddress}/api/${username}/groups/${groupId}/action`, false);  // `false` makes the request synchronous
    request.send(body);

    if (request.status === 200) {
        let result = JSON.parse(request.responseText);
        console.log(result)
    }
    throw new Error('Hópur fannst ekki');

}

serviceStorage = {
    username: 'oL27u8MQOYqD486TKcg7ki8OosDx982M5l2oqToP',
    ipAddress: '192.168.1.140'
}

function main(on) {
    if (!serviceStorage) {
        return 'Snjalltæki er ekki tengt'
    }

    let { ipAddress, username } = serviceStorage;

    if ( !ipAddress || !username) {
        return 'Snjalltæki er ekki tengt';
    }
    else {
        try {
            let groupId = getGroupId(ipAddress, username, 'skrifstofa');
            return turnOnGroup(ipAddress, username, groupId, on);
        } catch(error) {
            return error.message;
        }
    }
}

main(true);
