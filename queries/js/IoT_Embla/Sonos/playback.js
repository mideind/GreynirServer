function togglePlayPause() {
    let myHeaders = new Headers();
    myHeaders.append("Content-Type", "application/json");
    myHeaders.append("Authorization", "Bearer fhFVRX5CX0Zo8pRI7s366IbRRUQ0");
    myHeaders.append("Allow-Control-Allow-Origin", "https://api.ws.sonos.com");

    let requestOptions = {
        method: "POST",
        headers: myHeaders,
        redirect: "follow",
    };

    fetch(
        "https://api.ws.sonos.com/control/api/v1/groups/RINCON_542A1B599FF201400:2388243335/playback/togglePlayPause",
        requestOptions
    )
        .then((response) => response.text())
        .then((result) => console.log(result))
        .catch((error) => console.log("error", error));
}

togglePlayPause();