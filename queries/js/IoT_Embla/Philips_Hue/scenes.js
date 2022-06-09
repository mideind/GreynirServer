function getAllScenes(hub_ip = "192.168.1.68", username = "q2jNarhGHO9izO0xZZXcoww5GYANGi6mZyJYgMdL") {
    return fetch(`http://${hub_ip}/api/${username}/scenes`)
        .then((resp) => resp.json());
}