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
            componentMixins.backboneMixin('tracking', 'change invalid')
        ],
        statics: {
            title: i18n('welcome_page.title'),
            hiddenLayout: true,
            fetchData: function() {
                return app.settings.fetch().then(function() {
                    var tracking = new models.FuelSettings(_.cloneDeep(app.settings.attributes));
                    tracking.processRestrictions();
                    return {
                        settings: app.settings,
                        tracking: tracking
                    };
                });
            }
        },
        onStartButtonClick: function() {
            this.clearRegistrationForm();
            var statistics = this.props.tracking.get('statistics'),
                currentAttributes = _.cloneDeep(this.props.settings.attributes);
            statistics.user_choice_saved.value = true;
            // locked state is similar to actionInProgress but
            // we want the page isn't unlocked after successful saving
            this.setState({locked: true});
            this.props.settings.set(this.props.tracking.attributes);
            this.saveSettings(currentAttributes)
                .done(function() {
                    app.navigate('', {trigger: true});
                })
                .fail(_.bind(function() {
                    statistics.user_choice_saved.value = false;
                    this.setState({locked: false});
                }, this));
        },
        render: function() {
            var ns = 'welcome_page.',
                featureGroups = app.version.get('feature_groups'),
                isMirantisIso = _.contains(featureGroups, 'mirantis'),
                statsCollectorLink = 'https://stats.fuel-infra.org/',
                privacyPolicyLink = 'https://www.mirantis.com/company/privacy-policy/',
                username = this.props.settings.get('statistics').name.value;
            var disabled = this.state.actionInProgress || this.state.locked,
                buttonProps = {
                    disabled: disabled,
                    onClick: this.onStartButtonClick,
                    className: 'btn btn-lg btn-block btn-success'
                };
            return (
                <div className='welcome-page tracking'>
                    <div className='col-md-8 col-md-offset-2 col-xs-10 col-xs-offset-1'>
                        <h1 className='text-center'>{this.getText(ns + 'title')}</h1>
                        {isMirantisIso ?
                            <div>
                                {!_.contains(featureGroups, 'techpreview') &&
                                    <div className='register-trial'>
                                        {this.state.isConnected ?
                                            <div className='happy-cloud'>
                                                <div className='cloud-smile' />
                                                <div className='row'>
                                                    <div className='col-xs-8 col-xs-offset-2'>{i18n(ns + 'register.welcome_phrase.thanks')}{username ? ' ' + username : ''}, {i18n(ns + 'register.welcome_phrase.content')}</div>
                                                </div>
                                            </div>
                                        :
                                            <div>
                                                <p className='register_installation'>{i18n(ns + 'register.register_installation')}</p>
                                                {this.renderRegistrationForm(this.props.tracking, disabled, this.state.error, this.state.actionInProgress && !this.state.locked)}
                                            </div>
                                        }
                                    </div>
                                }
                                {this.renderInput('send_anonymous_statistic', 'welcome-checkbox-box', disabled)}
                                {this.renderIntro()}
                                {this.renderInput('send_user_info', 'welcome-checkbox-box', disabled)}
                                <p>
                                    <div className='notice'>{i18n(ns + 'privacy_policy')}</div>
                                    <div><a href={privacyPolicyLink} target='_blank'>{i18n(ns + 'privacy_policy_link')}</a></div>
                                </p>
                            </div>
                        :
                            <div>
                                {this.renderIntro()}
                                {this.renderInput('send_anonymous_statistic', 'welcome-checkbox-box')}
                                <p>
                                    <div>{i18n(ns + 'statistics_collector')}</div>
                                    <div><a href={statsCollectorLink} target='_blank'>{statsCollectorLink}</a></div>
                                </p>
                            </div>
                        }
                        <div className='welcome-button-box row'>
                            {this.state.isConnected || !isMirantisIso ?
                                <div className='col-xs-6 col-xs-offset-3'>
                                    <button autoFocus {...buttonProps}>
                                        {i18n(ns + 'start_fuel')}
                                    </button>
                                </div>
                            :
                                <div className='col-xs-10 col-xs-offset-1'>
                                    <div className='row'>
                                        <div className='col-xs-6'>
                                            <button {...buttonProps} className='btn btn-lg btn-block btn-default'>
                                                {i18n(ns + 'connect_later')}
                                            </button>
                                        </div>
                                        <div className='col-xs-6'>
                                            <button autoFocus {...buttonProps} onClick={this.connectToMirantis}>
                                                {i18n(ns + 'connect_now')}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            }
                        </div>
                        {isMirantisIso && <div className='welcome-text-box'>{i18n(ns + 'change_settings')}</div>}
                        <div className='welcome-text-box'>{this.getText(ns + 'thanks')}</div>
                    </div>
                </div>
            );
        }
    });

    return WelcomePage;
});
