import {GetSetMixin, Store} from 'mesosphere-shared-reactjs';

import ActionTypes from '../constants/ActionTypes';
import AppDispatcher from '../events/AppDispatcher';
import EventTypes from '../constants/EventTypes';

let PreFlighStore = Store.createStore({
  storeID: 'preFlight',

  mixins: [GetSetMixin],

  init: function () {
    this.set({
      agents: {
        error: false,
        status: 'Checking Agents',
        detail: null
      },
      completed: false,
      masters: {
        error: false,
        status: 'Checking Masters',
        detail: null
      },
      status: 'Running Pre-Flight...'
    });
  },

  addChangeListener: function (eventName, callback) {
    this.on(eventName, callback);
  },

  removeChangeListener: function (eventName, callback) {
    this.removeListener(eventName, callback);
  },

  processUpdateError: function () {
    this.emit(EventTypes.PREFLIGHT_STATE_CHANGE);
  },

  processUpdateSuccess: function () {
    // TODO: Process update for masters and agents.
    this.emit(EventTypes.PREFLIGHT_STATE_CHANGE);
  },

  dispatcherIndex: AppDispatcher.register(function (payload) {
    let {action} = payload;

    switch (action.type) {
      case ActionTypes.PREFLIGHT_UPDATE_ERROR:
        PreFlighStore.processUpdateError(action.data);
        break;
      case ActionTypes.PREFLIGHT_UPDATE_SUCCESS:
        PreFlighStore.processUpdateSuccess(action.data);
        break;
    }

    return true;
  })

});

module.exports = PreFlighStore;
