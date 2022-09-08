function togglePlayPause() {
    let myHeaders = new Headers();
    myHeaders.append("Content-Type", "application/json");
    myHeaders.append("Authorization", `Bearer ${sonosBearerToken}`);
    myHeaders.append("Allow-Control-Allow-Origin", "https://api.ws.sonos.com");

    let requestOptions = {
        method: "POST",
        headers: myHeaders,
        redirect: "follow",
    };

    fetch(
        `https://api.ws.sonos.com/control/api/v1/groups/${sonosGroupID}/playback/togglePlayPause`,
        requestOptions
    )
        .then((response) => response.text())
        .then((result) => console.log(result))
        .catch((error) => console.log("error", error));
}

function setVolume() {
    let volume = document.getElementById("volume_slider").value;
    let myHeaders = new Headers();
    myHeaders.append("Content-Type", "application/json");
    myHeaders.append("Authorization", `Bearer ${sonosBearerToken}`);

    let raw = JSON.stringify({
        volume: volume,
    });

    let requestOptions = {
        method: "POST",
        headers: myHeaders,
        body: raw,
        redirect: "follow",
    };

    fetch(
        `https://api.ws.sonos.com/control/api/v1/groups/${sonosGroupID}/groupVolume`,
        requestOptions
    )
        .then((response) => response.text())
        .then((result) => console.log(result))
        .catch((error) => console.log("error", error));
}

// togglePlayPause();
