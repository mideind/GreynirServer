import { decodeHTML } from '../../utils/text.js';

async function translate(engine, text, source, target, transfTransl) {
  let data = {
    ...engine.extraData,
    model: engine.extraData !== undefined && engine.extraData.model !== undefined ? engine.extraData.model : `${source}-${target}`,
    contents: text.split('\n\n'),
    sourceLanguageCode: source,
    targetLanguageCode: target,
  };
  if (engine.name !== 'Moses') {
    data.contents_tgt = Array.isArray(transfTransl) ? transfTransl : transfTransl.split('\n\n');
  }

  let url = engine.url;
  let param = {
    method: 'POST',
    crossDomain: true,
    mode: 'cors',
    ...engine.extraParam,
    headers: {
      'Content-Type': 'application/json; utf-8',
      ...engine.extraHeader
    },
  }
  param.body = JSON.stringify(data)

  if (source === target) {
    return text;
  }

  let transl;
  const response = await fetch(url, param).catch((e) => console.log(e));
  if (response !== undefined) {
    try {
      transl = await response.json()
      return transl.translations.map(trans => {
        if (engine.name !== 'Transformer') {
          return decodeHTML(trans.translatedText)
        } else {
          return transfTransl + " " + decodeHTML(trans.translatedText)
        }
      });
    } catch (err) {
      return ["Error"];
    }
  } else {
    return ["Error"];
  }
}


//const URL = "https://velthyding.mideind.is:8000/api/translations/usertranslations/";
const URL = "http://localhost:8000/api/translations/usertranslations/";
export async function storeTranslation(language_pair, model, source, target) {
  const data = {
    language_pair: language_pair,
    model: model,
    source_text: source,
    target_text: target
  }
  const param = {
    method: "POST",
    crossDomain: true,
    mode: 'cors',
    headers: {
      'Content-Type': 'application/json; utf-8'
    }
  }
  param.body = JSON.stringify(data)
  return await fetch(URL, param).catch((e) => console.log(e));
}


export async function translateMany(engines, text, source, target, transl) {
  const translations = await engines.map((engine) => translate(engine, text, source, target, transl));
  return Promise.all(translations).then((ts) => ts.map((p, i) => ({ text: p, engine: engines[i] })));
}