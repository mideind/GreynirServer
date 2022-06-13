"use strict";

// Constants to be used when setting lights from HTML
// var BRIDGE_IP = "192.168.1.68";
// var USERNAME = "p3obluiXT13IbHMpp4X63ZvZnpNRdbqqMt723gy2";

// TODO: Implement a hotfix for Ikea Tradfri bulbs, since it can only take one argument at a time
/* Gets a target for the given query and sets the state of the target to the given state using a fetch request.
 *  query - the query to find the target e.g. "eldhús"
 *  state - the state to set the target to e.g. "{"on": true}" or "{"scene": "energize"}"
 */
function setLights(query, state) {
    let parsed_state = JSON.parse(state);
    let promiseList = [getAllGroups(), getAllLights()];
    let sceneName;
    if (parsed_state.scene) {
        sceneName = parsed_state.scene;
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
        // Get the target object for the given query
        let targetObject = getTargetObject(query, allLights, allGroups);
        console.log("targetObject: ", targetObject);
        if (targetObject === undefined) {
            return "Ekki tókst að finna ljós";
        }
        if (sceneName) {
            let sceneID = getSceneID(parsed_state.scene, allScenes);
            if (sceneID === undefined) {
                return "Ekki tókst að finna senu";
            } else {
                parsed_state.scene = sceneID; // Change the scene parameter to the scene ID
                state = JSON.stringify(parsed_state);
            }
        }
        // Check if state includes a scene or a brightness change
        else if (parsed_state.bri_inc) {
            state = JSON.stringify(parsed_state);
        }
        // Send data to API
        let url = targetObject.url;
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
    });
}

/** Finds a matching light or group and returns an object with the ID, name and url for the target */
function getTargetObject(query, allLights, allGroups) {
    let targetObject;
    let lightsResult = philipsFuzzySearch(query, allLights);
    let groupsResult = philipsFuzzySearch(query, allGroups);

    if (lightsResult != null) {
        // Found a match for a single light
        targetObject = {
            id: lightsResult.ID,
            type: "light",
            url: `lights/${lightsResult.ID}/state`,
        };
    } else if (groupsResult != null) {
        // Found a match for a light group
        targetObject = {
            id: groupsResult.ID,
            type: "group",
            url: `groups/${groupsResult.ID}/action`,
        };
    }
    return targetObject;
}

/** Returns the ID for a given scene name using fuzzy search */
function getSceneID(scene_name, allScenes) {
    let scenesResult = philipsFuzzySearch(scene_name, allScenes);
    if (scenesResult != null) {
        return scenesResult.ID;
    } else {
        return;
    }
}

/* Tester function for setting lights directly from HTML controls */
function setLightsFromHTML() {
    let query = document.getElementById("queryInput").value;
    let stateObject = new Object();
    stateObject.bri_inc = Number(
        document.getElementById("brightnessInput").value
    );
    stateObject = JSON.stringify(stateObject);
    setLights(query, stateObject);
}

/* Tester function for setting lights directly from HTML input fields */
function queryTestFromHTML() {
    let query = document.getElementById("queryInput").value;
    let bool = document.getElementById("boolInput").value;
    let scene = document.getElementById("sceneInput").value;
    console.log(query);
    if (scene === "") {
        setLights(query, `{"on": ${bool}}`);
    } else {
        setLights(query, `{"scene": "${scene}"}`);
    }
}
