import _ from 'lodash';
import {Form} from 'reactjs-components';
import mixin from 'reactjs-mixin';
/* eslint-disable no-unused-vars */
import React from 'react';
/* eslint-enable no-unused-vars */
import {StoreMixin} from 'mesosphere-shared-reactjs';

import Config from '../config/Config';
import ConfigActions from '../events/ConfigActions';
import FormLabel from '../components/FormLabel';
import FormLabelContent from '../components/FormLabelContent';
import Page from '../components/Page';
import PageContent from '../components/PageContent';
import PageSection from '../components/PageSection';
import PasswordStrengthMeter from '../components/PasswordStrengthMeter';
import PreFlightStore from '../stores/PreFlightStore';
import SectionAction from '../components/SectionAction';
import SectionBody from '../components/SectionBody';
import SectionHeader from '../components/SectionHeader';
import SectionHeaderPrimary from '../components/SectionHeaderPrimary';
import SectionHeaderPrimarySubheading from '../components/SectionHeaderPrimarySubheading';
import SectionFooter from '../components/SectionFooter';
import SetupStore from '../stores/SetupStore';
import Tooltip from '../components/Tooltip';
import Upload from '../components/Upload';

const METHODS_TO_BIND = [
  'getCurrentConfig',
  'getErrors',
  'getValidationFn',
  'handleFormChange',
  'handleSubmitClick',
  'handleUploadSuccess',
  'isLastFormField',
  'prepareDataForAPI',
  'submitFormData'
];

const REQUIRED_FORM_DATA = [
  'master_list',
  'agent_list',
  'ip_detect_script',
  'ssh_user',
  'ssh_port',
  'ssh_key',
  'username',
  'password',
  'zk_exhibitor_hosts',
  'zk_exhibitor_port',
  'zk_exhibitor_port'
];

