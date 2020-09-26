"use strict";

async function getSmartDeviceInfo(ipAddress, username) {

    const headers = {
        'headers':'application/json'
    };

    const response = await fetch(
        `http://${ipAddress}/api/${username}`,
        {
            method: 'GET',
        }
    )
    .catch((error) =>{
        console.log('error');
        console.log(error);
    });
    return response.json();
}

async function changeLight(ipAddress, username, on) {
    const headers = {
        'headers':'application/json'
    };

    const body = {
        on: on,
        bri:40,
        hue: 65280,
        sat: 254,
        effect: 'colorloop'
    };

    const response = await fetch(
        `http://${ipAddress}/api/${username}/lights/1/state`,
        {
            method: 'PUT',
            body: JSON.stringify(body)
        }
    )
    .catch((error) =>{
        console.log('error');
        console.log(error);
    });
    return response.json();
}

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

function connectHub() {
    serviceStorage = {};
    let deviceInfo = getSmartDeviceAddress();

    try {
        let username = createNewDeveloper(deviceInfo.internalipaddress);
        
        if (username.success){
            serviceStorage.username = username.success.username;
        } else {
            return 'Ýttu á \'Philips\' takkann á tengiboxinu og reyndu aftur';
        }
        
        return 'Tenging við snjalltæki tókst';
    } catch(error) {
        return 'Ekki tókst að tengja snjalltæki';
    }
    // Errors for connectHub
    // {"error":{"address":"","description":"link button not pressed","type":101}}
    // {"error":"Failed to execute 'send' on 'XMLHttpRequest': Failed to load 'http://192.168.1.140/api'."}
    // {"success":{"username":"2GTB-NVq68YwLRA43AZLPHmMiuvRL8yaZJykuJBg"}}
}

connectHub();
