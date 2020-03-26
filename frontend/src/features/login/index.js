import React, { useState, useEffect }  from 'react';
import { useDispatch } from 'react-redux';
import { login, logout } from 'features/login/loginSlice';
import { loginUser } from 'api/index';
import './index.css';
import 'App.css';


function Login() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");

    const dispatch = useDispatch();
    const apiLogin = (email, password) => {
        loginUser(email, password).then(
            () => (
                dispatch(login(email))
            )
        ).catch((error) => {
            setError("Incorrect email or password.");
        });
    }

    const submit = (e) => {
        e.preventDefault();
        apiLogin(email, password);
    }

    return(
        <div className="App-content">
            <div className="Login">
                <form className="Login-content" onSubmit={submit}>
                    {error && <div className="Message-error">{error}</div>}
                    <div className="InputRow">
                        <label for="email">Email</label>
                        <input name="email" type="text" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)}></input>
                    </div>
                    <div className="InputRow">
                        <label for="password">Password</label>
                        <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)}></input>
                    </div>
                    <button type="submit">Login</button>
                </form>
            </div>
        </div>
    )
}

export default Login;