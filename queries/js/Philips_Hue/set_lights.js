"use strict";
/**
 * An object containing info on a light
 * connected to the Philips Hue hub,
 * after we restructure it.
 * @typedef {Object} Light
 * @property {string} ID
 * @property {Object} info
 * @property {string} info.manufacturername
 * @property {string} info.modelid
 * @property {Object} info.state
 * @property {boolean} info.state.on
 * @property {number} info.state.bri
 * @property {number} info.state.hue
 * @property {number} info.state.sat
 * @property {string} info.state.effect
 * @property {number[]} info.state.xy
 * @property {number} info.state.ct
 * @property {string} info.state.alert
 * @property {string} info.state.colormode
 * @property {string} info.state.mode
 * @property {boolean} info.state.reachable
 * @property {string} info.type
 * @property {string} info.name
 * @property {string} info.modelid
 * @property {string} info.manufacturername
 * @property {string} info.productname
 * @property {Object} info.capabilities
 * @property {string} info.uniqueid
 * @property {string} info.swversion
 * @property {string} info.swconfigid
 * @property {string} info.productid
 */

/**
 * An object containing info
 * on a group of lights.
 * @typedef {Object} Group
 * @property {string} ID
 * @property {Object} info
 * @property {string} info.name
 * @property {string[]} info.lights
 * @property {Object[]} info.sensors
 * @property {string} info.type
 * @property {Object} info.state
 * @property {boolean} info.state.all_on
 * @property {boolean} info.state.any_on
 * @property {string} info.class
 * @property {Object} info.action
 */

/**
 * An object containing info on a scene.
 * @typedef {Object} Scene
 * @property {string} ID
 * @property {Object} info
 * @property {string} info.name
 * @property {string} info.type
 * @property {string} info.group
 * @property {string[]} info.lights
 * @property {string} info.owner
 * @property {boolean} info.recycle
 * @property {boolean} info.locked
 * @property {string} info.picture
 * @property {string} info.image
 * @property {string} info.lastupdated
 * @property {string} info.version
 */

/** Fuzzy search function that returns an object in the form of {result: (Object), score: (Number)}
 * @template T
 * @param {string} query - the search term
 * @param {T[]} data - the data to search
 * @param {string[]} searchKeys - the key/s for searching the data
 * @return {T[]} List of results from search
 */
function fuzzySearch(query, data, searchKeys) {
    if (searchKeys === undefined) {
        searchKeys = ["info.name"];
    }
    // Set default argument for searchKeys

    // Fuzzy search for the query term (returns an array of objects)
    /* jshint ignore:start */
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
    /* jshint ignore:end */
}

/**
 * @typedef {Object} APIResponseItem
 * @property {Object|undefined} error
 * @property {string|undefined} error.type
 * @property {string|undefined} error.address
 * @property {string|undefined} error.description
 * @property {Object|undefined} success
 */

/** Send a PUT request to the given URL endpoint of the Philips Hue hub.
 * @param {string} hub_ip - the IP address of the Philips Hue hub on the local network
 * @param {string} username - the username we have registered with the hub
 * @param {string} url_endpoint - the relevant URL endpoint of the Hue API
 * @param {string} state - JSON encoded body
 * @returns {Promise<APIResponseItem[]>} Response from API
 */
async function put_api_v1(hub_ip, username, url_endpoint, state) {
    return fetch(`http://${hub_ip}/api/${username}/${url_endpoint}`, {
        method: "PUT",
        body: state,
    })
        .then((resp) => resp.json())
        .catch((err) => [{ error: { description: "Error contacting hub." } }]);
}

/**
 * Fetch all connected lights for this hub.
 * @param {string} hub_ip - the IP address of the Philips Hue hub on the local network
 * @param {string} username - the username we have registered with the hub
 * @returns {Promise<Light[]>} Promise which resolves to list of all connected lights
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
 * @returns {Promise<Group[]>} Promise which resolves to list of all light groups
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
 * @returns {Promise<Scene[]>} Promise which resolves to list of registered scenes
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
 * Check whether a light objects corresponds
 * to an IKEA TRADFRI lightbulb.
 * @param {Light} light - light object
 * @returns {boolean} True if light is IKEA TRADFRI bulb
 */
function isIKEABulb(light) {
    return (
        light.info.manufacturername.toLowerCase().includes("ikea") ||
        light.info.modelid.toLowerCase().includes("tradfri")
    );
}

/**
 * Target, describing API endpoint along with
 * @typedef {Object} TargetObject
 * @property {string} api_endpoint
 * @property {Light[]} affectedLights
 * @property {Group[]} affectedGroups
 * @property {(string|undefined)} error
 */

/**
 * For a given light-group query pair,
 * find the most appropriate API endpoint.
 * @param {string} light - query for a light
 * @param {string} group - query for a group
 * @param {Light[]} allLights - list of all lights
 * @param {Group[]} allGroups - list of all groups
 * @returns {TargetObject} Object containing API endpoint and affected lights/groups
 */
