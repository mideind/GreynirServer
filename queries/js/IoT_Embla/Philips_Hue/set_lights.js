"use strict";

// Constants to be used when setting lights from HTML
// var BRIDGE_IP = "192.168.1.68";
// var USERNAME = "BzdNyxr6mGSHVdQN86UeZP67qp5huJ2Q6TWyTzvz";

// TODO: Implement a hotfix for Ikea Tradfri bulbs, since it can only take one argument at a time

/** Gets a target for the given query and sets the state of the target to the given state using a fetch request.
 *  @param {String} target - the target to find the target e.g. "eldhús" or "lampi"
 *  @param {String} state - the state to set the target to e.g. "{"on": true}" or "{"scene": "energize"}"
 */
function setLights(target, state) {
    let parsedState = JSON.parse(state);
    let promiseList = [getAllGroups(), getAllLights()];
    let sceneName;
    if (parsedState.scene) {
        sceneName = parsedState.scene;
        promiseList.push(getAllScenes());
    }
    // Get all lights and all groups from the API (and all scenes if "scene" was a paramater)
    Promise.allSettled(promiseList).then((resolvedPromises) => {
        let allGroups = resolvedPromises[0].value;
        let allLights = resolvedPromises[1].value;
        let allScenes;
        try {
            allScenes = resolvedPromises[2].value;
        } catch (e) {
            console.log("No scene in state");
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
            } else {
                parsedState.scene = sceneID; // Change the scene parameter to the scene ID
                state = JSON.stringify(parsedState);
            }
        } else if (parsedState.bri_inc) {
            state = JSON.stringify(parsedState);
        }

        // Send data to API
        let url = targetObject.url;
        call_api(url, state);
        let isTradfriBulb = check_if_if_ikea_bulb_in_group(
            targetObject,
            allLights
        );
        if (sceneName && isTradfriBulb) {
            const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
            sleep(450).then(() => {
                call_api(url, state);
            });
        }
    });
    return "Ég var að kveikja ljósin.";
}
//         fetch(`http://${BRIDGE_IP}/api/${USERNAME}/${url}`, {
//             method: "PUT",
//             body: state,
//         })
//             .then((resp) => resp.json())
//             .then((obj) => {
//                 console.log(obj);
//             })
//             .catch((err) => {
//                 console.log("an error occurred!");
//             });
//     });
// }

function call_api(url, state) {
    console.log("call api");
    fetch(`http://${BRIDGE_IP}/api/${USERNAME}/${url}`, {
        method: "PUT",
        body: state,
    })
        .then((resp) => resp.json())
        .then((obj) => {
            console.log(obj);
        })
        .catch((err) => {
            console.log("an error occurred!");
        });
    return;
}

/** Finds a matching light or group and returns an object with the ID, name and url for the target
 * @param {String} target - the target to find the target e.g. "eldhús"
 * @param {Object} allLights - an object of all lights from the API
 * @param {Object} allGroups - an object of all groups from the API
 */
function getTargetObject(target, allLights, allGroups) {
    let targetObject, selection, url;
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
    console.log("sceneResult :", scenesResult);
    if (scenesResult != null) {
        return scenesResult.result.ID;
    } else {
        return;
    }
}

/* Tester function for setting lights directly from HTML controls */
function setLightsFromHTML() {
    let target = document.getElementById("queryInput").value;
    let stateObject = new Object();
    stateObject.bri_inc = Number(
        document.getElementById("brightnessInput").value
    );
    stateObject = JSON.stringify(stateObject);
    setLights(target, stateObject);
}

/* Tester function for setting lights directly from HTML input fields */
function queryTestFromHTML() {
    let target = document.getElementById("queryInput").value;
    let bool = document.getElementById("boolInput").value;
    let scene = document.getElementById("sceneInput").value;
    console.log(target);
    if (scene === "") {
        setLights(target, `{"on": ${bool}}`);
    } else {
        setLights(target, `{"scene": "${scene}"}`);
    }
}

function check_if_if_ikea_bulb_in_group(groupsObject, all_lights) {
    for (let key in groupsObject.lights) {
        let lightID = groupsObject.lights[key];
        let light = all_lights[lightID];
        if (
            light.manufacturername.includes("IKEA") ||
            light.modelid.includes("TRADFRI") ||
            light.manufacturername.includes("ikea") ||
            light.manufacturername.includes("tradfri")
        );

        {
            return true;
        }
    }
}

// /** Finds a matching light or group and returns an object with the ID, name and url for the target
//  * @param {String} target - the target to find the target e.g. "eldhús"
//  * @param {Object} allLights - an array of all lights from the API
//  * @param {Object} allGroups - an array of all groups from the API
//  */
//  function getTargetObjectOLD(target, allLights, allGroups) {
//     let targetObject;
//     let lightsResult = philipsFuzzySearch(target, allLights);
//     let groupsResult = philipsFuzzySearch(target, allGroups);
//     console.log("lightsResult: ", lightsResult);
//     console.log("groupsResult: ", groupsResult);

//     if (lightsResult != null && groupsResult == null) {
//         // Found a match for a single light
//         targetObject = {
//             id: lightsResult.result.ID,
//             type: "light",
//             url: `lights/${lightsResult.result.ID}/state`,
//         };
//     } else if (groupsResult != null && lightsResult == null) {
//         // Found a match for a light group
//         targetObject = {
//             id: groupsResult.result.ID,
//             type: "group",
//             url: `groups/${groupsResult.result.ID}/action`,
//         };
//     } else if (groupsResult != null && lightsResult != null) {
//         let lightsScore = lightsResult.score;
//         let groupsScore = groupsResult.score;
//         let selection = lightsScore > groupsScore ? lightsResult : groupsResult;
//         console.log("selection :", selection);
//         // Found a match for a light group and a light
//         targetObject = {
//             id: lightsResult.result.ID,
//             type: "light",
//             url: `lights/${lightsResult.result.ID}/state`,
//         };
//     }
//     console.log("targetObject: ", targetObject);
//     return targetObject;
// }
