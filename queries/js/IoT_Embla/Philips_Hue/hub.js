function findHub() {
    fetch(`https://discovery.meethue.com`)
        .then((resp) => resp.json())
        .then((j) => {
            console.log(j);
        })
        .catch((err) => {
            console.log("an error occurred!");
        });
}