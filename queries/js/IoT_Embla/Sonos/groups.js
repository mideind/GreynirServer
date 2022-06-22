function getGroups() {
    let myHeaders = new Headers();
    myHeaders.append("Authorization", `Bearer ${bearerToken}`);

    let requestOptions = {
        method: "GET",
        headers: myHeaders,
        redirect: "follow",
    };

    fetch(
        `https://api.ws.sonos.com/control/api/v1/households/${sonosHouseholdID}/groups`,
        requestOptions
    )
        .then((response) => response.text())
        .then((result) => console.log(result))
        .catch((error) => console.log("error", error));
}
