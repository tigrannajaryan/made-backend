import { Injectable } from '@angular/core';
import { StoreService } from './store';

/**
 * StoreServiceHelper working with StoreService data
 * and returns an updated data back
 */
@Injectable()
export class StoreServiceHelper {
  constructor(private store: StoreService) {}

  update(prop, state): void {
    const currentState = this.store.getState();
    const stateObj = { [prop]: state };
    this.store.setState({...currentState, ...stateObj});
  }

  add(prop, state): void {
    const currentState = this.store.getState();
    const collection = currentState[prop];
    const stateObj = { [prop]: [state, ...collection] };
    this.store.setState({...currentState, ...stateObj});
  }

  findAndUpdate(prop, state): void {
    const currentState = this.store.getState();
    const collection = currentState[prop];
    const stateObj = {[prop]: collection.map(item => {
        if (item.id !== state.id) {
          return item;
        }

        return {...item, ...state};
      })};

    this.store.setState({...currentState, ...stateObj});
  }

  findAndDelete(prop, id): void {
    const currentState = this.store.getState();
    const collection = currentState[prop];
    const stateObj = {[prop]: collection.filter(item => item.id !== id)};
    this.store.setState({...currentState, ...stateObj});
  }
}
