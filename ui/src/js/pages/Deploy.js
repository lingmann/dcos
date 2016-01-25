import mixin from 'reactjs-mixin';
import {StoreMixin} from 'mesosphere-shared-reactjs';
/* eslint-disable no-unused-vars */
import React from 'react';
/* eslint-enable no-unused-vars */

import DeployStore from '../stores/DeployStore';
import ErrorLabel from '../components/ErrorLabel';
import IconCircleCheckmark from '../components/icons/IconCircleCheckmark';
import IconSpinner from '../components/icons/IconSpinner';
import IconWarning from '../components/icons/IconWarning';
import InstallerStore from '../stores/InstallerStore';
import Page from '../components/Page';
import PageContent from '../components/PageContent';
import PageSection from '../components/PageSection';
import ProgressBar from '../components/ProgressBar';
import PostFlightStore from '../stores/PostFlightStore';
import SectionBody from '../components/SectionBody';
import SectionHeader from '../components/SectionHeader';
import SectionHeaderIcon from '../components/SectionHeaderIcon';
import SectionHeaderPrimary from '../components/SectionHeaderPrimary';
import SectionHeaderSecondary from '../components/SectionHeaderSecondary';
import SectionFooter from '../components/SectionFooter';
import StageActionButtons from '../components/StageActionButtons';
import StageLinks from '../components/StageLinks';

class Deploy extends mixin(StoreMixin) {
  constructor() {
    super();

    this.store_listeners = [
      {name: 'deploy', events: ['stateChange']},
      {name: 'postFlight', events: ['beginSuccess']}
    ];
  }

  componentWillMount() {
    DeployStore.init();
  }

  componentDidMount() {
    super.componentDidMount();
    InstallerStore.setNextStep({
      enabled: false,
      label: 'Post-Flight',
      link: '/post-flight',
      visible: true
    });
  }

  onPostFlightStoreBeginSuccess() {
    this.context.router.push('/post-flight');
  }

  handleRetryClick() {
    DeployStore.beginStage();
    DeployStore.init.bind(DeployStore)
  }

  getHeaderIcon(completed, failed, totalErrors) {
    if (completed && totalErrors === 0) {
      return <IconCircleCheckmark />;
    }

    if (completed && totalErrors > 0) {
      return <IconWarning />;
    }

    return <IconSpinner />;
  }

  getHeaderContent(completed, failed, totalErrors) {
    if (completed) {
      if (failed) {
        return 'Deploy Failed';
      }

      if (totalErrors > 0) {
        return 'Deploy Completed with Errors';
      }

      return 'Deploy Complete';
    }

    return 'Deploying DCOS...';
  }

  getProgressBarDetail(status, total) {
    if (status.completed) {
      return '';
    }

    let hostCount = status.totalStarted;
    return `Deploying ${hostCount} of ${total}`;
  }

  getProgressBarLabel(type, completed, errors) {
    if (errors > 0 && completed) {
      return `Errors with ${errors} ${type}`;
    }

    if (completed) {
      return `${type} Check Complete`;
    }

    return `Deploying to ${type}`;
  }

  getProgressBar(type, status, totalOfType) {
    let completed = status.completed;
    let progress = ((status.totalStarted / totalOfType) * 100) || 0;
    let state = 'ongoing';

    if (completed && status.errors > 0) {
      state = 'error';
    } else if (completed) {
      state = 'success';
    }

    return (
      <ProgressBar
        detail={this.getProgressBarDetail(status, totalOfType)}
        label={this.getProgressBarLabel(type, status.completed, status.errors)}
        progress={progress} state={state} />
    );
  }

  render() {
    let masterStatus = DeployStore.get('masters');
    let agentStatus = DeployStore.get('agents');

    let completed = masterStatus.completed && agentStatus.completed;
    let failed = masterStatus.errors > 0;
    let totalErrors = masterStatus.errors + agentStatus.errors;
    let totalAgents = agentStatus.totalAgents;
    let totalMasters = masterStatus.totalMasters;

    return (
      <Page hasNavigationBar={true}>
        <PageContent>
          <PageSection>
            <SectionHeader>
              <SectionHeaderIcon>
                {this.getHeaderIcon(completed, failed, totalErrors)}
              </SectionHeaderIcon>
              <SectionHeaderPrimary>
                {this.getHeaderContent(completed, failed, totalErrors)}
              </SectionHeaderPrimary>
              <SectionHeaderSecondary>
                <ErrorLabel step="deploy" />
              </SectionHeaderSecondary>
            </SectionHeader>
            <SectionBody>
              {this.getProgressBar('Masters', masterStatus, totalMasters)}
              {this.getProgressBar('Agents', agentStatus, totalAgents)}
            </SectionBody>
          </PageSection>
          <PageSection>
            <SectionFooter>
              <StageActionButtons
                completed={completed}
                failed={failed}
                nextText="Run Post-Flight"
                onNextClick={PostFlightStore.beginStage.bind(PostFlightStore)}
                onRetryClick={this.handleRetryClick.bind(this)}
                totalErrors={totalErrors} />
              <StageLinks
                completed={completed}
                failed={failed}
                stage="deploy"
                totalErrors={totalErrors} />
            </SectionFooter>
          </PageSection>
        </PageContent>
      </Page>
    );
  }
}

Deploy.contextTypes = {
  router: React.PropTypes.object
};

module.exports = Deploy;
