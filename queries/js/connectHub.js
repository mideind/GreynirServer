"use strict";

//const XMLHttpRequest = require("xmlhttprequest").XMLHttpRequest;

function getSmartDeviceAddress() {
    var request = new XMLHttpRequest();
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

    var request = new XMLHttpRequest();
    request.open('POST', `http://${ipAddress}/api`, false);  // `false` makes the request synchronous
    request.send(body);
    

    if (request.status === 200) {
        return JSON.parse(request.responseText)[0];
    }
    else {
        throw new Error('Error while creating new user');
    }
}

function storeDevice(data, requestURL) {

    let request = new XMLHttpRequest();
    
    request.open('POST', `http://${requestURL}/register_query_data.api`, false);
    request.setRequestHeader('Content-Type', 'application/json');

    request.send(JSON.stringify(data));

    if (request.status === 200) {
        return JSON.parse(request.responseText);
    }
    else {
        throw new Error('Error while storing user');
    }

}

function connectHub(device_id, requestURL) {

    let deviceInfo = getSmartDeviceAddress();

    try {
        let username = createNewDeveloper(deviceInfo.internalipaddress);
        
        if (!username.success) {
            return 'Ýttu á \'Philips\' takkann á tengiboxinu og reyndu aftur';
        }

        const data = {
            'device_id': device_id,
            'key': 'smartlights',
            'data': {
                'smartlights': {
                    'selected_light': 'philips_hue',
                    'philips_hue': {
                        'username':username.success.username,
                        'ipAddress':deviceInfo.internalipaddress
                    }
                }
            }
        };

        const result = storeDevice(data, requestURL);

        return 'Tenging við snjalltæki tókst';
    } catch(error) {
        console.log(error);
        return 'Ekki tókst að tengja snjalltæki';
    }
    // Errors for connectHub
    // {"error":{"address":"","description":"link button not pressed","type":101}}
    // {"error":"Failed to execute 'send' on 'XMLHttpRequest': Failed to load 'http://192.168.1.140/api'."}
    // {"success":{"username":"2GTB-NVq68YwLRA43AZLPHmMiuvRL8yaZJykuJBg"}}
}

