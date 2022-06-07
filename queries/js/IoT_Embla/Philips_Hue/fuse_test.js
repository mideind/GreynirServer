// 1. List of items to search in

const books = [
    {
      title: "Old Man's War",
      author: {
        firstName: 'John',
        lastName: 'Scalzi'
      }
    },
    {
      title: 'The Lock Artist',
      author: {
        firstName: 'Steve',
        lastName: 'Hamilton'
      }
    }
  ]

  const lights = [
      // const LIGHTS_EX = 
      { test:
      { state:{"on":true,"bri":100,"hue":6140,"sat":232,"effect":"none","xy":[0.5503,0.4000],"ct":500,"alert":"select","colormode":"xy","mode":"homeautomation","reachable":true},
      "swupdate":{"state":"noupdates","lastinstall":"2022-05-27T14:23:54"},"type":"Extended color light",
      name:"litaljós","modelid":"LCA001","manufacturername":"Signify Netherlands B.V.","productname":"Hue color lamp","capabilities":{"certified":true,"control":{"mindimlevel":200,"maxlumen":800,"colorgamuttype":"C","colorgamut":[[0.6915,0.3083],[0.1700,0.7000],[0.1532,0.0475]],"ct":{"min":153,"max":500}},"streaming":{"renderer":true,"proxy":true}},"config":{"archetype":"sultanbulb","function":"mixed","direction":"omnidirectional","startup":{"mode":"safety","configured":true}},"uniqueid":"00:17:88:01:06:79:c3:94-0b","swversion":"1.93.7","swconfigid":"3C05E7B6","productid":"Philips-LCA001-5-A19ECLv6"},
      "2":
      {"state":{"on":true,"bri":2,"ct":454,"alert":"select","colormode":"ct","mode":"homeautomation","reachable":false},
      "swupdate":{"state":"notupdatable","lastinstall":"2020-06-29T12:05:21"},"type":"Color temperature light",
      "name":"Ikea pera Uno","modelid":"TRADFRI bulb E27 WS opal 1000lm","manufacturername":"IKEA of Sweden","productname":"Color temperature light","capabilities":{"certified":false,"control":{"ct":{"min":250,"max":454}},"streaming":{"renderer":false,"proxy":false}},"config":{"archetype":"classicbulb","function":"functional","direction":"omnidirectional"},"uniqueid":"cc:cc:cc:ff:fe:02:92:52-01","swversion":"2.0.023"},
      "3":
      {"state":{"on":true,"bri":105,"ct":454,"alert":"select","colormode":"ct","mode":"homeautomation","reachable":false},
      "swupdate":{"state":"notupdatable","lastinstall":"2020-07-20T13:03:26"},"type":"Color temperature light",
      "name":"lesljós","modelid":"TRADFRI bulb E14 WS opal 400lm","manufacturername":"IKEA of Sweden","productname":"Color temperature light","capabilities":{"certified":false,"control":{"ct":{"min":250,"max":454}},"streaming":{"renderer":false,"proxy":false}},"config":{"archetype":"classicbulb","function":"functional","direction":"omnidirectional"},"uniqueid":"90:fd:9f:ff:fe:93:be:a1-01","swversion":"1.2.217"}}
  ]
  
//   2. Set up the Fuse instance
  const fuse = new Fuse(books, {
    keys: ['title']
  })

  const fuseLights = new Fuse(lights, {
    keys: ['test.name']
  })
  
  // 3. Now search!
  console.log(fuse.search('steve'))
//   console.log(fuseLights.search('lita'))
  
  // Output:
  // [
  //   {
  //     item: {
  //       title: "Old Man's War",
  //       author: {
  //         firstName: 'John',
  //         lastName: 'Scalzi'
  //       }
  //     },
  //     refIndex: 0
  //   }
  // ]