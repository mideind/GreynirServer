"use strict";

function call_api(url, state) {
    fetch(`http://${BRIDGE_IP}/api/${USERNAME}/${url}`, {
        method: "PUT",
        body: state,
    })
        .then((resp) => resp.json())
        .then((obj) => {})
        .catch((err) => {});
    return;
}

/** Finds a matching light or group and returns an object with the ID, name and url for the target
 * @param {String} target - the target to find the target e.g. "eldhús"
 * @param {Object} allLights - an object of all lights from the API
 * @param {Object} allGroups - an object of all groups from the API
 */
function getTargetObject(target, allLights, allGroups) {
    let targetObject;
    let lightsResult = philipsFuzzySearch(target, allLights);
    let groupsResult = philipsFuzzySearch(target, allGroups);

    if (lightsResult != null && groupsResult != null) {
        // Found a match for a light group and a light+
        targetObject =
            lightsResult.score < groupsResult.score // Select the light with the highest score
                ? {
                      id: lightsResult.result.ID,
                      url: `lights/${lightsResult.result.ID}/state`,
                  }
                : {
                      id: groupsResult.result.ID,
                      lights: groupsResult.result.info.lights,
                      url: `groups/${groupsResult.result.ID}/action`,
                  };
    } else if (lightsResult != null && groupsResult == null) {
        // Found a match for a single light
        targetObject = {
            id: lightsResult.result.ID,
            url: `lights/${lightsResult.result.ID}/state`,
        };
    } else if (groupsResult != null && lightsResult == null) {
        // Found a match for a light group
        targetObject = {
            id: groupsResult.result.ID,
            lights: groupsResult.result.info.lights,
            url: `groups/${groupsResult.result.ID}/action`,
        };
    } else {
        return;
    }
    return targetObject;
}

/** Returns the ID for a given scene name using fuzzy search
 * @param {String} sceneName - the name of the scene to find
 * @param {Object} allScenes - an array of all scenes from the API
 */
function getSceneID(scene_name, allScenes) {
    let scenesResult = philipsFuzzySearch(scene_name, allScenes);
    if (scenesResult != null) {
        return scenesResult.result.ID;
    } else {
        return;
    }
}

/**
 * Check whether any of the targeted lights are Ikea TRADFRI lights.
 * Done in order to deal with a bug where the lights only accept
 * one parameter at a time.
 * @param {Object} targetObject Object containing all lights in target/query
 * @param {Object} all_lights Object containing info for all connected lights
 * @returns True if any of the query lights are Ikea TRADFRI lights, false otherwise
 */
function check_if_ikea_bulb_in_target(targetObject, all_lights) {
    for (let key in targetObject.lights) {
        let lightID = targetObject.lights[key];
        let light = all_lights[lightID];
        if (
            light.manufacturername.includes("IKEA") ||
            light.modelid.includes("TRADFRI") ||
            light.manufacturername.includes("ikea") ||
            light.manufacturername.includes("tradfri")
        ) {
            return true;
        }
    }
}

/** Gets a target for the given query and sets the state of the target to the given state using a fetch request.
 *  @param {String} target - the target to find the target, e.g. "eldhús" or "lampi"
 *  @param {String} state - the state to set the target to e.g. {"on": true} or {"scene": "energize"}
 *  @return Basic string explaining what happened (in Icelandic).
 */
async function setLights(target, state) {
    let parsedState = JSON.parse(state);
    let promiseList = [getAllGroups(), getAllLights()];
    let sceneName;
    if (parsedState.scene) {
        sceneName = parsedState.scene;
        promiseList.push(getAllScenes());
    }
    // Get all lights and all groups from the API (and all scenes if "scene" was a paramater)
    return await Promise.allSettled(promiseList).then((resolvedPromises) => {
        let allGroups = resolvedPromises[0].value;
        let allLights = resolvedPromises[1].value;
        let allScenes;
        if (resolvedPromises.length > 2) {
            allScenes = resolvedPromises[2].value;
        }

        // Get the target object for the given target
        let targetObject = getTargetObject(target, allLights, allGroups);
        if (targetObject === undefined) {
            return "Ekki tókst að finna ljós";
        }

        // Check if state includes a scene or a brightness change
        if (sceneName) {
            let sceneID = getSceneID(parsedState.scene, allScenes);
            if (sceneID === undefined) {
                return "Ekki tókst að finna senu";
            }
            parsedState.scene = sceneID; // Change the scene parameter to the scene ID
            state = JSON.stringify(parsedState);
        } else if (parsedState.bri_inc) {
            state = JSON.stringify(parsedState);
        }

        // Send data to API
        let url = targetObject.url;
        call_api(url, state);

        // Deal with Ikea TRADFRI bug
        let isTradfriBulb = check_if_ikea_bulb_in_target(targetObject, allLights);
        if (sceneName && isTradfriBulb) {
            let sleep = (ms) => new Promise((r) => setTimeout(r, ms));
            sleep(450).then(() => {
                call_api(url, state);
            });
        }

        // Basic formatting of answers
        if (parsedState.scene) {
            return "Ég breytti um senu.";
        }
        if (parsedState.on == false) {
            return "Ég slökkti ljósin.";
        }
        if (parsedState.on == true && Object.keys(parsedState).length == 1) {
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
        return "Stillingu hefur verið breytt.";
    });
}
