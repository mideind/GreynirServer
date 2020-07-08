function changeLight(ipAddress, username, on) {

    const body = JSON.stringify({
        on: on,
        bri:254,
        hue: 65280,
        sat: 254,

    });

    var request = new XMLHttpRequest();
    request.open('PUT', `http://${ipAddress}/api/${username}/lights/1/state`, on);  // `false` makes the request synchronous
    request.send(body);

}

function main(on) {
    if (!window.serviceStorage) {
        return 'Snjalltæki er ekki tengt'
    }

    let { ipAddress, username } = serviceStorage;

    if ( !ipAddress || !username) {
        return 'Snjalltæki er ekki tengt';
    }
    else {
        try {
            changeLight(ipAddress, username, on);
            return 'skal gert';
        } catch(error) {
            return error.message;
        }
    }
}
