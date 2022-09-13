"use strict";

/* 
Fuzzy search function that returns an object in the form of {result: (Object), score: (Number)} 
* @param {String} query - The search term
* @param {Object} data - The data to search
*/
function philipsFuzzySearch(query, data) {
    // Restructure data to be searchable by name
    let newData = Object.keys(data).map(function (key) {
        return { ID: key, info: data[key] };
    });
    // Fuzzy search for the query term (returns an array of objects)
    var fuse = new Fuse(newData, {
        keys: ["info", "info.name"],
        includeScore: true,
        shouldSort: true,
        threshold: 0.5,
    });
    let searchResult = fuse.search(query);

    let resultObject = {};
    if (searchResult[0] === undefined) {
        return null;
    }
    // Structure the return object to be in the form of {result: (Object), score: (Number)}
    resultObject.result = searchResult[0].item;
    resultObject.score = searchResult[0].score;

    return resultObject;
}
