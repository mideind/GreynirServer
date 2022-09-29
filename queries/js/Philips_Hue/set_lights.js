/** Fuzzy search function that returns an object in the form of {result: (Object), score: (Number)}
 * @param {string} query - the search term
 * @param {Object} data - the data to search
 * @param {string[]} searchKeys - the key/s for searching the data
 * @return {Object[]} List of results from search
 */
function fuzzySearch(query, data, searchKeys) {
    if (searchKeys === undefined) {
        searchKeys = ["info.name"];
    }
    // Set default argument for searchKeys

    // Fuzzy search for the query term (returns an array of objects)
    let fuse = new Fuse(data, {
        includeScore: true,
        keys: searchKeys,
        shouldSort: true,
        threshold: 0.5,
    });

    // Array of results
    let searchResult = fuse.search(query);
    return searchResult.map((obj) => {
        // Copy score inside item
        obj.item.score = obj.score;
        // Return item itself
        return obj.item;
    });
}

/** Send a PUT request to the given URL endpoint of the Philips Hue hub.
 * @param {string} hub_ip - the IP address of the Philips Hue hub on the local network
 * @param {string} username - the username we have registered with the hub
 * @param {string} url_endpoint - the relevant URL endpoint of the Hue API
 * @param {string} state - JSON encoded body
 * @returns {Promise} Promise which resolves to the hub's response
 */
async function call_api_v1(hub_ip, username, url_endpoint, state) {
    return fetch(`http://${hub_ip}/api/${username}/${url_endpoint}`, {
        method: "PUT",
        body: state,
    })
        .then((resp) => resp.json())
        .catch((err) => [{ error: "Invalid response from hub." }]);
}

/**
 * Fetch all connected lights for this hub.
 * @param {string} hub_ip - the IP address of the Philips Hue hub on the local network
 * @param {string} username - the username we have registered with the hub
 * @returns {Promise<Object[]>} Promise which resolves to list of all connected lights
 */
async function getAllLights(hub_ip, username) {
    return fetch(`http://${hub_ip}/api/${username}/lights`)
        .then((resp) => resp.json())
        .then(
            // Restructure data to be easier to work with
            (data) => Object.keys(data).map((key) => ({ ID: key, info: data[key] }))
        );
}

/**
 * Fetch all light groups for this hub.
 * @param {string} hub_ip - the IP address of the Philips Hue hub on the local network
 * @param {string} username - the username we have registered with the hub
 * @returns {Promise<Object[]>} Promise which resolves to list of all light groups
 */
async function getAllGroups(hub_ip, username) {
    return fetch(`http://${hub_ip}/api/${username}/groups`)
        .then((resp) => resp.json())
        .then(
            // Restructure data to be easier to work with
            (data) => Object.keys(data).map((key) => ({ ID: key, info: data[key] }))
        );
}

/**
 * Fetch all scenes for this hub.
 * @param {string} hub_ip - the IP address of the Philips Hue hub on the local network
 * @param {string} username - the username we have registered with the hub
 * @returns {Promise<Object[]>} Promise which resolves to list of registered scenes
 */
async function getAllScenes(hub_ip, username) {
    return fetch(`http://${hub_ip}/api/${username}/scenes`)
        .then((resp) => resp.json())
        .then(
            // Restructure data to be easier to work with
            (data) => Object.keys(data).map((key) => ({ ID: key, info: data[key] }))
        );
}

/**
 * Check whether any of the targeted lights are Ikea TRADFRI lights.
 * Done in order to deal with a bug where the lights only accept
 * one parameter at a time.
 * @param {Object[]} matchedLights - array containing all lights in target/query
 * @returns {boolean} True if any of the query lights are Ikea TRADFRI lights, false otherwise
 */
function containsIKEABulb(matchedLights) {
    // Why does for..in give indexes instead of objects? :/
    for (const i in matchedLights) {
        const light = matchedLights[i];
        if (
            light.info.manufacturername.includes("IKEA") ||
            light.info.modelid.includes("TRADFRI") ||
            light.info.manufacturername.includes("ikea") ||
            light.info.manufacturername.includes("tradfri")
        ) {
            return true;
        }
    }
    return false;
}

/**
 * For a given light-group query pair,
 * find the most appropriate API endpoint.
 * @param {string} light - query for a light
 * @param {string} group - query for a group
 * @param {Object[]} allLights - list of all lights
 * @param {Object[]} allGroups - list of all groups
 * @returns {Object} object containing API endpoint and affected lights/groups
 */
