"use strict";

async function getAllLights(hub_ip = BRIDGE_IP, username = USERNAME) {
    return fetch(`http://${hub_ip}/api/${username}/lights`).then((resp) => resp.json());
}

async function getAllGroups(hub_ip = BRIDGE_IP, username = USERNAME) {
    return fetch(`http://${hub_ip}/api/${username}/groups`).then((resp) => resp.json());
}

async function getAllScenes(hub_ip = BRIDGE_IP, username = USERNAME) {
    return fetch(`http://${hub_ip}/api/${username}/scenes`).then((resp) => resp.json());
}

function getCurrentState(id) {
    return fetch(`http://${BRIDGE_IP}/api/${USERNAME}/lights/${id}`).then((resp) => resp.json());
}
