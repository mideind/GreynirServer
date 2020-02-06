import React, { useState, useEffect } from 'react';

import './index.css';


function LanguagePicker(props) {
    const [profileState, setProfileState] = useState({setSelected: props.setSelected, selected: props.selected});

    const [open, setOpen] = useState(false);
    const options = [{key: "is", name: "Icelandic"}, {key: "en", name: "English"}];
    const langs = {is: "Icelandic", en: "English"};

    useEffect(() => {
        setProfileState(props);
    }, [props]);

    return (
        <div onClick={() => setOpen(!open)} className="LanguagePicker">
            <div className="LanguagePicker-container">{langs[profileState.selected]} ⋁</div>
            {open &&
            <div className="LanguagePicker-menu">
                {options.map(o => (
                    <div onClick={() => props.setSelected(o.key)} 
                        className="LanguagePicker-menu-item">
                        {o.name}
                    </div>))}
            </div>}
        </div>
    )
}


function TranslatorSide (props) {
    const [profileState, setProfileState] = useState(props);
    let ref;

    useEffect(() => {
        setProfileState(props);
    }, [props]);

    return (
        <div className="TranslatorSide">
            <div className="TranslatorSide-lang">
                Translate {profileState.source ? "from" : "to"} <LanguagePicker
                                                                    selected={profileState.language}
                                                                    setSelected={props.setSelected}/>
            </div>
            <div className="TranslatorSide-container">
                <div className="TranslatorSide-text">
                    {profileState.source && <textarea
                        ref={el => ref=el}
                        height="300"
                        lang={profileState.language}
                        autoFocus={true}
                        tabIndex="110"
                        style={{height: 300}}
                        onChange={(e) => {
                            profileState.setText(e.target.value)
                        }}
                        onClick={(e) => {
                            console.log(ref.selectionStart) // TODO use this to find current word for beam search handling
                        }}
                        value={profileState.text}
                        acceptCharset="utf-8">
                    </textarea>}
                {(!profileState.source && profileState.text.length !== 0) && profileState.text.map(a => 
                        <div className="TranslatorSide-text-wrapper" key={'transKey-'+a.engine.name}>
                            <button className="TranslatorSide-clear"><span>{a.engine.name}</span></button>
                            <textarea
                                height="300"
                                lang={profileState.language}
                                autoFocus=""
                                tabIndex="110"
                                style={{height: 300}}
                                onChange={(e) => console.log(e.target)}
                                defaultValue={a.text}>
                            </textarea>
                        </div>)}
                    {(!profileState.source && profileState.text.length === 0) && <textarea
                        height="300"
                        lang={profileState.language}
                        autoFocus=""
                        tabIndex="110"
                        style={{height: 300}}
                        readOnly={true}>
                    </textarea>}
                </div>
                { profileState.source && <button className="TranslatorSide-clear" onClick={() => props.setText("")}>
                    <span>×</span>
                </button>}
            </div>
        </div>
    )
}


function Translator(props) { 
    return (
        <div className="Translator">
            <div className="Translator-container">
                <TranslatorSide
                    language={props.source}
                    source={true}
                    setText={props.setText}
                    text={props.sourceText}
                    setSelected={props.setSource}/>
                <TranslatorSide
                    language={props.target}
                    source={false}
                    setText={props.setTargetText}
                    text={props.targetText}
                    setSelected={props.setTarget}/>
            </div>    
        </div>
    )
}


export default Translator;