import React, { useState, useEffect } from 'react';
import {
  BrowserRouter as Router,
  Switch,
  Route,
  Link,
  Redirect
} from "react-router-dom";

import './App.css';
import logo from './velthyding.svg';
import mideindLogo from './mideind.svg';

import { useDispatch, useSelector } from 'react-redux';

import Translate from 'features/translate';
import Login from 'features/login';
import Home from 'features/home';

import { logout } from 'features/login/loginSlice';

import {logoutUser} from 'api';

function App() {

  const {loggedin, email} = useSelector(state => state.login);
  const dispatch = useDispatch();
  
  return (
    <Router>
      <div className="App">
        <header className="App-header">
          <div className="App-header-content">
            <div>
              <Link to="/">
                <img src={logo} height="50" width="50" />
              </Link>
            </div>
            <div className="App-header-menu">
              {!loggedin && <Link to="/login">Login</Link>}
              {loggedin && <div><Link to="/home">{email}</Link> / <span onClick={logoutUser}>Logout</span> </div> }
            </div>
          </div>
        </header>
        <div className="App-body">
          <Switch>
            <Route path="/login">
              {loggedin ? <Redirect to="/home"/> : <Login /> }
            </Route>
            <Route path="/home">
              {!loggedin ? <Redirect to="/login"/> : <Home /> }
            </Route>
            <Route path="/">
              <Translate />
            </Route>
          </Switch>
        </div>
        <div className="Footer">
          <div className="Footer-logo">
            <a href="https://mideind.is"><img src={mideindLogo} width="67" height="76" /></a>
            <p>Miðeind ehf., kt. 591213-1480</p>
            <p>Fiskislóð 31, rými B/304, 101 Reykjavík, <a href="mailto:mideind@mideind.is">mideind@mideind.is</a></p>
          </div>
        </div>
      </div>
    </Router>
  );
}

export default App;
