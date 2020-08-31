"use strict";

//const XMLHttpRequest = require("xmlhttprequest").XMLHttpRequest;

function getSmartDeviceAddress() {
    let request = new XMLHttpRequest();
    request.open('GET', 'https://discovery.meethue.com', false);  // `false` makes the request synchronous
    request.send(null);

    if (request.status === 200) {
        return JSON.parse(request.responseText)[0];
    }
    else {
        return 'No smart device found';
    }
}

function createNewDeveloper(ipAddress) {
    
    const body = JSON.stringify({
        'devicetype': 'mideind_hue_communication#smartdevice'
    });

    let request = new XMLHttpRequest();
    request.open('POST', `http://${ipAddress}/api`, false);  // `false` makes the request synchronous
    request.send(body);
    

    if (request.status === 200) {
        return JSON.parse(request.responseText)[0];
    }
    else {
        throw new Error('Error while creating new user');
    }
}

function connectHub() {
    serviceStorage = {};
    let deviceInfo = getSmartDeviceAddress();

    try {
        let username = createNewDeveloper(deviceInfo.internalipaddress);
        console.log('username');
        console.log(username);
        serviceStorage.username = username.success.username;
        return username;
    } catch(error) {
        serviceStorage.username = null;
        return {error:error.message};
    }
    // Errors for connectHub
    // {"error":{"address":"","description":"link button not pressed","type":101}}
    // {"error":"Failed to execute 'send' on 'XMLHttpRequest': Failed to load 'http://192.168.1.140/api'."}
    // {"success":{"username":"2GTB-NVq68YwLRA43AZLPHmMiuvRL8yaZJykuJBg"}}
}

connectHub();
