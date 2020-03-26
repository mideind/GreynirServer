import { configureStore, createSlice, getDefaultMiddleware } from '@reduxjs/toolkit'

// We'll use redux-logger just as an example of adding another middleware
import logger from 'redux-logger'

import { loginReducer } from 'features/login/loginSlice';

const reducer = {
  login: loginReducer
}

const middleware = [...getDefaultMiddleware(), logger]

export const store = configureStore({
  reducer,
  middleware,
  devTools: process.env.NODE_ENV !== 'production'
});