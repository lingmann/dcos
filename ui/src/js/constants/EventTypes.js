let EventTypes = {};
[
  'CONFIGURE_CHANGE_ERROR',
  'CONFIGURE_CHANGE_SUCCESS',
  'CONFIGURE_STATUS_CHANGE_ERROR',
  'CONFIGURE_STATUS_CHANGE_SUCCESS',
  'CONFIGURE_TYPE_CHANGE_ERROR',
  'CONFIGURE_TYPE_CHANGE_SUCCESS',
  'CONFIGURE_UPDATE_ERROR',
  'CONFIGURE_UPDATE_SUCCESS',
  'CURRENT_STAGE_CHANGE',
  'DEPLOY_BEGIN_SUCCESS',
  'DEPLOY_BEGIN_ERROR',
  'DEPLOY_STATE_CHANGE',
  'GLOBAL_INSTALL_IN_PROGRESS_CHANGE',
  'GLOBAL_NEXT_STEP_CHANGE',
  'PREFLIGHT_STATE_CHANGE',
  'PREFLIGHT_BEGIN_SUCCESS',
  'PREFLIGHT_BEGIN_ERROR',
  'POSTFLIGHT_STATE_CHANGE',
  'POSTFLIGHT_BEGIN_SUCCESS',
  'POSTFLIGHT_BEGIN_ERROR',
  'TOTAL_SLAVES_ERROR',
  'TOTAL_SLAVES_SUCCESS',
  'TOTAL_MASTERS_ERROR',
  'TOTAL_MASTERS_SUCCESS',
].forEach(function (eventType) {
  EventTypes[eventType] = eventType;
});

module.exports = EventTypes;
