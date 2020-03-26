import React, {useState, useEffect} from 'react';

import {getTranslations} from 'api';

function Home() {
    const [transl, setTransl] = useState([]);

    useEffect(() => {
        getTranslations().then((r) => {
            setTransl(r.data)
         });
    }, []);

    return(
        <div className="Home">
            <h3>Translations</h3>
            {transl.map((t) => 
                <div>
                    {t.model} - {t.source_text} - {t.target_text}
                </div>
            )}
        </div>
    )
}

export default Home;