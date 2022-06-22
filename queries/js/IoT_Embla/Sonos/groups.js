function getGroups() {
    let myHeaders = new Headers();
    myHeaders.append("Authorization", "Bearer fhFVRX5CX0Zo8pRI7s366IbRRUQ0");

    let requestOptions = {
        method: "GET",
        headers: myHeaders,
        redirect: "follow",
    };

    fetch(
        "https://api.ws.sonos.com/control/api/v1/households/Sonos_2qmmZYj1IfZpziI3yTZT2AdYkP.LzZPKytb_zgm6t3fVIv7/groups",
        requestOptions
    )
        .then((response) => response.text())
        .then((result) => console.log(result))
        .catch((error) => console.log("error", error));
}
