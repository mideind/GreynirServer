"use strict";
// Constants to be used when setting lights from HTML

// var BRIDGE_IP = "192.168.1.68"
// var USERNAME = "q2jNarhGHO9izO0xZZXcoww5GYANGi6mZyJYgMdL"
// const QUERY_EX = "eldhús";
// const STATE_EX = JSON.stringify({scene: "rómó"})
// const LIGHTS_EX = test();
// const LIGHTS_EX = '{"1":{"state":{"on":true,"bri":100,"hue":6140,"sat":232,"effect":"none","xy":[0.5503,0.4000],"ct":500,"alert":"select","colormode":"xy","mode":"homeautomation","reachable":true},"swupdate":{"state":"noupdates","lastinstall":"2022-05-27T14:23:54"},"type":"Extended color light","name":"litaljós","modelid":"LCA001","manufacturername":"Signify Netherlands B.V.","productname":"Hue color lamp","capabilities":{"certified":true,"control":{"mindimlevel":200,"maxlumen":800,"colorgamuttype":"C","colorgamut":[[0.6915,0.3083],[0.1700,0.7000],[0.1532,0.0475]],"ct":{"min":153,"max":500}},"streaming":{"renderer":true,"proxy":true}},"config":{"archetype":"sultanbulb","function":"mixed","direction":"omnidirectional","startup":{"mode":"safety","configured":true}},"uniqueid":"00:17:88:01:06:79:c3:94-0b","swversion":"1.93.7","swconfigid":"3C05E7B6","productid":"Philips-LCA001-5-A19ECLv6"},"2":{"state":{"on":true,"bri":2,"ct":454,"alert":"select","colormode":"ct","mode":"homeautomation","reachable":false},"swupdate":{"state":"notupdatable","lastinstall":"2020-06-29T12:05:21"},"type":"Color temperature light","name":"Ikea pera Uno","modelid":"TRADFRI bulb E27 WS opal 1000lm","manufacturername":"IKEA of Sweden","productname":"Color temperature light","capabilities":{"certified":false,"control":{"ct":{"min":250,"max":454}},"streaming":{"renderer":false,"proxy":false}},"config":{"archetype":"classicbulb","function":"functional","direction":"omnidirectional"},"uniqueid":"cc:cc:cc:ff:fe:02:92:52-01","swversion":"2.0.023"},"3":{"state":{"on":true,"bri":105,"ct":454,"alert":"select","colormode":"ct","mode":"homeautomation","reachable":false},"swupdate":{"state":"notupdatable","lastinstall":"2020-07-20T13:03:26"},"type":"Color temperature light","name":"lesljós","modelid":"TRADFRI bulb E14 WS opal 400lm","manufacturername":"IKEA of Sweden","productname":"Color temperature light","capabilities":{"certified":false,"control":{"ct":{"min":250,"max":454}},"streaming":{"renderer":false,"proxy":false}},"config":{"archetype":"classicbulb","function":"functional","direction":"omnidirectional"},"uniqueid":"90:fd:9f:ff:fe:93:be:a1-01","swversion":"1.2.217"}}'
// const GROUPS_EX = '{"1":{"name":"eldhús","lights":["1"],"sensors":[],"type":"Room","state":{"all_on":true,"any_on":true},"recycle":false,"class":"Living room","action":{"on":true,"bri":100,"hue":6140,"sat":232,"effect":"none","xy":[0.5503,0.4000],"ct":500,"alert":"select","colormode":"xy"}},"2":{"name":"Hús","lights":["3","2","1"],"sensors":[],"type":"Zone","state":{"all_on":true,"any_on":true},"recycle":false,"class":"Downstairs","action":{"on":true,"bri":100,"hue":6140,"sat":232,"effect":"none","xy":[0.5503,0.4000],"ct":500,"alert":"select","colormode":"xy"}},"3":{"name":"skrifstofa","lights":["2","3"],"sensors":[],"type":"Room","state":{"all_on":true,"any_on":true},"recycle":false,"class":"Living room","action":{"on":true,"bri":105,"ct":454,"alert":"select","colormode":"ct"}}}'
var output = undefined;

async function getIdObject(query) {
    let allLights = getAllLights();
    let allGroups = getAllGroups();
    
    for (let light in allLights) {
        if (allLights[light].name === query) {
            let return_object = {id: light, type: "light", url: `lights/${light}/state`};
            return return_object;
        }
    }
    for (let group in allGroups) {
        if (allGroups[group].name === query) {
            let return_object = {id: group, type: "group", url: `groups/${group}/action`};
            return return_object;
        }
    }
    //vantar e.k. error
    return;
}


async function getSceneID(scene_name){
    let allScenes = await getAllScenes();
    for (let scene in allScenes) {
        if (allScenes[scene].name === scene_name) {
            console.log("matching scene id: " + scene);
            return scene;
        }
    }
}


async function setLights(query, state){
    let idObject = await getIdObject(query);
    let ID = idObject.id;
    let parsed_state = JSON.parse(state);

    // Check if state includes a scene or a brightness change
    if (parsed_state.scene) {
        parsed_state.scene = await getSceneID(parsed_state.scene);
        state = JSON.stringify(parsed_state);
    }
    else if (parsed_state.bri_inc) {
        console.log(parsed_state.bri_inc);
        state = JSON.stringify(parsed_state);
    }
    // Send data to API
    let url = idObject.url;
    console.log(state);
    fetch(`http://${BRIDGE_IP}/api/${USERNAME}/${url}`, {
        method: "PUT",
        body: state,
    })
        .then((resp) => resp.json())
        .then((obj) => {
            console.log(obj);
            output = "Aðgerð tókst. " + query + state
            fetch(`http://192.168.1.243:31337/?q=outputDefinedINSuccess`)
            if (!("error" in obj)) {
                console.log("philips didn't understand")
            }
        })
        .catch((err) => {
            console.log("an error occurred!");
            output = "Aðgerð mistókst. " + query + state
            fetch(`http://192.168.1.243:31337/?q=outputDefinedInError`)
        });
}


function setLightsFromHTML() {
    let query = document.getElementById("queryInput").value;
    let stateObject = new Object();
    stateObject.bri_inc = Number(document.getElementById("brightnessInput").value);
    stateObject = JSON.stringify(stateObject);
    console.log(stateObject);
    setLights(query, stateObject);
}

function syncSetLights(query, state) {
    setLights(query, state);
    fetch(`http://192.168.1.243:31337/?q=syncSetLightsAccessed`)
    // while (output === undefined) {}
    fetch(`http://192.168.1.243:31337/?q=whileLoopExited`)
    return query + "\n" + state
}