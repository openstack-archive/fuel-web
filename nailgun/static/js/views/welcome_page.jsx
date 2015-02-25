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
    'underscore',
    'i18n',
    'react',
    'utils',
    'models',
    'jsx!views/dialogs',
    'jsx!component_mixins',
    'jsx!views/statistics_mixin'
],
function(_, i18n, React, utils, models, dialogs, componentMixins, statisticsMixin) {
    'use strict';

    var WelcomePage = React.createClass({
        mixins: [
            statisticsMixin,
            componentMixins.backboneMixin('settings')
        ],
        statics: {
            title: i18n('welcome_page.title'),
            hiddenLayout: true,
            fetchData: function() {
                return app.settings.fetch({cache: true}).then(function() {
                    return {settings: app.settings};
                });
            }
        },
        onStartButtonClick: function(e) {
            this.props.settings.get('statistics').user_choice_saved.value = true;
            this.saveSettings(e)
                .done(function() {
                    app.navigate('', {trigger: true});
                })
                .fail(_.bind(function() {
                    this.props.settings.get('statistics').user_choice_saved.value = false;
                }, this));
        },
        render: function() {
            if (this.state.loading) return null;
            var ns = 'welcome_page.',
                isMirantisIso = _.contains(app.version.get('feature_groups'), 'mirantis'),
                statsCollectorLink = 'https://stats.fuel-infra.org/',
                privacyPolicyLink = 'https://www.mirantis.com/company/privacy-policy/',
                isConnected = false;
            return (
                <div className='welcome-page'>
                    <div>
                        <h2 className='center'>{this.getText(ns + 'title')}</h2>
                        <RegisterTrial/>
                        {this.renderInput('send_anonymous_statistic', null, 'welcome-checkbox-box')}
                        {this.renderIntro()}
                        {this.renderInput('send_user_info', null, 'welcome-checkbox-box')}
                        {isMirantisIso ?
                            <p>
                                <div>{i18n(ns + 'privacy_policy')}</div>
                                <div><a href={privacyPolicyLink} target='_blank'>{i18n(ns + 'privacy_policy_link')}</a>.</div>
                            </p>
                        :
                            <p>
                                {i18n(ns + 'statistics_collector')}
                                <a href={statsCollectorLink} target='_blank'>{statsCollectorLink}</a>.
                            </p>
                        }
                        <form className='form-horizontal'>
                            <div className='welcome-button-box'>
                                {isConnected ?
                                    <button autoFocus className='btn btn-large btn-success' disabled={this.state.actionInProgress || !!this.props.settings.validationError} onClick={this.onStartButtonClick}>
                                        {i18n(ns + 'start_fuel')}
                                    </button>
                                :
                                    <div>
                                        <button className='btn btn-large btn-unwanted' onClick={this.onStartButtonClick}>
                                            {i18n(ns + 'connect_later')}
                                        </button>
                                        <button autoFocus className='btn btn-large btn-success' disabled={this.state.actionInProgress || !!this.props.settings.validationError} onClick={this.onStartButtonClick}>
                                            {i18n(ns + 'connect_now')}
                                        </button>
                                    </div>
                                }
                            </div>
                        </form>
                        {isMirantisIso && <div className='welcome-text-box'>{i18n(ns + 'change_settings')}</div>}
                        <div className='welcome-text-box'>{this.getText(ns + 'thanks')}</div>
                    </div>
                </div>
            );
        }
    });

    var RegisterTrial = React.createClass({
        shouldShowMessage: function() {
            return _.contains(app.version.get('feature_groups'), 'mirantis') && !_.contains(app.version.get('feature_groups'), 'techpreview');
        },
        showRegistrationDialog: function() {
            utils.showDialog(dialogs.RegistrationDialog, {
                credentials: new models.MirantisCredentials()
            });
        },
        render: function() {
            if (this.shouldShowMessage()) {
                var ns = 'welcome_page.register.';
                return (
                    <div className='register-trial'>
                        <p className='register_installation'>{i18n(ns + 'register_installation')}</p>
                        <div className='registration-form'>
                            <div className='control-group'>
                                <label className='control-label'>Email:</label>
                                <div className='controls'>
                                    <input className='input-xlarge' type='text' name='username' ref='username' onChange={this.onChange} />
                                </div>
                            </div>
                            <div className='control-group'>
                                <label className='control-label'>Password:</label>
                                <div className='controls'>
                                    <input className='input-xlarge' type='password' name='password' ref='password' onChange={this.onChange} />
                                </div>
                            </div>
                            <div className='links-container'>
                                <a href='#' onClick={this.showRegistrationDialog} className='create-account'>{i18n(ns + 'create_account')}</a>
                                <a href='#registration' className='retrive-password'>{i18n(ns + 'retrive_password')}</a>
                            </div>
                        </div>
                    </div>
                );
            }
            return null;
        }
    });

    return WelcomePage;
});