function findLights(light, group, allLights, allGroups) {
    /** @type {Light[]} */
    let matchedLights = [];
    /** @type {Group[]} */
    let matchedGroups = [];

    // Find matching lights
    if (light !== "*") {
        matchedLights = fuzzySearch(light, allLights);
    }
    // Find matching groups
    if (group !== "*" && group !== "") {
        matchedGroups = fuzzySearch(group, allGroups);
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
            // Try searching again, but swap light and group queries
            if (light !== "*") {
                matchedLights = fuzzySearch(light, allLights);
            }
            if (group !== "*" && group !== "") {
                matchedGroups = fuzzySearch(group, allGroups);
            }
            if (matchedGroups.length === 0 && matchedLights.length === 0) {
                return {
                    api_endpoint: "",
                    affectedLights: [],
                    affectedGroups: [],
                    error: "Ekki tókst að finna ljós.",
                };
            }
        }
        if (matchedLights.length === 0) {
            // Found a group
            if (light === "*") {
                // Target entire group
                api_endpoint = `groups/${matchedGroups[0].ID}/action`;
                // Update matched lights
                matchedLights = allLights.filter((li) =>
                    matchedGroups[0].info.lights.includes(li.ID)
                );
            } else {
                return {
                    api_endpoint: "",
                    affectedLights: [],
                    affectedGroups: [],
                    error: `Ekkert ljós fannst í herberginu ${group} með nafnið ${light}.`,
                };
            }
        } else if (matchedGroups.length === 0) {
            // Found a light
            api_endpoint = `lights/${matchedLights[0].ID}/state`;
            matchedLights = [matchedLights[0]];
        } else {
            // Found both, try to intelligently find a light within a group
            for (let i1 = 0; i1 < matchedGroups.length; i1++) {
                let currGroup = matchedGroups[i1];
                for (let i2 = 0; i2 < matchedLights.length; i2++) {
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

/**
 * The payload object that is sent, json encoded,
 * to the Hue API.
 * @typedef {Object} Payload
 * @property {boolean} on
 * @property {number|undefined} bri
 * @property {number|undefined} hue
 * @property {number|undefined} sat
 * @property {number[]|undefined} xy
 * @property {number|undefined} ct
 * @property {string|undefined} alert
 * @property {string|undefined} scene
 * @property {string|undefined} effect
 * @property {number|undefined} transitiontime
 * @property {number|undefined} bri_inc
 * @property {number|undefined} sat_inc
 * @property {number|undefined} hue_inc
 * @property {number|undefined} ct_inc
 * @property {number|undefined} xy_inc
 */

/** Gets a target for the given query and sets the state of the target to the given state using a fetch request.
 *  @param {string} hub_ip - the IP address of the Philips Hue hub on the local network
 *  @param {string} username - the username we have registered with the hub
 *  @param {string} light - the name of a light, "*" matches anything
 *  @param {string} group - the name of a group, "*" matches anything
 *  @param {string} json_data - the JSON encoded state to set the target to e.g. {"on": true} or {"scene": "energize"}
 *  @return {string} Basic string explaining what happened (in Icelandic).
 */
async function setLights(hub_ip, username, light, group, json_data) {
    /** @type {Payload} */
    let parsedState = JSON.parse(json_data);
    let promiseList = [
        getAllGroups(hub_ip, username),
        getAllLights(hub_ip, username),
        // Fetch all scenes if payload includes a scene,
        // otherwise have an empty list
        parsedState.scene !== undefined ? getAllScenes(hub_ip, username) : Promise.resolve([])
    ];

    // Get all lights and all groups from the API
    // (and all scenes if "scene" was a paramater)
    return await Promise.allSettled(promiseList).then(async (resolvedPromises) => {
        /** @type {Group[]} */
        let allGroups = resolvedPromises[0].value;
        /** @type {Light[]} */
        let allLights = resolvedPromises[1].value;
        /** @type {Scene[]} */
        let allScenes = resolvedPromises[2].value;
        if (allScenes.length > 0) {
            let scenesResults = fuzzySearch(parsedState.scene, allScenes);
            if (scenesResults.length === 0) {
                return `Ekki tókst að finna senuna ${parsedState.scene}.`;
            }
            // Change the scene parameter to the scene ID
            parsedState.scene = scenesResults[0].ID;
            if (group === "") {
                // If scene is specified with no group,
                // find scene's group and set group variable
                for (let g = 0; g < allGroups.length; g++) {
                    if (allGroups[g].ID === scenesResults[0].info.group) {
                        group = allGroups[g].info.name;
                        break;
                    }
                }
            }
        }

        // Find the lights we want to target
        let targetObj = findLights(light, group, allLights, allGroups);
        if (targetObj.error !== undefined) {
            // Ran into error while trying to find a light
            return targetObj.error;
        }

        let payload = JSON.stringify(parsedState);
        // Send data to API
        console.log("Endpoint:", targetObj.endpoint);
        console.log("Payload:", payload);
        let response = await put_api_v1(hub_ip, username, targetObj.endpoint, payload);
        console.log("Server response:", JSON.stringify(response));

        // Deal with IKEA TRADFRI bug
        // (sometimes can't handle more than one change at a time)
        if (
            (parsedState.scene || Object.keys(parsedState).length > 2) &&
            targetObj.affectedLights.some(isIKEABulb)
        ) {
            let sleep = (ms) => new Promise((r) => setTimeout(r, ms));
            sleep(450).then(() => {
                put_api_v1(hub_ip, username, targetObj.endpoint, payload);
            });
        }

        // Basic formatting of answers
        if (parsedState.scene) {
            return "Ég kveikti á senu.";
        }
        if (parsedState.on === false) {
            if (light === "*") {
                return "Ég slökkti ljósin.";
            }
            return "Ég slökkti ljósið.";
        }
        if (parsedState.on === true && Object.keys(parsedState).length === 1) {
            if (light === "*") {
                return "Ég kveikti ljósin.";
            }
            return "Ég kveikti ljósið.";
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
    }).catch((err) => {
        return "Ekki náðist samband við Philips Hue miðstöðina.";
    });
}
