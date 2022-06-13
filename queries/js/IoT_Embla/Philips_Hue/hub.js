"use strict";

async function findHub() {
    // let hubObj = new Object()
    // hubObj.id = "ecb5fafffe1be1a4"
    // hubObj.internalipaddress = "192.168.1.68"
    // hubObj.port = "443"
    // console.log(hubObj)
    // return hubObj
    return fetch(`https://discovery.meethue.com`)
        .then((resp) => resp.json())
        .then((obj) => {
            console.log(obj);
            return(obj[0]);
        })
        .catch((err) => {
            console.log("No smart device found!");
        });
};

async function createNewDeveloper(ipAddress) {
    console.log("create new developer");
    const body = JSON.stringify({
        'devicetype': 'mideind_hue_communication#smartdevice'
    });
    return fetch(`http://${ipAddress}/api`, {
        method: "POST",
        body: body,
    })
        .then((resp) => resp.json())
        .then((obj) => {
            return(obj[0]);
        })
        .catch((err) => {
            console.log(err);
        });
};


async function storeDevice(data, requestURL) {
    console.log("store device");
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
};

// clientID = "82AD3C91-7DA2-4502-BB17-075CEC090B14", requestURL = "192.168.1.68")
async function connectHub(clientID, requestURL) {
    console.log("connect hub");
    let deviceInfo = await findHub();
    console.log("device info: ", deviceInfo);
    console.log("device_ip :", deviceInfo.internalipaddress)

    try {
        let username = await createNewDeveloper(deviceInfo.internalipaddress);
        console.log("username: ",username);
        if (!username.success) {
            return 'Ýttu á \'Philips\' takkann á tengiboxinu og reyndu aftur';
        }

        const data = {
            'client_id': clientID,
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

        const result = await storeDevice(data, requestURL);
        console.log("result: ", result);
        return 'Tenging við snjalltæki tókst';
    } catch(error) {
        console.log(error);
        return 'Ekki tókst að tengja snjalltæki';
    }
};

function syncConnectHub() {
    let clientID = 'AB8C8D7E-20F5-4772-BD69-313EA9DAFBD8'
    let requestURl = '192.168.1.69:5000'
    connectHub(clientID, requestURl);
    return "blabla";
};
