const increment = createAction('INCREMENT')
const decrement = createAction('DECREMENT')

const counter = createReducer(0, {
  [increment]: state => state + 1,
  [decrement]: state => state - 1
})

const store = configureStore({
  reducer: counter
})