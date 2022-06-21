const AUTH_TOKEN = "Bearer 85dabaad-10de-4f74-94a7-0dee4685982e";

function turnOnLight() {
    var myHeaders = new Headers();
    myHeaders.append("Authorization", AUTH_TOKEN);
    myHeaders.append("Content-Type", "application/json");

    var raw = JSON.stringify({
        commands: [
            {
                component: "main",
                capability: "switch",
                command: "on",
            },
        ],
    });

    var requestOptions = {
        method: "POST",
        headers: myHeaders,
        body: raw,
        redirect: "follow",
    };

    fetch(
        "https://api.smartthings.com/v1/devices/7d47b44f-057c-4320-9777-3d1eadca106e/commands",
        requestOptions
    )
        .then((response) => response.text())
        .then((result) => console.log(result))
        .catch((error) => console.log("error", error));
}

function turnOffLight() {
    var myHeaders = new Headers();
    myHeaders.append("Authorization", AUTH_TOKEN);
    myHeaders.append("Content-Type", "application/json");

    var raw = JSON.stringify({
        commands: [
            {
                component: "main",
                capability: "switch",
                command: "off",
            },
        ],
    });

    var requestOptions = {
        method: "POST",
        headers: myHeaders,
        body: raw,
        redirect: "follow",
    };

    fetch(
        "https://api.smartthings.com/v1/devices/7d47b44f-057c-4320-9777-3d1eadca106e/commands",
        requestOptions
    )
        .then((response) => response.text())
        .then((result) => console.log(result))
        .catch((error) => console.log("error", error));
}

function raiseBrightness() {
    var myHeaders = new Headers();
    myHeaders.append("Authorization", AUTH_TOKEN);
    myHeaders.append("Content-Type", "application/json");

    var raw = JSON.stringify({
        commands: [
            {
                component: "main",
                capability: "switchLevel",
                command: "setLevel",
                arguments: "rate"[100],
            },
        ],
    });

    var requestOptions = {
        method: "POST",
        headers: myHeaders,
        body: raw,
        redirect: "follow",
    };

    fetch(
        "https://api.smartthings.com/v1/devices/7d47b44f-057c-4320-9777-3d1eadca106e/commands",
        requestOptions
    )
        .then((response) => response.text())
        .then((result) => console.log(result))
        .catch((error) => console.log("error", error));
}

function lowerBrightness() {
    var myHeaders = new Headers();
    myHeaders.append("Authorization", AUTH_TOKEN);
    myHeaders.append("Content-Type", "application/json");

    var raw = JSON.stringify({
        commands: [
            {
                component: "main",
                capability: "switchLevel",
                command: "setLevel",
                arguments: [1],
            },
        ],
    });

    var requestOptions = {
        method: "POST",
        headers: myHeaders,
        body: raw,
        redirect: "follow",
    };

    fetch(
        "https://api.smartthings.com/v1/devices/7d47b44f-057c-4320-9777-3d1eadca106e/commands",
        requestOptions
    )
        .then((response) => response.text())
        .then((result) => console.log(result))
        .catch((error) => console.log("error", error));
}

function smartThingsWrapper(device, capability, command, arguments = null) {
    var myHeaders = new Headers();
    myHeaders.append("Authorization", AUTH_TOKEN);
    myHeaders.append("Content-Type", "application/json");

    var raw = JSON.stringify({
        commands: [
            {
                component: device,
                capability: capability,
                command: command,
                if(arguments) {
                    arguments: [arguments];
                },
            },
        ],
    });

    var requestOptions = {
        method: "POST",
        headers: myHeaders,
        body: raw,
        redirect: "follow",
    };

    fetch(
        `"https://api.smartthings.com/v1/devices/${device}/commands"`,
        requestOptions
    )
        .then((response) => response.text())
        .then((result) => console.log(result))
        .catch((error) => console.log("error", error));
}
