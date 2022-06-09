var BRIDGE_IP = "192.168.1.68";
var USERNAME = "q2jNarhGHO9izO0xZZXcoww5GYANGi6mZyJYgMdL";

function changeBrightness() {
    var sliderValue = document.getElementById("brightness_slider").value;
    console.log(sliderValue);
    
    fetch(`http://${BRIDGE_IP}/api/${USERNAME}/lights/1/state`, {
        method: "PUT",
        body: JSON.stringify({ bri: Number(sliderValue)})
    })
        .then((resp) => resp.json())
        .then((j) => {
            console.log(j);
        })
        .catch((err) => {
            console.log("an error occurred!");
        });
}

function changeColor() {
    xValue = Number(document.getElementById("color_x").value)
    yValue = Number(document.getElementById("color_y").value)
    console.log(xValue, yValue);

    if(xValue === undefined || yValue === undefined || xValue > 1 || xValue < 0 || yValue > 1 || yValue < 0) {
        document.getElementById("color_error").innerHTML = "Please enter a value between 0 and 1.";
    }
    else {
        document.getElementById("color_error").innerHTML = "";
        colorValue = [Number(xValue), Number(yValue)]
        console.log(colorValue);
        fetch(`http://${BRIDGE_IP}/api/${USERNAME}/lights/1/state`, {
            method: "PUT",
            body: JSON.stringify({ xy: colorValue })
        })
            .then((resp) => resp.json())
            .then((j) => {
                console.log(j);
            })
            .catch((err) => {
                console.log("an error occurred!");
            });
    }

}  


function getAllLights(hub_ip = "192.168.1.68", username = "q2jNarhGHO9izO0xZZXcoww5GYANGi6mZyJYgMdL") {
    return fetch(`http://${hub_ip}/api/${username}/lights`)
        .then((resp) => resp.json())
}

function getAllGroups(hub_ip = "192.168.1.68", username = "q2jNarhGHO9izO0xZZXcoww5GYANGi6mZyJYgMdL") {
    return fetch(`http://${hub_ip}/api/${username}/groups`)
        .then((resp) => resp.json())
}

function getAllScenes(hub_ip = "192.168.1.68", username = "q2jNarhGHO9izO0xZZXcoww5GYANGi6mZyJYgMdL") {
    return fetch(`http://${hub_ip}/api/${username}/scenes`)
        .then((resp) => resp.json())
}

function getCurrentState(id) {
    return fetch(`http://${BRIDGE_IP}/api/${USERNAME}/lights/${id}`)
        .then((resp) => resp.json())
}


async function test(){
    console.log(getAllGroups())
    var lights = await getAllLights();
    var groups = await getAllGroups();
    console.log("lights:", lights)
    console.log("groups:", groups)
}


