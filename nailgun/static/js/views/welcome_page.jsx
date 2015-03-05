/*
 * Copyright 201 Mirantis, Inc.
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
    'underscore',
    'i18n',
    'react',
    'utils',
    'models',
    'jsx!views/dialogs',
    'jsx!component_mixins',
    'jsx!views/statistics_mixin',
    'jsx!views/controls'
],
function($, _, i18n, React, utils, models, dialogs, componentMixins, statisticsMixin, controls) {
    'use strict';

    var WelcomePage = React.createClass({
        mixins: [
            statisticsMixin,
            componentMixins.backboneMixin('settings'),
            componentMixins.backboneMixin('connectForm', 'change invalid')
        ],
        statics: {
            title: i18n('welcome_page.title'),
            hiddenLayout: true,
            fetchData: function() {
                var connectForm = new models.MirantisConnect();
                return $.when(app.settings.fetch({cache: true}), connectForm.fetch()).then(function() {
                    return {
                        settings: app.settings,
                        connectForm: connectForm
                    };
                });
            }
        },
        getInitialState: function() {
            return {isConnected: false};
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
        setConnected: function() {
            this.setState({isConnected: true});
        },
        render: function() {
            if (this.state.loading) return null;
            var ns = 'welcome_page.',
                isMirantisIso = _.contains(app.version.get('feature_groups'), 'mirantis'),
                connectForm = this.props.connectForm.attributes.credentials,
                statsCollectorLink = 'https://stats.fuel-infra.org/',
                privacyPolicyLink = 'https://www.mirantis.com/company/privacy-policy/';
            return (
                <div className='welcome-page'>
                    <div>
                        <h2 className='center'>{this.getText(ns + 'title')}</h2>
                        <RegisterTrial
                            {... _.pick(this.state, 'isConnected', 'actionInProgress', 'error', 'userData')}
                            setConnected={this.setConnected}
                            connectForm={this.props.connectForm}
                            settings={this.props.settings}/>
                        {isMirantisIso && this.renderInput('send_anonymous_statistic', null, 'welcome-checkbox-box')}
                        {this.renderIntro()}
                        {!isMirantisIso && this.renderInput('send_anonymous_statistic', null, 'welcome-checkbox-box')}
                        {this.renderInput('send_user_info', null, 'welcome-checkbox-box', !!this.props.connectForm.validationError || !connectForm.email.value || !connectForm.password.value)}
                        {isMirantisIso ?
                            <p>
                                <div className='notice'>{i18n(ns + 'privacy_policy')}</div>
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
                                {this.state.isConnected || !isMirantisIso ?
                                    <button autoFocus className='btn btn-large btn-success' disabled={this.state.actionInProgress || !!this.props.settings.validationError} onClick={this.onStartButtonClick}>
                                        {i18n(ns + 'start_fuel')}
                                    </button>
                                :
                                    <div>
                                        <button className='btn btn-large btn-unwanted' onClick={this.onStartButtonClick}>
                                            {i18n(ns + 'connect_later')}
                                        </button>
                                        <button autoFocus className='btn btn-large btn-success' disabled={this.state.actionInProgress || !!this.props.settings.validationError} onClick={this.connectToMirantis}>
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
        getInitialState: function() {
            return {};
        },
        onChange: function(inputName, value) {
            var credentials = this.props.connectForm,
                name = credentials.makePath('credentials', inputName, 'value');
            credentials.set(name, value);
            if (credentials.validationError) delete credentials.validationError['credentials.' + inputName];
        },
        shouldShowMessage: function() {
            return _.contains(app.version.get('feature_groups'), 'mirantis') && !_.contains(app.version.get('feature_groups'), 'techpreview');
        },
        showRegistrationDialog: function() {
            utils.showDialog(dialogs.RegistrationDialog, {
                credentials: new models.MirantisCredentials(),
                setConnected: this.props.setConnected,
                settings: this.props.settings
            });
        },
        retrievePasswordDialog: function() {
            utils.showDialog(dialogs.RetrievePasswordDialog);
        },
        render: function() {
            var credentials = this.props.connectForm;
            if (!credentials.attributes) return <controls.ProgressBar />;
            var fieldsList = credentials.attributes.credentials,
                actionInProgress = this.props.actionInProgress,
                error = this.props.error,
                sortedFields = ['email', 'password'];
            if (this.shouldShowMessage()) {
                var ns = 'welcome_page.register.';
                return (
                    <div className='register-trial'>
                        {this.props.isConnected ?
                            <div className='happy-cloud'>
                                <div className='cloud-smile'></div>
                                <div>Thanks {this.props.settings.get('statistics').name.value || 'Eugene'}, you’re all set!</div>
                            </div>
                        :
                            <div>
                                <p className='register_installation'>{i18n(ns + 'register_installation')}</p>
                                {actionInProgress && <controls.ProgressBar />}
                                {error &&
                                    <div className='error'>
                                        <i className='icon-attention'></i>
                                        {error}
                                    </div>
                                }
                                <div className='connection_form'>
                                    {_.map(sortedFields, function(inputName) {
                                        var input = fieldsList[inputName],
                                            path = 'credentials.' + inputName,
                                            error = credentials.validationError && credentials.validationError[path];
                                        return <controls.Input
                                            ref={inputName}
                                            key={inputName}
                                            name={inputName}
                                            type={input.type}
                                            label={input.label}
                                            value={input.value}
                                            onChange={this.onChange}
                                            error={error}/>;
                                    }, this)}
                                    <div className='links-container'>
                                        <a onClick={this.showRegistrationDialog} className='create-account'>{i18n(ns + 'create_account')}</a>
                                        <a onClick={this.retrievePasswordDialog} className='retrive-password'>{i18n(ns + 'retrive_password')}</a>
                                    </div>
                                </div>
                            </div>
                        }
                    </div>
                );
            }
            return null;
        }
    });

    return WelcomePage;
});
