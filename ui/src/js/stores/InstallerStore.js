import {GetSetMixin, Store} from 'mesosphere-shared-reactjs';

import EventTypes from '../constants/EventTypes';

let InstallerStore = Store.createStore({
  storeID: 'installer',

  mixins: [GetSetMixin],

  init: function () {
    this.set({
      currentStage: null,
      dcosURL: null,
      installInProgress: false,
      nextStep: {
        enabled: false,
        label: null,
        link: null,
        visible: false
      }
    });
  },

  addChangeListener: function (eventName, callback) {
    this.on(eventName, callback);
  },

  removeChangeListener: function (eventName, callback) {
    this.removeListener(eventName, callback);
  },

  getCurrentStage: function () {

  },

  setInstallInProgress: function (installInProgress) {
    InstallerStore.set({
      installInProgress: installInProgress
    });
    InstallerStore.emit(EventTypes.GLOBAL_INSTALL_IN_PROGRESS_CHANGE);
  },

  setNextStep: function (stepData) {
    InstallerStore.set({
      enabled: stepData.enabled,
      label: stepData.label,
      link: stepData.link,
      visible: stepData.visible
    });
    InstallerStore.emit(EventTypes.GLOBAL_NEXT_STEP_CHANGE);
  }
});

module.exports = InstallerStore;
