import React, { useState, useEffect } from 'react';
import ClipLoader from "react-spinners/ClipLoader";

import 'App.css';
import Translator from 'components/Translator';

import { ENGINES } from 'config/engines.js';

import { translateMany } from 'actions/translations/translate.js';

import {storeTranslation} from 'api'

function Translate() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [trans, setTrans] = useState([]);
  const [selectedEngines, setEngines] = useState({ 0: true, 1: false, 2: false, 3: false })
  const [source, setSource] = useState('is');
  const [target, setTarget] = useState('en');

  // Split up to enable propagation to trigger rendering
  const [transformerT, setTransformer] = useState("");
  const [bilstmT, setBiLSTM] = useState("");
  const [mosesT, setMoses] = useState("");
  const [googleT, setGoogle] = useState("");

  // Refactor when more languages on offer
  useEffect(() => {
    if (target === source) {
      if (source === 'is') {
        setSource('en');
      } else {
        setSource('is')
      }
    }
  }, [target]);

  useEffect(() => {
    if (target === source) {
      if (target === 'is') {
        setTarget('en');
      } else {
        setTarget('is')
      }
    }
  }, [source]);

  return (
    <div>
        {loading && <div className="Translate-loader"> <ClipLoader size={10} /></div>}
        <Translator
          sourceText={text}
          targetText={trans}
          setText={setText}
          setTargetText={setTrans}
          setSource={setSource}
          setTarget={setTarget}
          source={source}
          target={target}
          transformerT={transformerT}
          bilstmT={bilstmT}
          mosesT={mosesT}
          googleT={googleT}
          setTransformer={setTransformer}
          setBiLSTM={setBiLSTM}
          setMoses={setMoses}
          setGoogle={setGoogle}
        />
        <div className="Translate">
          <div className="Translate-footer">
            <div className="Translate-engines">
              {ENGINES.map((engine, idx) => (
                <div className="Checkbox" key={'cb-' + idx}>
                  <label>
                    <input
                      type="checkbox"
                      checked={selectedEngines[idx]}
                      onChange={() => setEngines({ ...selectedEngines, [idx]: !selectedEngines[idx] })} />
                    {engine.name} - {engine.url}
                  </label>
                </div>
              ))}
            </div>
            <button
              className="Button TranslateBox-submit"
              onClick={async () => {
                setLoading(true);
                const trans = await translateMany(
                  ENGINES.filter((engine, idx) => selectedEngines[idx]),
                  text,
                  source,
                  target,
                  transformerT
                );
                trans.map((t) => {
                  switch (t.engine.name) {
                    case 'Transformer':
                      setTransformer(t.text);
                      break;
                    case 'Moses':
                      setMoses(t.text);
                      break;
                    case 'Bi-LSTM':
                      setBiLSTM(t.text);
                      break;
                    default:
                      setGoogle(t.text);
                      break;
                  }
                })
                setTrans(trans);
                trans.map((t) => {
                  storeTranslation(`${source}-${target}`, t.engine.name, text, t.text.join("\n\n"))
                });
                setLoading(trans === [])
              }}>
              Translate
            </button>
          </div>
        </div>
      </div>
  );
}

export default Translate;
