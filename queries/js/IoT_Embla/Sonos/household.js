function getHousehold() {
    let myHeaders = new Headers();
    myHeaders.append("Authorization", `Bearer ${sonosBearerToken}`);

    let requestOptions = {
        method: "GET",
        headers: myHeaders,
        redirect: "follow",
    };

    fetch("https://api.ws.sonos.com/control/api/v2/households", requestOptions)
        .then((response) => response.text())
        .then((result) => console.log(result))
        .catch((error) => console.log("error", error));
}
