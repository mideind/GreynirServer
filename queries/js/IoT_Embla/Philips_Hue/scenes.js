function getAllScenes(hub_ip = BRIDGE_IP, username = USERNAME) {
    return fetch(`http://${hub_ip}/api/${username}/scenes`)
        .then((resp) => resp.json());
};