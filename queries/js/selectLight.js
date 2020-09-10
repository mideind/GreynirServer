"use strict";

function changeLight(ipAddress, username, lightNo) {

    const body = JSON.stringify({
        alert: 'lselect'
    });

    var request = new XMLHttpRequest();
    request.open('PUT', `http://${ipAddress}/api/${username}/lights/${lightNo}/state`, false);  // `false` makes the request synchronous
    request.send(body);

}
// lightNo: int
// If authorized then light with id lightNo will blink
function main(lightNo) {
    if (!window.serviceStorage) {
        return 'Snjalltæki er ekki tengt';
    }

    let { ipAddress, username } = serviceStorage;

    if ( !ipAddress || !username) {
        return 'Snjalltæki er ekki tengt';
    }
    else {
        try {
            changeLight(ipAddress, username, lightNo);
            return 'Skal gert';
        } catch(error) {
            return error.message;
        }
    }
}