module.exports = class Setup extends mixin(StoreMixin) {
  constructor() {
    super();

    this.state = {
      formData: {
        master_list: null,
        agent_list: null,
        ip_detect_script: null,
        ssh_user: null,
        ssh_port: null,
        ssh_key: null,
        username: null,
        password: '',
        zk_exhibitor_hosts: null,
        zk_exhibitor_port: null,
        zk_exhibitor_port: null
      },
      passwordFieldType: 'password'
    };

    this.store_listeners = [
      {
        name: 'setup',
        events: [
          'configFormCompletionChange',
          'configStatusChangeError',
          'configStatusChangeSuccess',
          'configUpdateError',
          'configUpdateSuccess',
          'currentConfigChangeSuccess'
        ]
      },
      {
        name: 'preFlight',
        events: ['beginSuccess', 'beginError']
      }
    ];

    METHODS_TO_BIND.forEach((method) => {
      this[method] = this[method].bind(this);
    });
  }

  componentWillMount() {
    this.getCurrentConfig();

    this.submitFormData = _.throttle(
      this.submitFormData, Config.apiRequestThrottle
    );
  }

  onSetupStoreConfigStatusChangeError() {
    // Show errors with current stored config.
  }

  onSetupStoreCurrentConfigChangeSuccess() {
    this.getCurrentConfig();
  }

  onPreFlightStoreBeginSuccess() {
    this.props.history.pushState(null, '/pre-flight');
  }

  onPreFlightStoreBeginError(data) {
    return data;
    // Handle pre-flight error.
  }

  getArrayFromHostsString(string) {
    if (string === '' || string == null) {
      return string;
    }

    return string.replace(/\s/g, '').split(',');
  }

  getStringFromHostsArray(array) {
    return array.join(', ');
  }

  // Deconstruct this on load as well.
  getCombinedZKHosts(hosts, port) {
    // Remove all whitespace, split into array, create new array in format of
    // host:port, and convert back to string.
    return this.getArrayFromHostsString(hosts).map(function (host) {
      return `${host}:${port}`;
    }).join(', ');
  }

  getCurrentConfig() {
    let mergedData = this.getNewFormData(SetupStore.get('currentConfig'));
    let displayedConfig = {};

    Object.keys(mergedData).forEach((key) => {
      if (_.isArray(mergedData[key])) {
        displayedConfig[key] = this.getStringFromHostsArray(mergedData[key]);
      } else if (_.isNumber(mergedData[key])) {
        displayedConfig[key] = mergedData[key].toString();
      } else {
        displayedConfig[key] = mergedData[key];
      }

      if (key === 'exhibitor_zk_hosts') {
        let {zkExhibitorHosts, zkExhibitorPort} =
          this.getSeparatedZKHostData(mergedData[key]);

        displayedConfig.zk_exhibitor_hosts = zkExhibitorHosts;
        displayedConfig.zk_exhibitor_port = zkExhibitorPort;
      }
    });

    this.setState({formData: displayedConfig});
  }

  getErrors(key) {
    let error = null;
    let errors = SetupStore.get('errors');

    if (errors[key]) {
      error = errors[key];
    }

    return error;
  }

  getFormDefinition() {
    return [
      [
        {
          fieldType: 'textarea',
          name: 'master_list',
          placeholder: 'Please provide a comma-separated list of 1, 3, or 5 ' +
            'IPv4 addresses.',
          showLabel: (
            <FormLabel>
              <FormLabelContent position="left">
                Master IP Address List
                <Tooltip content={'You can choose any target hosts as ' +
                  'masters and agents. We recommend 3 masters for production ' +
                  'environments, though 1 master is suitable for POC ' +
                  'applications.'} width={200} wrapText={true} />
              </FormLabelContent>
              <FormLabelContent position="right">
                <Upload displayText="Upload .csv"
                  onUploadFinish={this.handleUploadSuccess('master_list')} />
              </FormLabelContent>
            </FormLabel>
          ),
          showError: this.getErrors('master_list'),
          validationErrorText: this.getErrors('master_list'),
          validation: this.getErrors('master_list'),
          value: this.state.formData.master_list
        },
        {
          fieldType: 'textarea',
          name: 'agent_list',
          placeholder: 'Please provide a comma-separated list of 1 to n ' +
            'IPv4 addresses.',
          showLabel: (
            <FormLabel>
              <FormLabelContent>
                Agent IP Address List
                <Tooltip content={'You can choose any target hosts as agents.'}
                  width={200} wrapText={true} />
              </FormLabelContent>
              <FormLabelContent position="right">
                <Upload displayText="Upload .csv"
                  onUploadFinish={this.handleUploadSuccess('agent_list')} />
              </FormLabelContent>
            </FormLabel>
          ),
          showError: this.getErrors('agent_list'),
          validationErrorText: this.getErrors('agent_list'),
          validation: this.getValidationFn('agent_list'),
          value: this.state.formData.agent_list
        }
      ],
      [
        {
          fieldType: 'text',
          name: 'ssh_user',
          placeholder: 'Examples: root, admin, core',
          showLabel: (
            <FormLabel>
              <FormLabelContent>
                SSH Username
                <Tooltip content={'The SSH username must be the same for all ' +
                  'target hosts. The only unacceptable username is None.'}
                  width={200} wrapText={true} />
              </FormLabelContent>
            </FormLabel>
          ),
          showError: this.getErrors('ssh_user'),
          validationErrorText: this.getErrors('ssh_user'),
          validation: this.getValidationFn('ssh_user'),
          value: this.state.formData.ssh_user
        },
        {
          fieldType: 'text',
          name: 'ssh_port',
          showLabel: (
            <FormLabel>
              <FormLabelContent>
                SSH Listening Port
                <Tooltip content={'The SSH port must be the same on all ' +
                  'target hosts.'} width={200} wrapText={true} />
              </FormLabelContent>
            </FormLabel>
          ),
          showError: this.getErrors('ssh_port'),
          validationErrorText: this.getErrors('ssh_port'),
          validation: this.getValidationFn('ssh_port'),
          value: this.state.formData.ssh_port
        }
      ],
      {
        fieldType: 'textarea',
        name: 'ssh_key',
        showLabel: (
          <FormLabel>
            <FormLabelContent>
              SSH Key
              <Tooltip content={'The SSH key must be the same on all target ' +
                'hosts.'} width={200} wrapText={true} />
            </FormLabelContent>
          </FormLabel>
        ),
        showError: this.getErrors('ssh_key'),
        validationErrorText: this.getErrors('ssh_key'),
        validation: this.getValidationFn('ssh_key'),
        value: this.state.formData.ssh_key
      },
      <SectionHeaderPrimary align="left">
        DCOS Environment Settings
        <SectionHeaderPrimarySubheading>
          Choose a username and password for the DCOS administrator. This user
          will be able to manage and add other users.
        </SectionHeaderPrimarySubheading>
      </SectionHeaderPrimary>,
      [
        {
          fieldType: 'text',
          name: 'username',
          placeholder: 'For example, johnappleseed',
          showLabel: (
            <FormLabel>
              <FormLabelContent>
                Username
                <Tooltip content={'The only unacceptable username is "None".'}
                  width={200} wrapText={true} />
              </FormLabelContent>
            </FormLabel>
          ),
          showError: this.getErrors('username'),
          validationErrorText: this.getErrors('username'),
          validation: this.getValidationFn('username'),
          value: this.state.formData.username
        },
        {
          fieldType: this.state.passwordFieldType,
          name: 'password',
          renderer: (inputField) => {
            return (
              <div className="password-strength-wrapper">
                {inputField}
                <PasswordStrengthMeter password={this.state.formData.password}/>
              </div>
            );
          },
          showLabel: 'Password',
          showError: this.getErrors('password'),
          validationErrorText: this.getErrors('password'),
          validation: this.getValidationFn('password'),
          value: this.state.formData.password
        },
        {
          fieldType: 'checkbox',
          name: 'reveal_password',
          showLabel: <p>&nbsp;</p>,
          value: [
            {
              name: 'reveal_password_checkbox',
              label: 'Reveal Password'
            }
          ]
        }
      ],
      [
        {
          fieldType: 'textarea',
          name: 'zk_exhibitor_hosts',
          placeholder: 'Please provide an IPv4 address or a comma-separated ' +
            'list of 3 addresses.',
          showLabel: (
            <FormLabel>
              <FormLabelContent>
                Bootstrapping Zookeeper IP Address(es)
                <Tooltip content={
                    <span>
                      Exhibitor uses this Zookeeper cluster to orchestrate its
                      configuration and to recover the master hosts if they
                      fail. The Zookeeper cluster should be separate from your
                      target cluster to enable disaster recovery. If HA is
                      critical, specify three hosts. <a
                        href="http://zookeeper.apache.org/doc/r3.1.2/zookeeperAdmin.html"
                        target="_blank">
                      Learn more about Zookeeper</a>.
                    </span>
                  }
                  width={300} wrapText={true} />
              </FormLabelContent>
            </FormLabel>
          ),
          showError: this.getErrors('zk_exhibitor_hosts'),
          validationErrorText: this.getErrors('zk_exhibitor_hosts'),
          validation: this.getValidationFn('zk_exhibitor_hosts'),
          value: this.state.formData.zk_exhibitor_hosts
        },
        {
          fieldType: 'text',
          name: 'zk_exhibitor_port',
          showLabel: (
            <FormLabel>
              <FormLabelContent>
                Bootstrapping Zookeeper Port
                <Tooltip content={'We recommend leaving this set to the ' +
                  'default port, 2181.'} width={200} wrapText={true} />
              </FormLabelContent>
            </FormLabel>
          ),
          showError: this.getErrors('zk_exhibitor_port'),
          validation: this.getValidationFn('zk_exhibitor_port'),
          validationErrorText: this.getErrors('zk_exhibitor_port'),
          value: this.state.formData.zk_exhibitor_port
        }
      ],
      [
        {
          fieldType: 'textarea',
          name: 'resolvers',
          placeholder: 'Please provide a single address or a comma-separated ' +
            'list, e.g., 192.168.10.10, 10.0.0.1',
          showLabel: (
            <FormLabel>
              <FormLabelContent>
                Upstream DNS Servers
                <Tooltip content={
                    <span>
                      These can be DNS servers on your private network or on the
                      public internet, depending on your needs. Caution: If you set
                      this parameter incorrectly, you will have to reinstall
                      DCOS. <a
                        href="https://docs.mesosphere.com/administration/service-discovery/"
                        target="_blank">
                        Learn more about DNS and DCOS
                      </a>.
                    </span>
                  }
                  width={300} wrapText={true} />
              </FormLabelContent>
            </FormLabel>
          ),
          showError: this.getErrors('resolvers'),
          validation: this.getValidationFn('resolvers'),
          validationErrorText: this.getErrors('resolvers'),
          value: this.state.formData.resolvers
        },
        {
          fieldType: 'textarea',
          name: 'ip_detect_script',
          placeholder: 'IP Detect Script',
          showLabel: (
            <FormLabel>
              <FormLabelContent>
                IP Detect Script
              </FormLabelContent>
            </FormLabel>
          ),
          showError: this.getErrors('ip_detect_script'),
          validation: this.getValidationFn('ip_detect_script'),
          validationErrorText: this.getErrors('ip_detect_script'),
          value: this.state.formData.ip_detect_script
        }
      ]
    ];
  }

  getNewFormData(newFormData) {
    return _.extend({}, this.state.formData, newFormData);
  }

  getSeparatedZKHostData(hostData) {
    if (hostData == null) {
      return {
        zkExhibitorHosts: null,
        zkExhibitorPort: null
      };
    }

    let hosts = this.getArrayFromHostsString(hostData);
    let port = hosts[0].split(':')[1];

    hosts.forEach(function (host, index) {
      hosts[index] = host.split(':')[0];
    });

    return {
      zkExhibitorHosts: this.getStringFromHostsArray(hosts),
      zkExhibitorPort: port
    };
  }

  getValidationFn(key) {
    return function () {
      let errors = SetupStore.get('errors');

      if (errors[key]) {
        return false;
      }
      return true;
    }
  }

  handleFormChange(formData, eventDetails) {
    let {eventType, fieldName, fieldValue} = eventDetails;

    if (eventType === 'focus') {
      return;
    }

    if (eventType === 'blur'
      || (eventType === 'change' && this.isLastFormField(fieldName))) {
      this.submitFormData({[fieldName]: fieldValue});
    }

    if (eventType === 'blur') {
      // Submit form data immediately on blur events.
      this.submitFormData.flush();
    }

    if (eventType === 'multipleChange' && fieldName === 'reveal_password') {
      let passwordFieldType = this.state.passwordFieldType;
      if (fieldValue[0].checked) {
        passwordFieldType = 'text';
      } else {
        passwordFieldType = 'password';
      }

      this.setState({passwordFieldType});
    }

    let newFormData = this.getNewFormData({[fieldName]: fieldValue});

    this.setState({formData: newFormData});
  }

  handleUploadSuccess(destination) {
    return (fileContents) => {
      let formData = this.getNewFormData({
        [destination]: fileContents
      });

      this.setState({formData});
    }
  }

  handleSubmitClick() {
    // Do submit click stuff here
  }

  beginPreFlight() {
    PreFlightStore.beginStage();
  }

  isLastFormField(fieldName) {
    let errors = SetupStore.get('errors');
    let lastRemainingField = true;

    REQUIRED_FORM_DATA.forEach((key) => {
      if (key !== fieldName && (this.state.formData[key] === ''
        || this.state.formData[key] == null)) {
        lastRemainingField = false;
      }
    });

    // If errors exist, we don't want to send the form data on value change.
    if (lastRemainingField && Object.keys(errors).length) {
      lastRemainingField = false;
    }

    return lastRemainingField;
  }

  submitFormData(formData) {
    let preparedData = this.prepareDataForAPI(formData);

    if (preparedData) {
      ConfigActions.updateConfig(preparedData);
    }
  }

  prepareDataForAPI(data) {
    let preparedData = {};

    Object.keys(data).forEach((key) => {
      // For zk_exhibitor_hosts and zk_exhibitor_port, we need to send a
      // string with comma-separated host:port values.
      // For master_list and agent_list, we need to send an array of the IPs.
      // Everything else can be sent as entered by the user.
      if (key === 'zk_exhibitor_hosts') {
        if (this.state.formData.zk_exhibitor_hosts != null) {
          preparedData.exhibitor_zk_hosts = this.getCombinedZKHosts(
            data[key], this.state.formData.zk_exhibitor_port
          );
        }
      } else if (key === 'zk_exhibitor_port') {
        if (this.state.formData.zk_exhibitor_hosts != null) {
          preparedData.exhibitor_zk_hosts = this.getCombinedZKHosts(
            this.state.formData.zk_exhibitor_hosts, data[key]
          );
        }
      } else if (key === 'master_list' || key === 'agent_list'
        || key === 'resolvers') {
        preparedData[key] = this.getArrayFromHostsString(data[key]);
      } else if (key === 'ssh_port') {
        preparedData[key] = parseInt(data[key]);
      } else {
        preparedData[key] = data[key];
      }
    });

    return preparedData;
  }

  render() {
    return (
      <Page hasNavigationBar={true} size="large" pageName="setup">
        <PageContent>
          <PageSection>
            <SectionHeader>
              <SectionHeaderPrimary align="left">
                Deployment Settings
                <SectionHeaderPrimarySubheading>
                  Enter the IP addresses of your target hosts and their SSH
                  settings.
                </SectionHeaderPrimarySubheading>
              </SectionHeaderPrimary>
            </SectionHeader>
            <SectionBody>
              <Form definition={this.getFormDefinition()}
                onChange={this.handleFormChange} />
            </SectionBody>
          </PageSection>
          <PageSection>
            <SectionFooter>
              <SectionAction enabled={SetupStore.get('completed')} linkTo="/pre-flight"
                onClick={this.handleSubmitClick} type="primary">
                Run Pre-Flight
              </SectionAction>
            </SectionFooter>
          </PageSection>
        </PageContent>
      </Page>
    );
  }
}
