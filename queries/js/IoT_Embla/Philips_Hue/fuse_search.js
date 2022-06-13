function philipsFuzzySearch(query, data) {
    var newData = Object.keys(data).map(function (key) {
        return { ID: key, info: data[key] };
    });
    var fuse = new Fuse(newData, {
        keys: ["info", "info.name"],
        shouldSort: true,
        threshold: 0.5,
    });

    let searchTerm = query;
    let result = fuse.search(searchTerm);

    console.log("result: ", result);
    if (result[0] === undefined) {
        console.log("no match found");
        return null;
    } else {
        return result[0].item;
    }
}
