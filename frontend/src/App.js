import React, {useState} from 'react';
import ClipLoader from "react-spinners/ClipLoader";

import './App.css';
import logo from './velthyding.svg';
import mideindLogo from './mideind.svg';


//const baseDevURL = "velthyding.mideind.is";
const baseDevURL = "192.168.1.76:5050";

const ENGINES = [
  {
    url: `http://${baseDevURL}/nn/translate.api`,
    name: "Greynir Transformer",
    extraData: {
      model: "transformer"
    }
  },
  {
    url: `http://${baseDevURL}/nn/translate.api`,
    name: "Greynir Bi-LSTM",
    extraData: {
      model: "bilstm"
    }
  },
  {
    url: "http://nlp.cs.ru.is/moses/translateText",
    name: "Moses",
    extraData: {
      model: "moses"
    }
  },
  {
    url: `http://${baseDevURL}/nn/googletranslate.api`,
    name: "Google v2",
  }
]

const LANGUAGE_PAIRS = [
  ['is', 'en'],
  ['en', 'is']
]

const decode = str => {
  return str.replace(/&#(\d+);/g, function(match, dec) {
    return String.fromCharCode(dec);
  });
}

async function translate(engine, text, source, target) {
  const data = {
    ...engine.extraData,
    model: engine.extraData !== undefined && engine.extraData.model !== undefined ? engine.extraData.model : `${source}-${target}`,
    contents: text.split('\n\n'),
    sourceLanguageCode: source,
    targetLanguageCode: target,
  };
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
      return transl.translations.map(trans => decode(trans.translatedText));
    } catch(err) {
      return ["Error"];
    }
  } else {
    return ["Error"];
  }
}

async function translateMany(engines, text, source, target){
  const translations = await engines.map((engine) => translate(engine, text, source, target));
  return Promise.all(translations).then( (ts) => ts.map((p, i) => ({text: p, engine: engines[i]})));
}

function App() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [trans, setTrans] = useState([]);
  const [selectedEngines, setEngines] = useState({0: true, 1: true, 2: true, 3: true})
  const [source, setSource] = useState('is');
  const [target, setTarget] = useState('en');

  return (
    <div className="App">
      <header className="App-header">
        <div className="App-content">
          <img src={logo} height="200" width="200"/>
        </div>
      </header>
      <div className="App-body">
        <div className="Translate">
          <div className="Translate-main">
            <div className="TranslateBox">
              <div className="TranslateBox-header">Source</div>
              <textarea className="TranslateBox-area" value={text} onChange={(e) => setText(e.target.value)}></textarea>
            </div>
            <div className="TranslateBox">
              <div className="TranslateBox-header">Translation {loading && <ClipLoader size={10} /> } </div>
              <div className="TranslateBox-container">
                {trans.length === 0 && <div className="TranslateBox-area-trans">Press translate to translate</div>}
                {trans.map((t, i) =>
                    <div className="TranslateBox-area-blurb" key={"trans-" + i}>
                      <div className="TranslateBox-area-blurb-header">{t.engine.name}</div>
                      <div className="TranslateBox-area-trans">
                          {t.text.map(s => <div className="TranslateBox-area-trans-sent">{s}</div>)}
                        </div>
                      </div>
                    )}
                </div>
            </div>
          </div>
          <div className="Translate-footer">
            <div className="Translate-engines">
              {ENGINES.map( (engine, idx) => (
                <div className="Checkbox" key={'cb-' + idx}>
                  <label>
                    <input
                      type="checkbox"
                      checked={selectedEngines[idx]}
                      onChange={() => setEngines({ ...selectedEngines, [idx]: !selectedEngines[idx] })}/>
                    {engine.name} - {engine.url}
                  </label>
                </div>
              ))}
              <div className="PairPicker">
                <div className="PairPicker-source">
                  <div className="PairPicker-label">Source</div>
                  <select id="PairPicker-source" value={source} onChange={(e) => setSource(e.target.value)}>
                    {LANGUAGE_PAIRS.map((pair, i) =>  <option key={"source-" + i} value={pair[0]}>{pair[0]}</option>)}
                  </select>
                </div>
                <div className="PairPicer-target">
                <div className="PairPicker-label">Target</div>
                  <select id="PairPicker-target" value={target} onChange={(e) => setTarget(e.target.value)}>
                    {LANGUAGE_PAIRS.map((pair, i) =>  <option key={"target-" + i} value={pair[1]}>{pair[1]}</option>)}
                  </select>
                </div>
              </div>
            </div>
            <button
              className="Button TranslateBox-submit"
              onClick={async () => {
                setLoading(true);
                const trans = await translateMany(
                  ENGINES.filter((engine, idx) => selectedEngines[idx]),
                  text,
                  source,
                  target
                );
                setTrans(trans);
                setLoading(trans === [])
                }}>
                Translate
            </button> 
          </div>
        </div>
      </div>
      <div className="Footer">
          <div className="Footer-logo">
            <a href="https://mideind.is"><img src={mideindLogo} width="67" height="76" /></a>
            <p>Miðeind ehf., kt. 591213-1480</p>
            <p>Fiskislóð 31, rými B/304, 101 Reykjavík, <a href="mailto:mideind@mideind.is">mideind@mideind.is</a></p>
          </div>
      </div>
    </div>
  );
}

export default App;
