//const baseURL = "192.168.86.58:5050";
const baseURL = "velthyding.mideind.is";
//const baseURL = "192.168.1.76:5050";
const https = "https";

export const ENGINES = [
  {
    url: `${https}://${baseURL}/nn/translate.api`,
    name: "Transformer",
    extraData: {
      model: "transformer"
    }
  },
  {
    url: `${https}://${baseURL}/nn/translate.api`,
    name: "Bi-LSTM",
    extraData: {
      model: "bilstm"
    }
  },
  {
    url: `${https}://nlp.cs.ru.is/moses/translateText`,
    name: "Moses",
    extraData: {
      model: "moses"
    }
  },
  {
    url: `${https}://${baseURL}/nn/googletranslate.api`,
    name: "Google",
  }
]