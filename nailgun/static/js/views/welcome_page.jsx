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
define(
[
    'jquery',
    'react',
    'jsx!views/controls',
    'jsx!views/statistics_mixin'
],
function($, React, controls, statisticsMixin) {
    'use strict';

    var WelcomePage = React.createClass({
        mixins: [
            statisticsMixin,
            React.BackboneMixin('settings')
        ],
        breadcrumbsPath: [],
        hiddenLayout: true,
        title: function() {
            return $.t('welcome_page.title');
        },
        onStartButtonClick: function(e) {
            this.props.settings.get('statistics').user_choice_saved.value = true;
            this.saveSettings(e)
                .done(function() {
                    app.navigate('#clusters', {trigger: true});
                })
                .fail(_.bind(function() {
                    this.props.settings.get('statistics').user_choice_saved.value = false;
                }, this));
        },
        render: function() {
            if (this.state.loading) return <controls.ProgressBar />;
            var ns = 'welcome_page.',
                contacts = ['name', 'email', 'company'],
                error = _.compact(_.map(contacts, this.getError, this))[0];
            return (
                <div className='welcome-page'>
                    <div>
                        <h2 className='center'>{$.t(ns + 'title')}</h2>
                        {this.renderIntro()}
                        {this.renderInput('send_anonymous_statistic', null, 'welcome-checkbox-box')}
                        <div className='welcome-text-box'>
                            <p className='center'>
                                {$.t(ns + 'support')}<br/>
                                {$.t(ns + 'provide_contacts')}
                            </p>
                        </div>
                        {this.renderInput('send_user_info', null, 'welcome-checkbox-box')}
                        <form className='form-horizontal'>
                            { _.map(contacts, function(settingName) {
                                return this.renderInput(settingName, 'welcome-form-item', 'welcome-form-box', true);
                            }, this)}
                            {error &&
                                <div className='welcome-form-error'>{$.t(error)}</div>
                            }
                            <div className='welcome-button-box'>
                                <button autoFocus className='btn btn-large btn-success' disabled={this.state.actionInProgress} onClick={this.onStartButtonClick}>
                                    {$.t(ns + 'start_fuel')}
                                </button>
                            </div>
                        </form>
                        <div className='welcome-text-box'>
                            <p className='center'>
                                {$.t(ns + 'change_settings')}<br/>
                                {$.t(ns + 'thanks')}
                            </p>
                        </div>
                    </div>
                </div>
            );
        }
    });

    return WelcomePage;
});
