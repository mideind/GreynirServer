import { createSlice } from '@reduxjs/toolkit'


export const loginSlice = createSlice({
    name: 'counter',
    initialState: {
        loggedin: false,
        email: null
    },
    reducers: {
      login: (state, action) => ({email: action.payload, loggedin: true}),
      logout: (state, action) => ({email: action.payload, loggedin: false})
    }
  });
  

export const loginReducer = loginSlice.reducer;
export const {login, logout} = loginSlice.actions;