function findLights(light, group, allLights, allGroups) {
    let matchedLights = [];
    let matchedGroups = [];

    // Find matching lights
    if (light !== "*") {
        matchedLights = fuzzySearch(light, allLights);
        console.log("matchedLights:", matchedLights.toString());
    }
    // Find matching groups
    if (group !== "*" && group !== "") {
        matchedGroups = fuzzySearch(group, allGroups);
        console.log("matchedGroups:", matchedGroups.toString());
    }

    // API URL endpoint (different for groups vs lights)
    let api_endpoint = null;
    if (light === "*" && group === "*") {
        api_endpoint = `groups/0/action`; // Special all-lights group
    } else {
        if (matchedGroups.length === 0 && matchedLights.length === 0) {
            // Fallback if no group and light matched
            let x = light;
            light = group;
            group = x;
            console.log("SWITCHED");
            // Try searching again, but swap light and group queries
            if (light !== "*") {
                matchedLights = fuzzySearch(light, allLights);
            }
            if (group !== "*" && group !== "") {
                matchedGroups = fuzzySearch(group, allGroups);
            }
            if (matchedGroups.length === 0 && matchedLights.length === 0) {
                return "Ekki tókst að finna ljós";
            }
        }
        if (matchedLights.length === 0) {
            console.log("found a group");
            // Found a group
            if (light === "*") {
                console.log("target entire group");
                // Target entire group
                api_endpoint = `groups/${matchedGroups[0].ID}/action`;
                // Update matched lights
                matchedLights = allLights.filter((li) =>
                    matchedGroups[0].info.lights.includes(li.ID)
                );
            } else {
                console.log("villa í ljósinu");
                return `Ekkert ljós fannst í herberginu ${group} með nafnið ${light}.`;
            }
        } else if (matchedGroups.length === 0) {
            console.log("fann ljós");
            // Found a light
            api_endpoint = `lights/${matchedLights[0].ID}/state`;
            matchedLights = [matchedLights[0]];
        } else {
            console.log("fundum bæði");
            // Found both, try to intelligently find a light within a group
            for (let i1 in matchedGroups) {
                let currGroup = matchedGroups[i1];
                for (let i2 in matchedLights) {
                    let currLight = matchedLights[i2];
                    if (currGroup.info.lights.includes(currLight.ID)) {
                        // Found the matched light inside the current group; perfect
                        api_endpoint = `lights/${currLight.ID}/state`;
                        matchedLights = [currLight];
                        break;
                    }
                }
                if (api_endpoint !== null) {
                    // Found a light, end loop
                    break;
                }
            }
        }
    }
    return {
        endpoint: api_endpoint,
        affectedLights: matchedLights,
        affectedGroups: matchedGroups,
    };
}

/** Gets a target for the given query and sets the state of the target to the given state using a fetch request.
 *  @param {string} hub_ip - the IP address of the Philips Hue hub on the local network
 *  @param {string} username - the username we have registered with the hub
 *  @param {string} light - the name of a light, "*" matches anything
 *  @param {string} group - the name of a group, "*" matches anything
 *  @param {string} json_data - the JSON encoded state to set the target to e.g. {"on": true} or {"scene": "energize"}
 *  @return {string} Basic string explaining what happened (in Icelandic).
 */
async function setLights(hub_ip, username, light, group, json_data) {
    let parsedState = JSON.parse(json_data);
    console.log("parsedState:", parsedState);
    let promiseList = [getAllGroups(hub_ip, username), getAllLights(hub_ip, username)];
    if (parsedState.scene) {
        promiseList.push(getAllScenes(hub_ip, username));
    }
    console.log("created promises...");
    // Get all lights and all groups from the API
    // (and all scenes if "scene" was a paramater)
    return await Promise.allSettled(promiseList).then((resolvedPromises) => {
        console.log("promises resolved!");
        let allGroups = resolvedPromises[0].value;
        console.log("allGroups:", allGroups);
        let allLights = resolvedPromises[1].value;
        console.log("allLights:", allLights);
        let allScenes;
        if (resolvedPromises.length > 2) {
            allScenes = resolvedPromises[2].value;
            let scenesResults = fuzzySearch(parsedState.scene, allScenes);
            console.log("scenesResults:", scenesResults);
            if (scenesResults.length == 0) {
                return `Ekki tókst að finna senuna ${parsedState.scene}.`;
            }
            parsedState.scene = scenesResults[0].ID; // Change the scene parameter to the scene ID
        }
        let targetObj = findLights(light, group, allLights, allGroups);
        let payload = JSON.stringify(parsedState);
        // Send data to API
        console.log("sendum payload:", payload);
        call_api_v1(hub_ip, username, targetObj.endpoint, payload);
        console.log("buid :)");

        // Deal with IKEA TRADFRI bug
        // (sometimes can't handle more than one change at a time)
        if (
            containsIKEABulb(targetObj.affectedLights) &&
            (parsedState.scene || Object.keys(parsedState).length > 2)
        ) {
            console.log("ja ikea pera");
            let sleep = (ms) => new Promise((r) => setTimeout(r, ms));
            sleep(450).then(() => {
                call_api_v1(hub_ip, username, targetObj.endpoint, payload);
            });
        }
        console.log("buid 2 :)");
        // Basic formatting of answers
        if (parsedState.scene) {
            return "Ég breytti um senu.";
        }
        if (parsedState.on == false) {
            return "Ég slökkti ljósin.";
        }
        if (parsedState.on == true && Object.keys(parsedState).length == 1) {
            console.log("alveg buid faddfafdafda");
            return "Ég kveikti ljósin.";
        }
        if (parsedState.bri_inc && parsedState.bri_inc > 0) {
            return "Ég hækkaði birtuna.";
        }
        if (parsedState.bri_inc && parsedState.bri_inc < 0) {
            return "Ég minnkaði birtuna.";
        }
        if (parsedState.xy || parsedState.hue) {
            return "Ég breytti lit ljóssins.";
        }
        return "Stillingu ljósa var breytt.";
    });
}
