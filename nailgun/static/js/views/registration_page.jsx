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
    'jsx!views/statistics_mixin',
    'jsx!views/controls'
],
function(_, i18n, React, models, componentMixins, statisticsMixin, controls) {
    'use strict';

    var RegistrationPage = React.createClass({
        mixins: [
            componentMixins.backboneMixin('settings')
        ],
        statics: {
            title: i18n('welcome_page.title'),
            hiddenLayout: true,
            fetchData: function() {
                var credentials  = new models.MirantisCredentials();
                return app.settings.fetch({cache: true}).then(function() {
                    return {
                        settings: app.settings,
                        credentials: credentials
                    };
                });
            }
        },
        getInitialState: function() {
            return {
                loading: true
            };
        },
        componentDidMount: function() {
            var credentials = this.props.credentials;
            credentials.fetch().done(_.bind(function() {
                this.setState({
                    credentials: credentials,
                    loading: false
                });
            }, this));
        },
        composeOptions: function(values) {
            return _.map(values, function(value, index) {
                return (
                    <option key={index} value={value.data} disabled={value.disabled}>
                        {value.label}
                    </option>
                );
            });
        },
        getName: function(label) {
            return label;
        },
        render: function() {
            var credentials = this.state.credentials,
                sortedFields = [];
            if (credentials) {
                var fields = credentials.attributes;
                sortedFields = _.chain(_.keys(credentials.attributes))
                    .without('metadata')
                    .sortBy(function(inputName) {return credentials.attributes[inputName].weight;})
                    .value();
            }
            return (
                <div className='registration-page'>
                    <div>
                        <h2 className='center'>Please fill in this form to create an account</h2>
                            {credentials ?
                                <form className='form-horizontal'>
                                    {_.map(sortedFields, function(inputName) {
                                        var input = fields[inputName];
                                        return <controls.Input
                                            key={inputName}
                                            name={inputName}
                                            type={input.type}
                                            children={input.type == 'select' ? this.composeOptions(input.values) : null}
                                            label={input.label}
                                            description={input.description}
                                        />;
                                    }, this)}
                                </form>
                            :
                                <div> Loading </div>
                            }
                        <div>Buttons block</div>
                    </div>
                </div>
            );
        }
    });

    return RegistrationPage;
});
