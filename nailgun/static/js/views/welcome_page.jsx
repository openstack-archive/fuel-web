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
            componentMixins.backboneMixin('settings', 'change invalid')
        ],
        statics: {
            title: i18n('welcome_page.title'),
            hiddenLayout: true,
            fetchData: function() {
                var remoteLoginForm = new models.MirantisLoginForm(),
                    remoteRetrievePasswordForm = new models.MirantisRetrievePasswordForm();
                return app.settings.fetch({cache: true}).then(function() {
                    return {settings: app.settings, remoteLoginForm: remoteLoginForm, remoteRetrievePasswordForm: remoteRetrievePasswordForm};
                });
            }
        },
        componentDidMount: function() {
            var remoteLoginForm = this.props.remoteLoginForm;
            remoteLoginForm.fetch()
                .done(_.bind(function() {this.setState({loading: false});}, this))
                .fail(_.bind(function() {
                    remoteLoginForm.url = remoteLoginForm.nailgunUrl;
                    remoteLoginForm.fetch()
                        .fail(this.showResponseErrors)
                        .always(_.bind(function() {this.setState({loading: false});}, this));
                }, this));
        },
        getInitialState: function() {
            return {isConnected: false};
        },
        onStartButtonClick: function(e) {
            if (!this.state.isConnected) this.cleanConnectionForm();
            this.props.settings.get('statistics').user_choice_saved.value = true;
            this.setState({disabled: true});
            this.saveSettings(e)
                .done(function() {
                    app.navigate('', {trigger: true});
                })
                .fail(_.bind(function() {
                    this.props.settings.get('statistics').user_choice_saved.value = false;
                    this.setState({disabled: false});
                }, this));
        },
        cleanConnectionForm: function() {
            var settings = this.props.settings;
            _.each(settings.get('tracking'), function(data, inputName) {
                var name = settings.makePath('tracking', inputName, 'value');
                settings.set(name, '');
            });
        },
        setConnected: function() {
            this.setState({isConnected: true});
        },
        render: function() {
            if (this.state.loading) return null;
            var ns = 'welcome_page.',
                isMirantisIso = _.contains(app.version.get('feature_groups'), 'mirantis'),
                statsCollectorLink = 'https://stats.fuel-infra.org/',
                privacyPolicyLink = 'https://www.mirantis.com/company/privacy-policy/';
            return (
                <div className='welcome-page'>
                    <div>
                        <h2 className='center'>{this.getText(ns + 'title')}</h2>
                        <RegisterTrial
                            {... _.pick(this.state, 'isConnected', 'actionInProgress', 'error', 'userData')}
                            {... _.pick(this.props, 'settings', 'remoteRetrievePasswordForm')}
                            setConnected={this.setConnected}/>
                        {isMirantisIso ?
                            <div>
                                {this.renderInput('send_anonymous_statistic', null, 'welcome-checkbox-box')}
                                {this.renderIntro()}
                                {this.renderInput('send_user_info', null, 'welcome-checkbox-box')}
                                <p>
                                    <div className='notice'>{i18n(ns + 'privacy_policy')}</div>
                                    <div><a href={privacyPolicyLink} target='_blank'>{i18n(ns + 'privacy_policy_link')}</a></div>
                                </p>
                            </div>
                        :
                            <div>
                                {this.renderIntro()}
                                {this.renderInput('send_anonymous_statistic', null, 'welcome-checkbox-box')}
                                <p>
                                    <div>{i18n(ns + 'statistics_collector')}</div>
                                    <div><a href={statsCollectorLink} target='_blank'>{statsCollectorLink}</a></div>
                                </p>
                            </div>
                        }
                        <form className='form-horizontal'>
                            <div className='welcome-button-box'>
                                {this.state.isConnected || !isMirantisIso ?
                                    <button autoFocus className='btn btn-large btn-success' disabled={this.state.actionInProgress || this.state.disabled} onClick={this.onStartButtonClick}>
                                        {i18n(ns + 'start_fuel')}
                                    </button>
                                :
                                    <div>
                                        <button className='btn btn-large btn-unwanted' onClick={this.onStartButtonClick} disabled={this.state.actionInProgress || this.state.disabled}>
                                            {i18n(ns + 'connect_later')}
                                        </button>
                                        <button autoFocus className='btn btn-large btn-success' disabled={this.state.actionInProgress || this.state.disabled} onClick={this.connectToMirantis}>
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
            var settings = this.props.settings,
                name = settings.makePath('tracking', inputName, 'value');
            if (settings.validationError) delete settings.validationError['tracking.' + inputName];
            settings.set(name, value);
        },
        shouldShowMessage: function() {
            return _.contains(app.version.get('feature_groups'), 'mirantis') && !_.contains(app.version.get('feature_groups'), 'techpreview');
        },
        showRegistrationDialog: function() {
            dialogs.RegistrationDialog.show({
                registrationForm: new models.MirantisRegistrationForm(),
                setConnected: this.props.setConnected,
                settings: this.props.settings
            });
        },
        showRetrievePasswordDialog: function() {
            dialogs.RetrievePasswordDialog.show({
                remoteRetrievePasswordForm: this.props.remoteRetrievePasswordForm
            });
        },
        render: function() {
            var settings = this.props.settings,
                loginForm = this.props.settings.get('tracking'),
                actionInProgress = this.props.actionInProgress,
                sortedFields = _.chain(_.keys(loginForm))
                    .without('metadata')
                    .sortBy(function(inputName) {return loginForm[inputName].weight;})
                    .value(),
                error = this.props.error;
            if (this.shouldShowMessage()) {
                var ns = 'welcome_page.register.';
                return (
                    <div className='register-trial'>
                        {this.props.isConnected ?
                            <div className='happy-cloud'>
                                <div className='cloud-smile'></div>
                                <div>{i18n(ns + 'welcome_phrase.thanks')} {this.props.settings.get('statistics').name.value}, {i18n(ns + 'welcome_phrase.content')}</div>
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
                                <div className='connection-form'>
                                    {_.map(sortedFields, function(inputName) {
                                        var input = loginForm[inputName],
                                            path = 'tracking.' + inputName,
                                            error = settings.validationError && settings.validationError[path];
                                        return <controls.Input
                                            ref={inputName}
                                            key={inputName}
                                            name={inputName}
                                            {... _.pick(input, 'type', 'label', 'value')}
                                            onChange={this.onChange}
                                            error={error}/>;
                                    }, this)}
                                    <div className='links-container'>
                                        <a onClick={this.showRegistrationDialog} className='create-account'>{i18n(ns + 'create_account')}</a>
                                        <a onClick={this.showRetrievePasswordDialog} className='retrive-password'>{i18n(ns + 'retrieve_password')}</a>
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
