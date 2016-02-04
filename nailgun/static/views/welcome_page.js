/*
 * Copyright 2014 Mirantis, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the 'License'); you may
 * not use this file except in compliance with the License. You may obtain
 * a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an 'AS IS' BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations
 * under the License.
 **/
import i18n from 'i18n';
import React from 'react';
import {backboneMixin} from 'component_mixins';
import statisticsMixin from 'views/statistics_mixin';

var WelcomePage = React.createClass({
  mixins: [
    statisticsMixin,
    backboneMixin('settings', 'change')
  ],
  statics: {
    title: i18n('welcome_page.title'),
    hiddenLayout: true,
    fetchData() {
      return app.fuelSettings.fetch().then(() => {
        return {
          settings: app.fuelSettings
        };
      });
    }
  },
  onStartButtonClick() {
    var statistics = this.props.settings.get('statistics');
    //var currentAttributes = _.cloneDeep(this.props.settings.attributes);
    statistics.user_choice_saved.value = true;
    // locked state is similar to actionInProgress but
    // we want the page isn't unlocked after successful saving
    //this.setState({locked: true});
    //this.props.settings.set(this.props.tracking.attributes);
    this.saveSettings()
      .done(() => {
        app.navigate('', {trigger: true});
      })
      .fail(() => {
        statistics.user_choice_saved.value = false;
        this.setState({locked: false});
      });
  },
  render() {
    var ns = 'welcome_page.';
    var statsCollectorLink = 'https://stats.fuel-infra.org/';
    var disabled = this.state.actionInProgress;
    var buttonProps = {
      disabled: disabled,
      onClick: this.onStartButtonClick,
      className: 'btn btn-lg btn-block btn-success'
    };
    return (
      <div className='welcome-page tracking'>
        <div className='col-md-8 col-md-offset-2 col-xs-10 col-xs-offset-1'>
          <h1 className='text-center'>{this.getText(ns + 'title')}</h1>
          <div>
            {this.renderIntro()}
            {this.renderInput('send_anonymous_statistic', 'welcome-checkbox-box')}
            <div>
              <div>{i18n(ns + 'statistics_collector')}</div>
              <div><a href={statsCollectorLink} target='_blank'>{statsCollectorLink}</a></div>
            </div>
          </div>
          <div className='welcome-button-box row'>
            <div className='col-xs-6 col-xs-offset-3'>
              <button autoFocus {...buttonProps}>
                {i18n(ns + 'start_fuel')}
              </button>
            </div>
          </div>
          <div className='welcome-text-box'>{this.getText(ns + 'thanks')}</div>
        </div>
      </div>
    );
  }
});

export default WelcomePage;
