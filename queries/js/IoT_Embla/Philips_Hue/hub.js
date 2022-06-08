
"use strict";

//const XMLHttpRequest = require("xmlhttprequest").XMLHttpRequest;

// function getSmartDeviceAddress() {
//     var request = new XMLHttpRequest();
//     request.open('GET', 'https://discovery.meethue.com', false);  // `false` makes the request synchronous
//     request.send(null);

//     if (request.status === 200) {
//         return JSON.parse(request.responseText)[0];
//     }
//     else {
//         return 'No smart device found';
//     }
// }

// function createNewDeveloper(ipAddress) {
    
//     const body = JSON.stringify({
//         'devicetype': 'mideind_hue_communication#smartdevice'
//     });

//     var request = new XMLHttpRequest();
//     request.open('POST', `http://${ipAddress}/api`, false);  // `false` makes the request synchronous
//     request.send(body);
    

//     if (request.status === 200) {
//         return JSON.parse(request.responseText)[0];
//     }
//     else {
//         throw new Error('Error while creating new user');
//     }
// }

async function findHub() {
    console.log("find hub")
    return fetch(`https://discovery.meethue.com`)
        .then((resp) => resp.json())
        .then((obj) => {
            return(obj);
        })
        .catch((err) => {
            console.log("No smart device found!");
        });
    let hubObj = new Object()
    hubObj.id = "ecb5fafffe1be1a4"
    hubObj.internalipaddress = "192.168.1.68"
    hubObj.port = "443"
    console.log(hubObj)
    return hubObj
}

async function createNewDeveloper(ipAddress) {
    console.log("create new developer")
    const body = JSON.stringify({
        'devicetype': 'mideind_hue_communication#smartdevice'
    });
    return fetch(`http://${ipAddress}/api`, {
        method: "POST",
        body: body,
    })
        .then((resp) => resp.json())
        .then((obj) => {
            return(obj);
        })
        .catch((err) => {
            console.log("Error while creating new user");
        });
}

// function storeDevice(data, requestURL) {

//     let request = new XMLHttpRequest();
    
//     request.open('POST', `http://${requestURL}/register_query_data.api`, false);
//     request.setRequestHeader('Content-Type', 'application/json');

//     request.send(JSON.stringify(data));

//     if (request.status === 200) {
//         return JSON.parse(request.responseText);
//     }
//     else {
//         throw new Error('Error while storing user');
//     }

// }


async function storeDevice(data, requestURL) {
    console.log("store device")
    console.log("data :", data)
    return fetch(`http://${requestURL}/register_query_data.api`, {
        method: "POST",
        body: JSON.stringify(data),
        headers: {
            'Content-Type': 'application/json'
          },
    })
        .then((resp) => resp.json())
        .then((obj) => {
            return(obj);
        })
        .catch((err) => {
            console.log("Error while storing user");
        });
}

async function connectHub(clientID="82AD3C91-7DA2-4502-BB17-075CEC090B14", requestURL="192.168.1.69:5000") {
    console.log("connect hub")
    let deviceInfo = await findHub();
    console.log("device info: ", deviceInfo)

    try {
        let username2 = await createNewDeveloper(deviceInfo.internalipaddress);
        // let username2 = new Object();
        // username2.success = new Object();
        // username2.success.username2 = "3ERlJxkO23rvt2WK3Sks5nFMvKC1dpQzRbQu4QdV"
        console.log("username: ",username2)
        if (!username2.success) {
            return 'Ýttu á \'Philips\' takkann á tengiboxinu og reyndu aftur';
        }

        const data = {
            'client_id': clientID,
            'key': 'smartlights',
            'data': {
                'smartlights': {
                    'selected_light': 'philips_hue',
                    'philips_hue': {
                        'username':username2.success.username2,
                        'ipAddress':deviceInfo.internalipaddress
                    }
                }
            }
        };

        const result = await storeDevice(data, requestURL);
        console.log("result: ", result)
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

