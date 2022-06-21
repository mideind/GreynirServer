async function storeDevice(data, ipAddress) {
    console.log("store device");
    return fetch(`http://${ipAddress}/register_query_data.api`, {
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
        .catch((err) => {
            console.log("Error while storing user");
        });
}

// bearer token 64780d2b-b763-433d-95ca-3eaaf5e10642
async function connectHub(clientID, ipAddress) {
    console.log("connect hub");
    let bearerToken = "64780d2b-b763-433d-95ca-3eaaf5e10642";

    try {
        const data = {
            client_id: clientID,
            key: "smart_hubs",
            data: {
                hubs: {
                    selected_hub: "smart_things",
                    smart_things: {
                        bearer_token: bearerToken,
                    },
                },
            },
        };

        const result = await storeDevice(data, ipAddress);
        console.log("result: ", result);
        return "Tenging við snjalltæki tókst";
    } catch (error) {
        console.log(error);
        return "Ekki tókst að tengja snjalltæki";
    }
}

function syncConnectHub(cliendID, ipAdress) {
    connectHub(cliendID, ipAdress);
}
