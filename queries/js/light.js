"use strict";

function changeLight(ipAddress, username, on = null, dimmer) {

    let body = {};

    if (on) {
        body.on = on;
    }

    if (dimmer) {
        body.dimmer = parseInt(parseInt(dimmer) * 1/254);
    }
    /*
    const body = JSON.stringify({
        on: on,
        bri:254,
        hue: 65280,
        sat: 254,

    });
    */

    var request = new XMLHttpRequest();
    request.open('PUT', `http://${ipAddress}/api/${username}/lights/1/state`, on);  // `false` makes the request synchronous
    request.send(JSON.stringify(body));

}

function main(on = null, dimmer = null) {
    if (!window.serviceStorage) {
        return 'Snjalltæki er ekki tengt';
    }

    let { ipAddress, username } = serviceStorage;

    if (!ipAddress || !username) {
        return 'Snjalltæki er ekki tengt';
    }
    else {
        try {
            changeLight(ipAddress, username, on, dimmer);
            return 'Skal gert';
        } catch(error) {
            return error.message;
        }
    }
}
