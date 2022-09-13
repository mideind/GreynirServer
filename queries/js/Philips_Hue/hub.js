"use strict";

async function findHub() {
    return fetch(`https://discovery.meethue.com`)
        .then((resp) => resp.json())
        .then((obj) => {
            return obj[0];
        })
        .catch((err) => {});
}

async function createNewDeveloper(ipAddress) {
    return fetch(`http://${ipAddress}/api`, {
        method: "POST",
        body: JSON.stringify({
            devicetype: "Embla",
        }),
    })
        .then((resp) => resp.json())
        .then((obj) => {
            return obj[0];
        })
        .catch((err) => {});
}

async function storeDevice(data, requestURL) {
    return fetch(`http://${requestURL}/register_query_data.api`, {
        method: "POST",
        body: JSON.stringify(data),
        headers: {
            "Content-Type": "application/json",
        },
    })
        .then((resp) => resp.json())
        .then((obj) => {
            return obj;
        })
        .catch((err) => {});
}

async function connectHub(clientID, requestURL) {
    let deviceInfo = await findHub();

    try {
        let username = await createNewDeveloper(deviceInfo.internalipaddress);
        if (!username.success) {
            return "Ýttu á 'Philips' takkann á miðstöðinni og reyndu aftur";
        }

        const data = {
            client_id: clientID,
            key: "iot",
            data: {
                iot_lights: {
                    philips_hue: {
                        credentials: {
                            username: username.success.username,
                            ip_address: deviceInfo.internalipaddress,
                        },
                    },
                },
            },
        };

        await storeDevice(data, requestURL);
        return "Tenging við Philips Hue miðstöðina tókst!";
    } catch (error) {
        return "Ekki tókst að tengja Philips Hue miðstöðina.";
    }
}
