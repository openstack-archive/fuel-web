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
    'utils',
    'jsx!views/controls',
    'jsx!views/statistics_mixin'
],
function($, React, utils, controls, statisticsMixin) {
    'use strict';

    var WelcomePage = React.createClass({
        mixins: [
            statisticsMixin,
            React.BackboneMixin('settings')
        ],
        breadcrumbsPath: [],
        customLayout: true,
        title: function() {
            return $.t('welcome_page.title');
        },
        onStartButtonClick: function(e) {
            this.props.settings.get('statistics').show_welcome_page.value = false;
            this.saveSettings(e)
                .done(function() {
                    app.navigate('#clusters', {trigger: true});
                })
                .fail(_.bind(function() {
                    this.props.settings.get('statistics').show_welcome_page.value = true;
                }, this));
        },
        render: function() {
            if (this.state.loading) return <controls.ProgressBar />;
            var ns = 'welcome_page.',
                contacts = _.chain(_.keys(this.get('user_info')))
                    .sortBy(function(settingName) {
                        return this.get('user_info', settingName, 'weight');
                    }, this)
                    .without('metadata').value(),
                error = null;
            if (this.props.settings.validationError) {
                _.each(contacts, function(name) {
                    error = this.props.settings.validationError[utils.makePath('user_info', name)];
                    return !error;
                }, this);
            }
            return (
                <div className='welcome-page'>
                    <div>
                        <h2 className='center'>{$.t(ns + 'title')}</h2>
                        {this.renderIntro()}
                        {this.renderInput(this.get('statistics', 'send_anonymous_statistic'), 'statistics', 'send_anonymous_statistic', null, 'welcome-checkbox-box')}
                        <div className='welcome-text-box'>
                            <p className='center'>
                                {$.t(ns + 'support')}<br/>
                                {$.t(ns + 'provide_contacts')}
                            </p>
                        </div>
                        {this.renderInput(this.get('statistics', 'send_user_info'), 'statistics', 'send_user_info', null, 'welcome-checkbox-box')}
                        <form className='form-horizontal'>
                            { _.map(contacts, function(settingName) {
                                return this.renderInput(this.get('user_info', settingName), 'user_info', settingName, 'welcome-form-item', 'welcome-form-box', true);
                            }, this)}
                            {error &&
                                <div className='welcome-form-error'>{error}</div>
                            }
                            <div className='welcome-button-box'>
                                <button className='btn btn-large btn-success' disabled={this.state.actionInProgress} onClick={this.onStartButtonClick}>
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
