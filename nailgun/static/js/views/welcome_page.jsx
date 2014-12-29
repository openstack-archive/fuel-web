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
    'models',
    'jsx!component_mixins',
    'jsx!views/statistics_mixin'
],
function(_, i18n, React, models, componentMixins, statisticsMixin) {
    'use strict';

    var WelcomePage = React.createClass({
        mixins: [
            statisticsMixin,
            componentMixins.backboneMixin('settings')
        ],
        breadcrumbsPath: [],
        hiddenLayout: true,
        title: function() {
            return this.getText('welcome_page.title');
        },
        statics: {
            fetchData: function() {
                return app.settings.fetch({cache: true}).then(function() {
                    return {settings: app.settings};
                });
            }
        },
        getInitialState: function() {
            return {fuelKey: new models.FuelKey()};
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
                contacts = ['name', 'email', 'company'],
                error = _.compact(_.map(contacts, this.getError, this))[0],
                isMirantisIso = _.contains(app.version.get('feature_groups'), 'mirantis');
            return (
                <div className='welcome-page'>
                    <div>
                        <h2 className='center'>{this.getText(ns + 'title')}</h2>
                        <RegisterTrial fuelKey={this.state.fuelKey} />
                        {this.renderIntro()}
                        {this.renderInput('send_anonymous_statistic', null, 'welcome-checkbox-box')}
                        {isMirantisIso && <div className='welcome-text-box'>{i18n(ns + 'support')}</div>}
                        {this.renderInput('send_user_info', null, 'welcome-checkbox-box')}
                        <form className='form-horizontal'>
                            {this.props.settings.get('statistics').send_user_info.value &&
                                <div className='welcome-text-box'>{i18n(ns + 'provide_contacts')}</div>
                            }
                            { _.map(contacts, function(settingName) {
                                return this.renderInput(settingName, 'welcome-form-item', 'welcome-form-box', true);
                            }, this)}
                            {error &&
                                <div className='welcome-form-error'>{i18n(error)}</div>
                            }
                            <div className='welcome-button-box'>
                                <button autoFocus className='btn btn-large btn-success' disabled={this.state.actionInProgress} onClick={this.onStartButtonClick}>
                                    {i18n(ns + 'start_fuel')}
                                </button>
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
        mixins: [componentMixins.backboneMixin('fuelKey')],
        shouldShowMessage: function() {
            return _.contains(app.version.get('feature_groups'), 'mirantis') && !_.contains(app.version.get('feature_groups'), 'techpreview');
        },
        componentWillMount: function() {
            if (this.shouldShowMessage()) {
                this.props.fuelKey.fetch();
            }
        },
        render: function() {
            if (this.shouldShowMessage()) {
                var ns = 'welcome_page.register_trial.',
                    key = this.props.fuelKey.get('key');
                return (
                    <div className='register-trial'>
                        <p>{i18n(ns + 'register_installation')}</p>
                        <p>{i18n(ns + 'register_now')}</p>
                        <p>
                            <a target="_blank" className="btn btn-info" href={!_.isUndefined(key) ? 'http://fuel.mirantis.com/create-subscriber/?key=' + key : '/'}>{i18n(ns + 'link_text')}</a>
                        </p>
                    </div>
                );
            }
            return null;
        }
    });

    return WelcomePage;
});
