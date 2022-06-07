var BRIDGE_IP = "192.168.1.68";
var USERNAME = "q2jNarhGHO9izO0xZZXcoww5GYANGi6mZyJYgMdL";

function light_show() {
    fetch(`http://${BRIDGE_IP}/api/${USERNAME}/lights/1/state`, {
        method: "PUT",
        body: JSON.stringify({ on: true, bri: 100, xy: [0.55, 0.4] }),
    })
        .then((resp) => resp.json())
        .then((j) => {
            console.log(j);
        })
        .catch((err) => {
            console.log("an error occurred!");
        });
}

// function find_hub() {
//     fetch(`https://discovery.meethue.com`)
//         .then((resp) => resp.json())
//         .then((j) => {
//             console.log(j);
//         })
//         .catch((err) => {
//             console.log("an error occurred!");
//         });
// }

function get_lights() {
    fetch(`http://${BRIDGE_IP}/api/${USERNAME}/lights`,{
        method: "GET"
    })
    .then((resp) => resp.json())
    .then((j) => {
        console.log(j);
        document.write(j)
        return(j)
    })
    .catch((err) => {
        console.log("an error occured!")
    })
}

function turn_off_lights() {
    fetch(`http://${BRIDGE_IP}/api/${USERNAME}/lights/1/state`,{
        method: "PUT",
        body: JSON.stringify({ on: false})
    })
    .then((resp) => resp.json())
    .then((j) => {
        console.log(j);
    })
    .catch((err) => {
        console.log("an error occured!")
    })
}
