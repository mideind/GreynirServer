"use strict";
// Constants to be used when setting lights from HTML

var BRIDGE_IP = "192.168.1.68";
var USERNAME = "q2jNarhGHO9izO0xZZXcoww5GYANGi6mZyJYgMdL";
// const QUERY_EX = "eldhús";
// const STATE_EX = JSON.stringify({scene: "rómó"})
// const LIGHTS_EX = test();
// const LIGHTS_EX = '{"1":{"state":{"on":true,"bri":100,"hue":6140,"sat":232,"effect":"none","xy":[0.5503,0.4000],"ct":500,"alert":"select","colormode":"xy","mode":"homeautomation","reachable":true},"swupdate":{"state":"noupdates","lastinstall":"2022-05-27T14:23:54"},"type":"Extended color light","name":"litaljós","modelid":"LCA001","manufacturername":"Signify Netherlands B.V.","productname":"Hue color lamp","capabilities":{"certified":true,"control":{"mindimlevel":200,"maxlumen":800,"colorgamuttype":"C","colorgamut":[[0.6915,0.3083],[0.1700,0.7000],[0.1532,0.0475]],"ct":{"min":153,"max":500}},"streaming":{"renderer":true,"proxy":true}},"config":{"archetype":"sultanbulb","function":"mixed","direction":"omnidirectional","startup":{"mode":"safety","configured":true}},"uniqueid":"00:17:88:01:06:79:c3:94-0b","swversion":"1.93.7","swconfigid":"3C05E7B6","productid":"Philips-LCA001-5-A19ECLv6"},"2":{"state":{"on":true,"bri":2,"ct":454,"alert":"select","colormode":"ct","mode":"homeautomation","reachable":false},"swupdate":{"state":"notupdatable","lastinstall":"2020-06-29T12:05:21"},"type":"Color temperature light","name":"Ikea pera Uno","modelid":"TRADFRI bulb E27 WS opal 1000lm","manufacturername":"IKEA of Sweden","productname":"Color temperature light","capabilities":{"certified":false,"control":{"ct":{"min":250,"max":454}},"streaming":{"renderer":false,"proxy":false}},"config":{"archetype":"classicbulb","function":"functional","direction":"omnidirectional"},"uniqueid":"cc:cc:cc:ff:fe:02:92:52-01","swversion":"2.0.023"},"3":{"state":{"on":true,"bri":105,"ct":454,"alert":"select","colormode":"ct","mode":"homeautomation","reachable":false},"swupdate":{"state":"notupdatable","lastinstall":"2020-07-20T13:03:26"},"type":"Color temperature light","name":"lesljós","modelid":"TRADFRI bulb E14 WS opal 400lm","manufacturername":"IKEA of Sweden","productname":"Color temperature light","capabilities":{"certified":false,"control":{"ct":{"min":250,"max":454}},"streaming":{"renderer":false,"proxy":false}},"config":{"archetype":"classicbulb","function":"functional","direction":"omnidirectional"},"uniqueid":"90:fd:9f:ff:fe:93:be:a1-01","swversion":"1.2.217"}}'
// const GROUPS_EX = '{"1":{"name":"eldhús","lights":["1"],"sensors":[],"type":"Room","state":{"all_on":true,"any_on":true},"recycle":false,"class":"Living room","action":{"on":true,"bri":100,"hue":6140,"sat":232,"effect":"none","xy":[0.5503,0.4000],"ct":500,"alert":"select","colormode":"xy"}},"2":{"name":"Hús","lights":["3","2","1"],"sensors":[],"type":"Zone","state":{"all_on":true,"any_on":true},"recycle":false,"class":"Downstairs","action":{"on":true,"bri":100,"hue":6140,"sat":232,"effect":"none","xy":[0.5503,0.4000],"ct":500,"alert":"select","colormode":"xy"}},"3":{"name":"skrifstofa","lights":["2","3"],"sensors":[],"type":"Room","state":{"all_on":true,"any_on":true},"recycle":false,"class":"Living room","action":{"on":true,"bri":105,"ct":454,"alert":"select","colormode":"ct"}}}'


async function getIdObject(query) {
        let allLights = await getAllLights();
        let allGroups = await getAllGroups();
        let returnObject

        console.log("all lights: ", allLights);
        console.log("query :", query);

        let lightsResult = await philipsFuzzySearch(query, allLights);
        let groupsResult = await philipsFuzzySearch(query, allGroups);
        
        console.log("lightResult :", lightsResult);
        console.log("groupsResult :", groupsResult);
        if (lightsResult != null) {
            returnObject = {id: lightsResult.ID, type: "light", url: `lights/${lightsResult.ID}/state`};
            console.log("returnObject: ", returnObject);
        }
        else if (groupsResult != null) {
            console.log("groupresult test")
            returnObject = {id: groupsResult.ID, type: "group", url: `groups/${groupsResult.ID}/action`};
            console.log("returnObject: ",returnObject);
        }
        console.log("returnObject: ",returnObject)
        return returnObject;
        //vantar e.k. error
};


async function getSceneID(scene_name){
    let allScenes = await getAllScenes();
    let scenesResult = await philipsFuzzySearch(scene_name, allScenes);
    if (scenesResult != null) {
        return scenesResult.ID;
    }
    else {
        return;
    }
};


async function setLights(query, state){
    let idObject = await getIdObject(query);
    if (idObject === undefined) {
        return "Ekki tókst að finna ljós"
    };
    let ID = idObject.id;
    let parsed_state = JSON.parse(state);
    console.log("parsed state :", parsed_state);

    // Check if state includes a scene or a brightness change
    if (parsed_state.scene) {
        let sceneID = await getSceneID(parsed_state.scene);
        console.log("sceneID :", sceneID)
        if (sceneID === undefined) {
            return "Ekki tókst að finna senu"
        }
        else {
            console.log("tókst")
            parsed_state.scene = sceneID;
            state = JSON.stringify(parsed_state);
        }
    }
    else if (parsed_state.bri_inc) {
        console.log(parsed_state.bri_inc);
        state = JSON.stringify(parsed_state);
    }
    // Send data to API
    let url = idObject.url;
    console.log("url", url)
    console.log(state);
    console.log("idObject", idObject);
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
};


function setLightsFromHTML() {
    let query = document.getElementById("queryInput").value;
    let stateObject = new Object();
    stateObject.bri_inc = Number(document.getElementById("brightnessInput").value);
    stateObject = JSON.stringify(stateObject);
    console.log(stateObject);
    setLights(query, stateObject);
};


function syncSetLights(query, state) {
    setLights(query, state);
    return query;
};


function epliSceneTest() {
    setLights('eldhús', '{"on": true, "scene": "epli"}');
};


function queryTest() {
    let query = document.getElementById('queryInput').value;
    let bool = document.getElementById("boolInput").value;
    let scene = document.getElementById("sceneInput").value;
    if (scene === "") {
        syncSetLights(query, `{"on": ${bool}}`);
    }
    else{
        syncSetLights(query, `{"scene": "${scene}"}`);
    }
};


// async function getIdObjectOld(query) {
//     let allLights = await getAllLights();
//     let allGroups = await getAllGroups();

//     for (let light in allLights) {
//         if (allLights[light].name === query) {
//             let returnObject = {id: light, type: "light", url: `lights/${light}/state`};
//             return returnObject;
//         }
//     }
//     for (let group in allGroups) {
//         if (allGroups[group].name === query) {
//             let returnObject = {id: group, type: "group", url: `groups/${group}/action`};
//             return returnObject;
//         }
//     }
//     //vantar e.k. error
//     return;